"""Tests for the Gemini LLM augmentation wiring.

These mock the google-genai SDK so they run without network or an API key.
Exercises:
  - the SDK is called with the expected model + structured-output config
  - the score-first invariant survives an LLM response that tries to mutate score
  - the LLM can populate the new structured fields (tone, coverage_gaps, verdict_probability)
  - missing API key path falls through to the deterministic baseline unchanged
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.analyzer import ReportContext, analyze_report
from app.config import get_settings


NFP_TEXT = (
    "Total nonfarm payroll employment increased by 150,000 in April. "
    "The change in total nonfarm payroll employment for February was revised down by 35,000 "
    "and the change for March was revised down by 22,000. "
    "Government employment increased by 38,000."
)


def _ctx() -> ReportContext:
    return ReportContext(
        source="BLS",
        report_type="Nonfarm Payrolls",
        release_date="2026-05-02",
        headline="Payrolls jump by 150k, crushing the 65k estimate",
        report_text=NFP_TEXT,
    )


def _fake_gemini_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(text=json.dumps(payload))


def _llm_payload(score_to_try: int) -> dict:
    """A plausible Gemini response. Sets new structured fields and tries
    (illegitimately) to mutate the score, so the test can verify the
    invariant overrides it."""
    return {
        "verdict": "Headline mostly supported",  # LLM-rewritten prose
        "summary": "Headline figure matches but revisions undercut quality.",
        "score": score_to_try,                   # invariant should overwrite this
        "confidence": 0.81,
        "metrics": [],                           # invariant should overwrite this
        "score_components": [],                  # invariant should overwrite this
        "supporting_factors": ["Headline figure matches the release."],
        "contradicting_factors": ["Headline omits -57k revisions."],
        "caveats": [],
        "citations": [],
        "model_used": "gemini-2.5-flash-lite",
        "headline_claims": [],
        "composition": [],
        "revision_adjustment": None,
        "tone": {
            "headline_intensity": 0.85,
            "data_intensity": 0.45,
            "gap": 0.4,
            "loaded_words": ["jump", "crushing"],
            "note": "Tone overstates the magnitude of the surprise.",
        },
        "coverage_gaps": [
            {
                "topic": "Prior-month revisions",
                "release_emphasis_pct": 22.0,
                "in_headline": False,
                "note": "Release dedicates ~22% of words to revisions; headline omits them.",
            }
        ],
        "verdict_probability": {
            "accurate_summary_p": 0.42,
            "ci_low": 0.35,
            "ci_high": 0.5,
            "components": {
                "figure_accuracy": 0.95,
                "context_completeness": 0.25,
                "tone_calibration": 0.4,
                "composition_disclosure": 0.3,
            },
            "note": "Figures accurate; context and tone undercut overall accuracy.",
        },
    }


def _patch_settings(monkeypatch: pytest.MonkeyPatch, key: str = "fake-key") -> None:
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    get_settings.cache_clear()


def test_gemini_sdk_called_with_expected_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)
    captured: dict = {}

    def fake_generate_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["config"] = config
        return _fake_gemini_response(_llm_payload(99))

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate_content))
    with patch("app.gemini_analysis.genai.Client", return_value=fake_client):
        analyze_report(_ctx())

    assert captured["model"] == "gemini-2.5-flash-lite"
    cfg = captured["config"]
    # Both pydantic dataclass-style and dict-style configs are acceptable.
    cfg_dict = cfg if isinstance(cfg, dict) else cfg.model_dump()
    assert cfg_dict.get("response_mime_type") == "application/json"
    assert cfg_dict.get("response_json_schema") is not None
    assert "INVARIANT" in (cfg_dict.get("system_instruction") or "")
    # The user payload was JSON and contained the headline + report text.
    user = json.loads(captured["contents"])
    assert user["headline"].startswith("Payrolls jump")
    assert "deterministic_baseline" in user


def test_invariant_overrides_score_returned_by_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM returns score=99 but baseline computed something else; baseline wins."""
    _patch_settings(monkeypatch)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kw: _fake_gemini_response(_llm_payload(99))
        )
    )
    with patch("app.gemini_analysis.genai.Client", return_value=fake_client):
        result = analyze_report(_ctx())

    # Baseline score for this NFP example is in the 40s — never 99.
    assert result.score != 99
    # And the deterministic metrics/components survive (LLM tried to send empty lists).
    assert len(result.metrics) > 0
    assert len(result.score_components) > 0


def test_llm_only_fields_are_populated_when_gemini_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)

    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kw: _fake_gemini_response(_llm_payload(99))
        )
    )
    with patch("app.gemini_analysis.genai.Client", return_value=fake_client):
        result = analyze_report(_ctx())

    assert result.tone is not None
    assert result.tone.headline_intensity == pytest.approx(0.85)
    assert "crushing" in result.tone.loaded_words

    assert len(result.coverage_gaps) == 1
    assert result.coverage_gaps[0].topic == "Prior-month revisions"

    assert result.verdict_probability is not None
    assert result.verdict_probability.accurate_summary_p == pytest.approx(0.42)


def test_no_api_key_falls_through_to_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    # Patch genai.Client so the test fails loudly if the SDK is touched.
    def boom(*args, **kwargs):
        raise AssertionError("Gemini SDK should not be invoked when no API key is set")

    with patch("app.gemini_analysis.genai.Client", side_effect=boom):
        result = analyze_report(_ctx())

    # Deterministic-only result: structured fields populated, LLM fields None.
    assert result.tone is None
    assert result.coverage_gaps == []
    assert result.verdict_probability is None
    assert result.model_used == "local-heuristic-v0"


def test_gemini_failure_is_caught_and_caveated(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_settings(monkeypatch)

    def boom(**kwargs):
        raise RuntimeError("simulated gemini transport error")

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=boom))
    with patch("app.gemini_analysis.genai.Client", return_value=fake_client):
        result = analyze_report(_ctx())

    assert any("Gemini" in c for c in result.caveats), result.caveats
    assert result.tone is None  # LLM-only fields stay empty on failure
    assert result.model_used == "local-heuristic-v0"
