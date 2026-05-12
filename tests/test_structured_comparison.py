"""Tests for the new structured-comparison fields (#1, #4, #5).

Per CLAUDE.md, the analyzer owns the score; the LLM owns prose. These tests
exercise only the deterministic baseline path (no LLM).
"""
from app.analyzer import analyze_report, ReportContext


NFP_TEXT = (
    "Total nonfarm payroll employment increased by 150,000 in April. "
    "Employment continued to trend up in health care and government employment. "
    "The change in total nonfarm payroll employment for February was revised down by 35,000 "
    "and the change for March was revised down by 22,000. "
    "The number of persons employed part time for economic reasons increased by 42,000. "
    "Multiple jobholders also increased by 25,000 over the month. "
    "Government employment increased by 38,000. "
    "The labor force participation rate was little changed, and the household survey showed "
    "civilian employment was roughly flat."
)


def _ctx(headline: str = "Payrolls jump by 150k, crushing the 65k estimate") -> ReportContext:
    return ReportContext(
        source="BLS",
        report_type="Nonfarm Payrolls",
        release_date="2026-05-02",
        headline=headline,
        report_text=NFP_TEXT,
    )


def test_atomic_headline_claims_are_extracted():
    result = analyze_report(_ctx())
    kinds = {c.kind for c in result.headline_claims}
    assert {"subject", "figure", "comparison", "tone"}.issubset(kinds), (
        f"expected subject/figure/comparison/tone claims, got {kinds}"
    )

    # The figure claim should match the release.
    figure = next(c for c in result.headline_claims if c.kind == "figure")
    assert figure.verdict == "match"
    assert "150,000" in figure.text or "150" in figure.text


def test_revision_omission_is_flagged_as_missing_context():
    # Headline says nothing about revisions but the release discloses them.
    result = analyze_report(_ctx())
    omissions = [c for c in result.headline_claims if c.id == "omission_revisions"]
    assert omissions, "should flag revision omission when headline doesn't mention them"
    assert omissions[0].verdict == "missing_context"


def test_composition_breaks_down_headline_number():
    result = analyze_report(_ctx())
    labels = [s.label for s in result.composition]
    assert any("Government" in l for l in labels), f"expected Government slice, got {labels}"
    assert any("Multiple jobholders" in l for l in labels), labels
    assert any("Part-time" in l for l in labels), labels
    # Slices should sum to roughly 100% with the residual filler.
    total = sum(s.share_pct for s in result.composition)
    assert 95 <= total <= 105, f"composition shares should sum to ~100, got {total}"


def test_revision_adjustment_is_structured():
    result = analyze_report(_ctx())
    assert result.revision_adjustment is not None
    r = result.revision_adjustment
    # 150,000 + (-57,000 from Feb -35k + Mar -22k) = 93,000
    assert "93" in r.adjusted_value, f"expected 93,000 net of revisions, got {r.adjusted_value}"
    assert r.direction == "negative"
    assert "Feb" in r.periods_revised or "Mar" in r.periods_revised


def test_llm_only_fields_are_none_without_api_key():
    # With no OPENAI_API_KEY in .env, tone / coverage_gaps / verdict_probability stay empty.
    result = analyze_report(_ctx())
    assert result.tone is None
    assert result.coverage_gaps == []
    assert result.verdict_probability is None
