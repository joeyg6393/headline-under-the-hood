"""LLM augmentation via Google's Gemini API.

Per the score-first invariant in CLAUDE.md, the deterministic analyzer always
owns score, metrics, and score_components. This module asks Gemini to populate
the LLM-only structured fields (tone, coverage_gaps, verdict_probability) and
to refine the prose around the deterministic baseline. The caller in
``app.analyzer.analyze_report`` re-applies the invariant after this returns.

Default model: ``gemini-2.5-flash-lite`` — the fastest, lowest-cost model in
the 2.5 family. Override via ``GEMINI_MODEL`` in ``.env``.
"""
from __future__ import annotations

import json

from google import genai
from google.genai import types as genai_types

from app.analyzer import ReportContext
from app.config import get_settings
from app.schemas import AnalysisResult


SYSTEM_INSTRUCTION = """You analyze official economic and financial releases against a reported
news headline. Return only structured JSON matching the requested schema.

INVARIANT: The deterministic baseline owns the score, metrics, and score_components.
You MUST NOT modify these fields - they will be overwritten back to the baseline values
after your response. You are responsible for the supporting prose and for populating
the LLM-only structured fields described below.

You can REFINE these fields the baseline already populated:
  - headline_claims:  add precise verdicts (match | partial | contradicts | unsupported |
                      missing_context), notes that cite specific release language, and
                      citation_ref values. Keep all baseline claims; you may add new ones.
  - composition:      adjust slice labels, add notes, or add slices the baseline missed.
  - revision_adjustment: refine the note with a one-line journalistic explanation.

You SOLELY populate these LLM-only fields:
  - tone:                 headline_intensity (0-1, how loaded is the headline language),
                          data_intensity (0-1, how dramatic the actual data is),
                          gap = headline_intensity - data_intensity,
                          loaded_words = list of intense words in the headline.
  - coverage_gaps:        topics the release devotes significant space to that the
                          headline does not mention. release_emphasis_pct is the rough
                          share of the release dedicated to the topic (estimate from
                          paragraph weight). in_headline = false unless the headline
                          mentions it explicitly.
  - verdict_probability:  accurate_summary_p in [0,1], with ci_low/ci_high. components
                          should be a dict like
                          {"figure_accuracy": 0.9, "context_completeness": 0.4,
                           "tone_calibration": 0.5, "composition_disclosure": 0.3}.
                          The note should explain in one sentence what drives the verdict.

Be skeptical but not sensational. Cite short excerpts from the supplied report text only.
"""


def analyze_with_gemini(context: ReportContext, baseline: AnalysisResult) -> AnalysisResult:
    """Augment the deterministic baseline by calling Gemini.

    Raises whatever ``google-genai`` raises on transport / parsing failure so
    that the caller in ``analyzer.analyze_report`` can catch and degrade
    gracefully back to the baseline.
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    schema = AnalysisResult.model_json_schema()

    user_payload = json.dumps(
        {
            "source": context.source,
            "report_type": context.report_type,
            "release_date": context.release_date,
            "headline": context.headline,
            "report_text": context.report_text[:50_000],
            "deterministic_baseline": baseline.model_dump(),
        },
        ensure_ascii=True,
    )

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_payload,
        config=genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema=schema,
        ),
    )

    raw = (response.text or "").strip()
    if not raw:
        # Gemini returned no text (safety filter, empty completion, etc).
        # Return the baseline unchanged with a caveat the caller can surface.
        baseline.caveats.append("Gemini returned an empty response; local fallback used.")
        return baseline

    parsed = json.loads(raw)
    parsed["model_used"] = settings.gemini_model
    return AnalysisResult(**parsed)
