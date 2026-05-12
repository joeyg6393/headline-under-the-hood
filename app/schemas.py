from __future__ import annotations

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    source: str = Field(min_length=2, examples=["BLS"])
    report_type: str = Field(min_length=2, examples=["Nonfarm Payrolls"])
    release_date: str = Field(min_length=4, examples=["2026-05-08"])
    headline: str = Field(min_length=10)
    report_text: str = Field(min_length=20)


class MetricFinding(BaseModel):
    key: str
    name: str
    value: str
    numeric_value: float | None = None
    unit: str | None = None
    prior_value: float | None = None
    delta: float | None = None
    direction: str = "neutral"
    source: str | None = None
    math: str | None = None
    interpretation: str


class ScoreComponent(BaseModel):
    label: str
    points: int
    math: str
    evidence: str
    direction: str = "neutral"


class Citation(BaseModel):
    label: str
    excerpt: str


# === New structured-comparison primitives ===========================

class HeadlineClaim(BaseModel):
    """A single atomic claim parsed out of the headline.

    The deterministic analyzer parses the headline into typed pieces (figure,
    comparison, tone, subject, timing). The LLM may refine verdicts/notes but
    the deterministic baseline always populates a usable starting set.
    """

    id: str
    kind: str  # figure | comparison | tone | subject | timing
    text: str
    value: str | None = None
    unit: str | None = None
    verdict: str = "unsupported"  # match | partial | contradicts | unsupported | missing_context
    citation_ref: str | None = None
    note: str | None = None


class CompositionSlice(BaseModel):
    """One slice of what the headline number is made of."""

    label: str
    share_pct: float = Field(ge=0, le=100)
    direction: str = "neutral"
    note: str | None = None


class RevisionAdjustment(BaseModel):
    """Headline number net of prior-period revisions."""

    headline_value: str
    revision_total: str
    adjusted_value: str
    periods_revised: list[str] = Field(default_factory=list)
    direction: str = "neutral"  # positive | negative | neutral
    note: str | None = None


class ToneAssessment(BaseModel):
    """Headline tone vs. data magnitude."""

    headline_intensity: float = Field(ge=0, le=1)
    data_intensity: float = Field(ge=0, le=1)
    gap: float  # signed: headline - data
    loaded_words: list[str] = Field(default_factory=list)
    note: str | None = None


class CoverageGap(BaseModel):
    """A topic the release emphasizes that the headline ignores or downplays."""

    topic: str
    release_emphasis_pct: float = Field(ge=0, le=100)
    in_headline: bool
    note: str | None = None


class VerdictProbability(BaseModel):
    """Bayesian framing of the verdict."""

    accurate_summary_p: float = Field(ge=0, le=1)
    ci_low: float = Field(ge=0, le=1)
    ci_high: float = Field(ge=0, le=1)
    components: dict[str, float] = Field(default_factory=dict)
    note: str | None = None


# === Top-level analysis result ======================================

class AnalysisResult(BaseModel):
    verdict: str
    summary: str
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    metrics: list[MetricFinding]
    score_components: list[ScoreComponent] = Field(default_factory=list)
    supporting_factors: list[str]
    contradicting_factors: list[str]
    caveats: list[str]
    citations: list[Citation]
    model_used: str
    # Deterministic-or-refined structured comparison fields
    headline_claims: list[HeadlineClaim] = Field(default_factory=list)
    composition: list[CompositionSlice] = Field(default_factory=list)
    revision_adjustment: RevisionAdjustment | None = None
    # LLM-only fields (None when no API key is configured)
    tone: ToneAssessment | None = None
    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    verdict_probability: VerdictProbability | None = None


class ReportResponse(BaseModel):
    id: int
    source: str
    report_type: str
    release_date: str
    headline: str
    raw_file_path: str
    status: str
    created_at: str
    updated_at: str
    analysis: AnalysisResult | None = None
