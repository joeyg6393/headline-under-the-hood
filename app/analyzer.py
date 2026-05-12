from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.schemas import (
    AnalysisResult,
    Citation,
    CompositionSlice,
    HeadlineClaim,
    MetricFinding,
    RevisionAdjustment,
    ScoreComponent,
)


@dataclass(frozen=True)
class ReportContext:
    source: str
    report_type: str
    release_date: str
    headline: str
    report_text: str


KEYWORD_RULES = {
    "part_time": {
        "patterns": ["part-time", "part time", "parttime"],
        "message": "The report mentions part-time work, which can weaken the quality of a headline jobs gain.",
    },
    "multiple_jobholders": {
        "patterns": ["multiple jobholders", "multiple job holders", "second jobs", "second job"],
        "message": "The report mentions multiple jobholding or second jobs, so payroll growth may overstate unique-worker strength.",
    },
    "revisions": {
        "patterns": ["revision", "revised", "revisions"],
        "message": "The report includes revisions, which can materially change the headline read.",
    },
    "labor_force": {
        "patterns": ["labor force", "participation rate", "labor force participation"],
        "message": "Labor-force participation is relevant to whether job growth reflects broadening employment.",
    },
    "household": {
        "patterns": ["household survey", "civilian employment", "employment level"],
        "message": "The household survey provides a useful cross-check against the payroll headline.",
    },
    "government": {
        "patterns": ["government employment", "public sector", "government jobs"],
        "message": "Government-job concentration can make private-sector momentum look weaker than the headline.",
    },
    "temporary": {
        "patterns": ["temporary help", "temporary services"],
        "message": "Temporary-help weakness can flag softer labor demand beneath the headline.",
    },
    "core_inflation": {
        "patterns": ["core cpi", "core pce", "core ppi", "excluding food and energy"],
        "message": "Core inflation strips out volatile food and energy and is often the cleaner trend signal.",
    },
    "shelter": {
        "patterns": ["shelter", "rent", "owners' equivalent rent"],
        "message": "Shelter costs can keep inflation sticky even when goods prices cool.",
    },
    "energy": {
        "patterns": ["energy", "gasoline"],
        "message": "Energy can move the headline inflation number without saying as much about the underlying trend.",
    },
    "control_group": {
        "patterns": ["control group", "excluding motor vehicles", "ex-autos", "ex autos"],
        "message": "Retail-sales control-group details are important for the consumer-spending read-through.",
    },
    "new_orders": {
        "patterns": ["new orders"],
        "message": "New orders are a forward-looking check on PMI headline strength.",
    },
    "claims": {
        "patterns": ["initial claims", "continuing claims", "four-week moving average"],
        "message": "Claims details can confirm whether labor-market stress is broadening or only weekly noise.",
    },
}


def analyze_report(context: ReportContext) -> AnalysisResult:
    baseline = _local_analysis(context)
    settings = get_settings()
    if settings.gemini_api_key:
        try:
            from app.gemini_analysis import analyze_with_gemini

            ai_result = analyze_with_gemini(context, baseline)
            # Score-first invariant: deterministic analyzer owns these.
            ai_result.score = baseline.score
            ai_result.metrics = baseline.metrics
            ai_result.score_components = baseline.score_components
            # Preserve baseline structured fields if the LLM left them empty.
            if not ai_result.headline_claims:
                ai_result.headline_claims = baseline.headline_claims
            if not ai_result.composition:
                ai_result.composition = baseline.composition
            if ai_result.revision_adjustment is None:
                ai_result.revision_adjustment = baseline.revision_adjustment
            return ai_result
        except Exception as exc:
            baseline.caveats.append(f"Gemini analysis failed, so local fallback was used: {exc}")
            return baseline
    return baseline


def _local_analysis(context: ReportContext) -> AnalysisResult:
    headline_jobs = _extract_jobs_number(context.headline)
    estimate_jobs = _extract_estimate_number(context.headline)
    report_jobs = _extract_jobs_number(context.report_text)
    headline_percent = _extract_percent_number(context.headline)
    estimate_percent = _extract_estimate_percent(context.headline)
    report_percent = _extract_percent_number(context.report_text)
    found_rules = _find_rules(context.report_text)
    citations = _make_citations(context.report_text, found_rules)

    metrics: list[MetricFinding] = []
    score_components: list[ScoreComponent] = []
    if headline_jobs is not None:
        metrics.append(
            MetricFinding(
                key="headline_payroll_claim",
                name="Headline payroll claim",
                value=f"{headline_jobs:,}",
                numeric_value=headline_jobs,
                unit="jobs",
                direction="neutral",
                interpretation="The headline centers on this jobs-added figure.",
            )
        )
    if estimate_jobs is not None:
        metrics.append(
            MetricFinding(
                key="consensus_estimate",
                name="Consensus estimate",
                value=f"{estimate_jobs:,}",
                numeric_value=estimate_jobs,
                unit="jobs",
                direction="neutral",
                interpretation="The reported estimate creates the headline surprise benchmark.",
            )
        )
    if report_jobs is not None:
        metrics.append(
            MetricFinding(
                key="reported_payroll_gain",
                name="First jobs figure found in report",
                value=f"{report_jobs:,}",
                numeric_value=report_jobs,
                unit="jobs",
                direction="supporting",
                source="Report text",
                interpretation="This is the first payroll-like number detected in the report text.",
            )
        )
    if headline_percent is not None:
        metrics.append(
            MetricFinding(
                key="headline_release_read",
                name="Headline release read",
                value=f"{headline_percent:g}%",
                numeric_value=headline_percent,
                unit="percent",
                direction="neutral",
                interpretation="The headline centers on this percentage move or index level.",
            )
        )
    if estimate_percent is not None:
        metrics.append(
            MetricFinding(
                key="consensus_percent_estimate",
                name="Consensus estimate",
                value=f"{estimate_percent:g}%",
                numeric_value=estimate_percent,
                unit="percent",
                direction="neutral",
                interpretation="The estimate creates the benchmark for the headline surprise.",
            )
        )
    if report_percent is not None:
        metrics.append(
            MetricFinding(
                key="reported_release_read",
                name="First percentage found in report",
                value=f"{report_percent:g}%",
                numeric_value=report_percent,
                unit="percent",
                direction="supporting",
                source="Report text",
                interpretation="This is the first percentage or index-level figure detected in the report text.",
            )
        )

    supporting: list[str] = []
    contradicting: list[str] = []
    caveats: list[str] = []
    score = 60

    if report_jobs is not None and headline_jobs is not None:
        if report_jobs >= headline_jobs * 0.9:
            supporting.append(
                f"The main payroll figure supports the headline: {report_jobs:,} reported jobs vs {headline_jobs:,} in the headline."
            )
        else:
            contradicting.append(
                f"The report jobs figure is materially below the headline: {report_jobs:,} detected vs {headline_jobs:,} claimed."
            )
            score_components.append(
                ScoreComponent(
                    label="Headline/report mismatch",
                    points=-15,
                    math=f"{report_jobs:,} reported - {headline_jobs:,} headline = {report_jobs - headline_jobs:,}",
                    evidence="The first payroll-like number detected in the report was below the headline claim.",
                    direction="negative",
                )
            )
            score -= 15

    if headline_jobs is not None and estimate_jobs is not None:
        surprise = headline_jobs - estimate_jobs
        surprise_points = max(-30, min(30, round(surprise / 3_500)))
        score += surprise_points
        direction = "positive" if surprise_points >= 0 else "negative"
        text = "beat" if surprise >= 0 else "missed"
        score_components.append(
            ScoreComponent(
                label="Headline surprise",
                points=surprise_points,
                math=f"{headline_jobs:,} actual - {estimate_jobs:,} estimate = {surprise:,}",
                evidence=f"The headline {text} the estimate by {abs(surprise):,} jobs.",
                direction=direction,
            )
        )
        if surprise >= 0:
            supporting.append(f"The headline beat is real on the surface: {headline_jobs:,} vs {estimate_jobs:,}, a +{surprise:,} surprise.")
        else:
            contradicting.append(f"The headline missed expectations: {headline_jobs:,} vs {estimate_jobs:,}, a {surprise:,} surprise.")

    if report_percent is not None and headline_percent is not None:
        gap = report_percent - headline_percent
        if abs(gap) <= 0.05:
            supporting.append(
                f"The main reported percentage supports the headline: {report_percent:g}% in the report vs {headline_percent:g}% in the headline."
            )
        else:
            contradicting.append(
                f"The first reported percentage differs from the headline: {report_percent:g}% detected vs {headline_percent:g}% claimed."
            )
            score_components.append(
                ScoreComponent(
                    label="Headline/report percentage gap",
                    points=-12,
                    math=f"{report_percent:g}% reported - {headline_percent:g}% headline = {gap:+.1f} pp",
                    evidence="The first percentage detected in the report did not match the headline percentage.",
                    direction="negative",
                )
            )
            score -= 12

    if headline_percent is not None and estimate_percent is not None:
        surprise = headline_percent - estimate_percent
        cue = _headline_surprise_cue(context.headline)
        matches_headline = (surprise >= 0 and cue >= 0) or (surprise <= 0 and cue <= 0)
        points = min(22, max(3, round(abs(surprise) * 55)))
        if cue == 0:
            points = max(3, round(points / 2))
            direction = "neutral"
            evidence = f"The headline includes the estimate gap: {headline_percent:g}% actual vs {estimate_percent:g}% expected."
        elif matches_headline:
            direction = "positive"
            evidence = f"The percentage surprise supports the headline framing: {headline_percent:g}% actual vs {estimate_percent:g}% expected."
        else:
            points = -points
            direction = "negative"
            evidence = f"The percentage surprise cuts against the headline framing: {headline_percent:g}% actual vs {estimate_percent:g}% expected."
        score += points
        score_components.append(
            ScoreComponent(
                label="Estimate surprise",
                points=points,
                math=f"{headline_percent:g}% actual - {estimate_percent:g}% estimate = {surprise:+.1f} pp",
                evidence=evidence,
                direction=direction,
            )
        )
        if points >= 0:
            supporting.append(evidence)
        else:
            contradicting.append(evidence)

    for metric in _extract_percentage_metrics(context.report_text):
        if not any(existing.key == metric.key for existing in metrics):
            metrics.append(metric)

    revision_values = _extract_revision_values(context.report_text)
    if revision_values:
        total_revision = sum(revision_values)
        points = -min(15, round(abs(total_revision) / 6_000)) if total_revision < 0 else min(10, round(total_revision / 6_000))
        score += points
        metrics.append(
            MetricFinding(
                key="prior_revisions",
                name="Prior-month revisions",
                value=f"{total_revision:+,}",
                numeric_value=total_revision,
                unit="jobs",
                delta=total_revision,
                direction="contradicting" if total_revision < 0 else "supporting",
                source="Report text",
                math=_sum_math(revision_values),
                interpretation="Prior revisions change the quality of the headline month by changing the recent trend.",
            )
        )
        score_components.append(
            ScoreComponent(
                label="Prior revisions",
                points=points,
                math=f"{_sum_math(revision_values)} = {total_revision:+,}",
                evidence=f"Prior months were revised {'down' if total_revision < 0 else 'up'} by {abs(total_revision):,} jobs in total.",
                direction="negative" if total_revision < 0 else "positive",
            )
        )
        if total_revision < 0:
            contradicting.append(f"Prior revisions subtract {abs(total_revision):,} jobs from the recent trend ({_sum_math(revision_values)}).")
        else:
            supporting.append(f"Prior revisions add {total_revision:,} jobs to the recent trend ({_sum_math(revision_values)}).")

        if headline_jobs is not None:
            net_adjusted = headline_jobs + total_revision
            metrics.append(
                MetricFinding(
                    key="revision_adjusted_headline",
                    name="Revision-adjusted headline read",
                    value=f"{net_adjusted:,}",
                    numeric_value=net_adjusted,
                    unit="jobs",
                    delta=total_revision,
                    direction="contradicting" if total_revision < 0 else "supporting",
                    math=f"{headline_jobs:,} headline + {total_revision:+,} revisions = {net_adjusted:,}",
                    interpretation="This rough read combines the headline month with prior revisions.",
                )
            )

    metric_specs = [
        (
            "multiple_jobholders",
            "Multiple jobholders",
            ["multiple jobholders", "multiple job holders", "second jobs", "second job"],
            "A rise in multiple jobholding can mean payroll growth overstates unique-worker strength.",
            -6,
            5_000,
        ),
        (
            "part_time_economic",
            "Part-time for economic reasons",
            ["part time for economic reasons", "part-time for economic reasons", "part time", "part-time"],
            "A rise in involuntary part-time work weakens the quality of a payroll gain.",
            -8,
            6_000,
        ),
        (
            "household_employment",
            "Household employment",
            ["household survey", "civilian employment", "employment level"],
            "The household survey is a cross-check against the establishment payroll number.",
            -6,
            10_000,
        ),
        (
            "government_employment",
            "Government employment",
            ["government employment", "government jobs", "public sector"],
            "A high government-job share can make private-sector momentum look weaker than the headline.",
            -3,
            8_000,
        ),
        (
            "temporary_help",
            "Temporary help",
            ["temporary help", "temporary services"],
            "Temporary-help weakness can flag softer forward labor demand.",
            -5,
            3_000,
        ),
    ]

    extracted_metric_keys: set[str] = set()
    for key, name, keywords, interpretation, max_penalty, divisor in metric_specs:
        delta = _extract_delta_near_keywords(context.report_text, keywords)
        flat = _mentions_flat_near_keywords(context.report_text, keywords)
        if delta is None and not flat:
            continue

        extracted_metric_keys.add(key)
        direction = _metric_direction(key, delta, flat)
        value = "flat" if delta is None else f"{delta:+,}"
        math = "described as roughly flat" if delta is None else f"reported month change = {delta:+,}"
        metrics.append(
            MetricFinding(
                key=key,
                name=name,
                value=value,
                numeric_value=delta,
                unit="persons" if key != "government_employment" else "jobs",
                delta=delta,
                direction=direction,
                source="Report text",
                math=math,
                interpretation=interpretation,
            )
        )

        points = _points_for_metric(key, delta, flat, max_penalty, divisor)
        if points:
            score += points
            evidence = _metric_evidence(name, delta, flat, interpretation)
            score_components.append(
                ScoreComponent(
                    label=name,
                    points=points,
                    math=math,
                    evidence=evidence,
                    direction="negative" if points < 0 else "positive",
                )
            )
            if points < 0:
                contradicting.append(evidence)
            else:
                supporting.append(evidence)

    if report_jobs and _metric_value(metrics, "government_employment") is not None:
        gov_delta = _metric_value(metrics, "government_employment")
        if gov_delta and gov_delta > 0:
            share = gov_delta / report_jobs
            metrics.append(
                MetricFinding(
                    key="government_share",
                    name="Government share of payroll gain",
                    value=f"{share:.1%}",
                    numeric_value=share,
                    unit="share",
                    direction="contradicting" if share >= 0.25 else "neutral",
                    math=f"{gov_delta:,} government jobs / {report_jobs:,} total payroll jobs = {share:.1%}",
                    interpretation="This estimates how much of the payroll gain came from government employment.",
                )
            )
            if share >= 0.25:
                points = -min(5, round(share * 18))
                score += points
                evidence = f"Government jobs account for {share:.1%} of the detected payroll gain ({gov_delta:,} of {report_jobs:,})."
                score_components.append(
                    ScoreComponent(
                        label="Government-job concentration",
                        points=points,
                        math=f"{gov_delta:,} / {report_jobs:,} = {share:.1%}",
                        evidence=evidence,
                        direction="negative",
                    )
                )
                contradicting.append(evidence)

    for key, rule in found_rules.items():
        if key in extracted_metric_keys:
            continue
        message = rule["message"]
        if key in {"part_time", "multiple_jobholders", "revisions", "government", "temporary"}:
            contradicting.append(message)
        else:
            caveats.append(message)

    if not contradicting:
        supporting.append("The local analyzer did not detect obvious quality caveats in the supplied text.")

    caveats.append("This MVP local analyzer uses keyword and number heuristics; model-backed analysis should be used for production.")

    score = max(0, min(100, score))

    verdict = _verdict(score)
    summary = _summary(verdict, supporting, contradicting, caveats)

    return AnalysisResult(
        verdict=verdict,
        summary=summary,
        score=score,
        confidence=0.58 if found_rules else 0.45,
        metrics=metrics,
        score_components=score_components,
        supporting_factors=supporting[:5],
        contradicting_factors=contradicting[:6],
        caveats=caveats[:6],
        citations=citations[:5],
        model_used="local-heuristic-v0",
        headline_claims=_extract_headline_claims(context, metrics),
        composition=_compute_composition(metrics, context.report_type),
        revision_adjustment=_compute_revision_adjustment(metrics, context.report_text),
    )


def _extract_jobs_number(text: str) -> int | None:
    patterns = [
        r"([+-]?\d+(?:,\d{3})?)\s*(?:k|K)\b",
        r"([+-]?\d+(?:,\d{3})?)\s+jobs",
        r"payrolls?\s+(?:increased|rose|added|grew)\s+by\s+([+-]?\d+(?:,\d{3})?)",
        r"employment\s+(?:increased|rose|added|grew)\s+by\s+([+-]?\d+(?:,\d{3})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).replace(",", "")
            number = int(raw)
            if "k" in match.group(0).lower():
                return number * 1000
            return number
    return None


def _extract_estimate_number(text: str) -> int | None:
    patterns = [
        r"(?:vs|versus)\.?\s+(?:an?\s+)?([+-]?\d+(?:,\d{3})?)(?:\s*k)?\s+(?:estimate|est\.?|expected|consensus)",
        r"([+-]?\d+(?:,\d{3})?)(?:\s*k)?\s+(?:estimate|est\.?|expected|consensus)",
        r"(?:estimate|est\.?|expected|consensus)\s+(?:of\s+)?([+-]?\d+(?:,\d{3})?)(?:\s*k)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_number(match.group(1), "k" in match.group(0).lower())
    return None


def _extract_percent_number(text: str) -> float | None:
    patterns = [
        r"([+-]?\d+(?:\.\d+)?)\s*%",
        r"([+-]?\d+(?:\.\d+)?)\s+percent",
        r"(?:registered|at)\s+([+-]?\d+(?:\.\d+)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_estimate_percent(text: str) -> float | None:
    patterns = [
        r"(?:vs|versus)\.?\s+(?:an?\s+)?([+-]?\d+(?:\.\d+)?)\s*(?:%|percent)?\s+(?:estimate|est\.?|expected|consensus)",
        r"([+-]?\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:estimate|est\.?|expected|consensus)",
        r"(?:estimate|est\.?|expected|consensus)\s+(?:of\s+)?([+-]?\d+(?:\.\d+)?)\s*(?:%|percent)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_percentage_metrics(text: str) -> list[MetricFinding]:
    specs = [
        (
            "core_inflation",
            "Core inflation",
            ["core cpi", "core pce", "core ppi", "excluding food and energy"],
            "Core inflation is a cleaner read on the underlying price trend.",
        ),
        (
            "shelter_costs",
            "Shelter costs",
            ["shelter", "rent", "owners' equivalent rent"],
            "Shelter is a large, sticky component in inflation reports.",
        ),
        (
            "energy_prices",
            "Energy prices",
            ["energy", "gasoline"],
            "Energy can swing headline inflation without moving the core trend.",
        ),
        (
            "control_group",
            "Retail control group",
            ["control group"],
            "The control group is the retail-sales slice that maps most directly into consumer spending.",
        ),
        (
            "new_orders",
            "New orders",
            ["new orders"],
            "New orders are a forward-looking PMI demand signal.",
        ),
        (
            "employment_index",
            "Employment index",
            ["employment index"],
            "The employment index cross-checks whether activity data are flowing into hiring demand.",
        ),
        (
            "price_index",
            "Prices index",
            ["prices index", "price index"],
            "Price sub-indexes show whether input-cost pressure is easing or building.",
        ),
    ]
    metrics: list[MetricFinding] = []
    for key, name, keywords, interpretation in specs:
        value = _extract_percent_near_keywords(text, keywords)
        if value is None:
            continue
        metrics.append(
            MetricFinding(
                key=key,
                name=name,
                value=f"{value:g}%",
                numeric_value=value,
                unit="percent",
                direction="neutral",
                source="Report text",
                math=f"reported value = {value:g}%",
                interpretation=interpretation,
            )
        )
    return metrics


def _extract_percent_near_keywords(text: str, keywords: list[str]) -> float | None:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in keywords):
            continue
        match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(?:%|percent)?", sentence, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _headline_surprise_cue(headline: str) -> int:
    lowered = headline.lower()
    positive_terms = ["hot", "heats", "above", "beats", "strong", "accelerates", "surges"]
    negative_terms = ["cool", "below", "miss", "falls", "slows", "weak", "contracts", "soft"]
    if any(term in lowered for term in positive_terms):
        return 1
    if any(term in lowered for term in negative_terms):
        return -1
    return 0


def _extract_revision_values(text: str) -> list[int]:
    values: list[int] = []
    patterns = [
        r"revised\s+(down|lower|up|higher)\s+by\s+([+-]?\d+(?:,\d{3})?)(?:\s*k)?",
        r"revision[s]?\s+(?:of|totaled|were)\s+([+-]?\d+(?:,\d{3})?)(?:\s*k)?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if len(match.groups()) == 2 and match.group(1).lower() in {"down", "lower", "up", "higher"}:
                sign = -1 if match.group(1).lower() in {"down", "lower"} else 1
                values.append(sign * _parse_number(match.group(2), "k" in match.group(0).lower()))
            else:
                values.append(_parse_number(match.group(1), "k" in match.group(0).lower()))
    return values


def _extract_delta_near_keywords(text: str, keywords: list[str]) -> int | None:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in keywords):
            continue
        patterns = [
            r"(?:increased|rose|added|grew|up)\s+(?:by\s+)?([+-]?\d+(?:,\d{3})?)(?:\s*k)?",
            r"(?:decreased|fell|declined|dropped|down)\s+(?:by\s+)?([+-]?\d+(?:,\d{3})?)(?:\s*k)?",
            r"([+-]\d+(?:,\d{3})?)(?:\s*k)?",
        ]
        for pattern in patterns:
            match = re.search(pattern, sentence, flags=re.IGNORECASE)
            if not match:
                continue
            value = _parse_number(match.group(1), "k" in match.group(0).lower())
            if re.search(r"decreased|fell|declined|dropped|down", match.group(0), flags=re.IGNORECASE):
                value = -abs(value)
            return value
    return None


def _mentions_flat_near_keywords(text: str, keywords: list[str]) -> bool:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords) and any(term in lowered for term in ["flat", "little changed", "roughly unchanged"]):
            return True
    return False


def _parse_number(raw: str, is_thousands: bool) -> int:
    value = int(raw.replace(",", ""))
    return value * 1_000 if is_thousands else value


def _sum_math(values: list[int]) -> str:
    return " + ".join(f"{value:+,}" for value in values)


def _metric_direction(key: str, delta: int | None, flat: bool) -> str:
    if flat and key == "household_employment":
        return "contradicting"
    if delta is None:
        return "neutral"
    if key in {"multiple_jobholders", "part_time_economic", "government_employment"}:
        return "contradicting" if delta > 0 else "supporting"
    if key in {"household_employment", "temporary_help"}:
        return "supporting" if delta > 0 else "contradicting"
    return "neutral"


def _points_for_metric(key: str, delta: int | None, flat: bool, max_penalty: int, divisor: int) -> int:
    if flat and key == "household_employment":
        return max_penalty
    if delta is None:
        return 0
    magnitude_points = min(abs(max_penalty), max(1, round(abs(delta) / divisor)))
    if key in {"multiple_jobholders", "part_time_economic", "government_employment"}:
        return -magnitude_points if delta > 0 else min(6, magnitude_points)
    if key in {"household_employment", "temporary_help"}:
        return min(8, magnitude_points) if delta > 0 else -magnitude_points
    return 0


def _metric_evidence(name: str, delta: int | None, flat: bool, interpretation: str) -> str:
    if flat and delta is None:
        return f"{name} was described as roughly flat. {interpretation}"
    assert delta is not None
    verb = "increased" if delta > 0 else "decreased"
    return f"{name} {verb} by {abs(delta):,}. {interpretation}"


def _metric_value(metrics: list[MetricFinding], key: str) -> float | None:
    for metric in metrics:
        if metric.key == key:
            return metric.numeric_value
    return None


def _find_rules(text: str) -> dict[str, dict[str, object]]:
    lowered = text.lower()
    found: dict[str, dict[str, object]] = {}
    for key, rule in KEYWORD_RULES.items():
        if any(pattern in lowered for pattern in rule["patterns"]):
            found[key] = rule
    return found


def _make_citations(text: str, found_rules: dict[str, dict[str, object]]) -> list[Citation]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    citations: list[Citation] = []
    for key, rule in found_rules.items():
        patterns = rule["patterns"]
        for sentence in sentences:
            if any(pattern in sentence.lower() for pattern in patterns):
                citations.append(Citation(label=key.replace("_", " ").title(), excerpt=sentence[:280]))
                break
    if not citations and sentences:
        citations.append(Citation(label="Report excerpt", excerpt=sentences[0][:280]))
    return citations



# === Structured-comparison helpers ==================================

_TONE_WORDS = {
    "crushing": 0.85, "crushes": 0.85, "shocking": 0.85, "shockingly": 0.85,
    "soaring": 0.85, "soars": 0.85, "plunging": 0.85, "plunges": 0.85,
    "surging": 0.8, "surges": 0.8, "explosive": 0.85, "explodes": 0.85,
    "blowout": 0.85, "skyrocket": 0.85, "skyrockets": 0.85,
    "jumping": 0.7, "jumps": 0.7, "jump": 0.7, "leaping": 0.7, "leaps": 0.7,
    "slumping": 0.75, "slumps": 0.75, "tumbling": 0.75, "tumbles": 0.75,
    "robust": 0.7, "strong": 0.6, "stronger": 0.6, "weak": 0.6, "weaker": 0.6,
    "cooling": 0.55, "cools": 0.55, "easing": 0.5, "eases": 0.5,
    "modest": 0.4, "modestly": 0.4, "tepid": 0.55, "softens": 0.55, "softening": 0.55,
    "beats": 0.6, "beating": 0.6, "miss": 0.6, "misses": 0.6, "missed": 0.6,
    "above": 0.4, "below": 0.4, "near": 0.3,
}


def _extract_headline_claims(
    context: ReportContext, metrics: list[MetricFinding]
) -> list[HeadlineClaim]:
    """Parse the headline into atomic claims and label each with a verdict.

    Verdict semantics:
        match            - confirmed by a metric extracted from the release
        partial          - direction matches but magnitude differs
        contradicts      - directly contradicted by a metric in the release
        unsupported      - no metric found that bears on this claim
        missing_context  - claim is true but release qualifies it (e.g., revisions)
    """
    claims: list[HeadlineClaim] = []
    headline = context.headline

    by_key = {m.key: m for m in metrics}

    # ------- subject claim (the noun the headline is about)
    subject = _detect_subject(headline)
    if subject:
        claims.append(
            HeadlineClaim(
                id="subject",
                kind="subject",
                text=subject,
                value=subject,
                verdict="match",
                note="Subject of the headline matches the report type.",
            )
        )

    # ------- figure claims
    headline_jobs = _extract_jobs_number(headline)
    headline_pct = _extract_percent_number(headline)
    if headline_jobs is not None:
        reported = by_key.get("reported_payroll_gain") or by_key.get("reported_release_read")
        verdict, note = _compare_figure(headline_jobs, reported.numeric_value if reported else None, "jobs")
        claims.append(
            HeadlineClaim(
                id="figure_jobs",
                kind="figure",
                text=f"{headline_jobs:,} jobs",
                value=f"{headline_jobs:,}",
                unit="jobs",
                verdict=verdict,
                citation_ref="reported_payroll_gain" if reported else None,
                note=note,
            )
        )
    elif headline_pct is not None:
        reported = by_key.get("reported_release_read")
        verdict, note = _compare_figure(headline_pct, reported.numeric_value if reported else None, "percent")
        claims.append(
            HeadlineClaim(
                id="figure_pct",
                kind="figure",
                text=f"{headline_pct:g}%",
                value=f"{headline_pct:g}%",
                unit="percent",
                verdict=verdict,
                citation_ref="reported_release_read" if reported else None,
                note=note,
            )
        )

    # ------- comparison claims (vs estimate)
    estimate_jobs = _extract_estimate_number(headline)
    estimate_pct = _extract_estimate_percent(headline)
    if estimate_jobs is not None and headline_jobs is not None:
        delta = headline_jobs - estimate_jobs
        verdict = "match" if delta >= 0 else "contradicts"
        claims.append(
            HeadlineClaim(
                id="cmp_estimate_jobs",
                kind="comparison",
                text=f"{'beat' if delta >= 0 else 'missed'} estimate by {abs(delta):,}",
                value=f"{delta:+,}",
                unit="jobs",
                verdict=verdict,
                note=f"Headline {headline_jobs:,} vs consensus {estimate_jobs:,}.",
            )
        )
    elif estimate_pct is not None and headline_pct is not None:
        delta = headline_pct - estimate_pct
        verdict = "match" if abs(delta) < 0.05 else "partial"
        claims.append(
            HeadlineClaim(
                id="cmp_estimate_pct",
                kind="comparison",
                text=f"{'above' if delta > 0 else 'below' if delta < 0 else 'in line with'} estimate",
                value=f"{delta:+.2g}pp",
                unit="percentage_points",
                verdict=verdict,
                note=f"Headline {headline_pct:g}% vs consensus {estimate_pct:g}%.",
            )
        )

    # ------- tone claim
    tone_word, intensity = _detect_tone(headline)
    if tone_word:
        # Check if the magnitude justifies the tone. Use surprise size if available.
        magnitude = None
        if headline_jobs is not None and estimate_jobs is not None:
            magnitude = abs(headline_jobs - estimate_jobs) / max(50_000, 1)  # crude scale
        elif headline_pct is not None and estimate_pct is not None:
            magnitude = abs(headline_pct - estimate_pct) / 0.5  # crude scale
        verdict = "missing_context"
        note = f"Headline uses '{tone_word}' (intensity {intensity:.2f})."
        if magnitude is not None:
            note += f" Surprise magnitude {magnitude:.2f} of typical range."
            if intensity - magnitude > 0.3:
                verdict = "contradicts"
                note += " Tone exceeds the data."
            elif intensity <= magnitude + 0.1:
                verdict = "match"
                note += " Tone tracks the data."
        claims.append(
            HeadlineClaim(
                id="tone",
                kind="tone",
                text=tone_word,
                value=f"{intensity:.2f}",
                verdict=verdict,
                note=note,
            )
        )

    # ------- revision-omission claim (if revisions exist but headline doesn't mention them)
    if "prior_revisions" in by_key:
        rev = by_key["prior_revisions"]
        rev_amt = rev.numeric_value or 0
        mentions = bool(re.search(r"revis", headline, re.IGNORECASE))
        if not mentions and abs(rev_amt) > 5_000:
            claims.append(
                HeadlineClaim(
                    id="omission_revisions",
                    kind="comparison",
                    text="prior-month revisions",
                    value=f"{rev_amt:+,}",
                    unit="jobs",
                    verdict="missing_context",
                    citation_ref="prior_revisions",
                    note=f"Release discloses {rev_amt:+,} in prior revisions; headline does not mention them.",
                )
            )

    return claims


def _detect_subject(headline: str) -> str | None:
    lowered = headline.lower()
    if "payroll" in lowered or "jobs" in lowered or "employment" in lowered:
        return "payrolls"
    if "cpi" in lowered or "inflation" in lowered:
        return "inflation"
    if "pce" in lowered:
        return "PCE"
    if "gdp" in lowered:
        return "GDP"
    if "retail" in lowered:
        return "retail sales"
    if "ism" in lowered or "pmi" in lowered:
        return "activity index"
    if "fed" in lowered or "rate" in lowered:
        return "rates"
    return None


def _detect_tone(headline: str) -> tuple[str | None, float]:
    lowered = headline.lower()
    best_word = None
    best_intensity = 0.0
    for word, intensity in _TONE_WORDS.items():
        if re.search(r"\b" + re.escape(word) + r"\b", lowered):
            if intensity > best_intensity:
                best_word = word
                best_intensity = intensity
    return best_word, best_intensity


def _compare_figure(
    headline_value: float, reported_value: float | None, unit: str
) -> tuple[str, str]:
    if reported_value is None:
        return ("unsupported", f"No matching figure detected in the release for the headline {unit} value.")
    if abs(headline_value - reported_value) < max(1, headline_value * 0.02):
        return (
            "match",
            f"Headline figure {headline_value:g} matches release figure {reported_value:g}.",
        )
    if (headline_value > 0) == (reported_value > 0) and abs(headline_value - reported_value) < headline_value * 0.15:
        return (
            "partial",
            f"Direction matches but magnitudes differ: headline {headline_value:g} vs release {reported_value:g}.",
        )
    return (
        "contradicts",
        f"Release figure ({reported_value:g}) does not back the headline ({headline_value:g}).",
    )


def _compute_composition(
    metrics: list[MetricFinding], report_type: str
) -> list[CompositionSlice]:
    """Derive a composition stack of what the headline number is made of.

    For NFP-like reports we have government_employment, multiple_jobholders,
    part_time_economic, etc. For inflation reports we have shelter_costs,
    energy_prices, core_inflation. We compute share-of-total where the
    deterministic analyzer extracted enough signal; otherwise return [].
    """
    by_key = {m.key: m for m in metrics}
    slices: list[CompositionSlice] = []

    # --- Employment (NFP) composition
    total = by_key.get("reported_payroll_gain")
    if total and total.numeric_value:
        total_v = total.numeric_value
        components = [
            ("government_employment", "Government", "negative"),
            ("multiple_jobholders", "Multiple jobholders", "negative"),
            ("part_time_economic", "Part-time (econ. reasons)", "negative"),
            ("temporary_help", "Temporary help", "neutral"),
        ]
        accounted = 0.0
        for key, label, dir_default in components:
            m = by_key.get(key)
            if m and m.numeric_value is not None:
                share = abs(m.numeric_value) / total_v if total_v else 0
                if share <= 0.001:
                    continue
                share_pct = round(min(share, 1.0) * 100, 1)
                accounted += share_pct
                slices.append(
                    CompositionSlice(
                        label=label,
                        share_pct=share_pct,
                        direction=m.direction or dir_default,
                        note=m.math,
                    )
                )
        if slices:
            other = max(0.0, round(100.0 - accounted, 1))
            if other > 1:
                slices.append(
                    CompositionSlice(
                        label="Private-sector / other",
                        share_pct=other,
                        direction="positive",
                        note="Residual after the disclosed sub-components.",
                    )
                )

    # --- Inflation composition (CPI/PCE)
    if not slices:
        cpi_components = [
            ("shelter_costs", "Shelter", "negative"),
            ("energy_prices", "Energy", "neutral"),
            ("core_inflation", "Core (ex food/energy)", "neutral"),
        ]
        any_pct = [by_key.get(k) for k, _, _ in cpi_components if by_key.get(k)]
        if any_pct:
            # Use percentage values as relative weights, not true contributions.
            values = [(label, abs(by_key[k].numeric_value or 0), dir_default)
                      for k, label, dir_default in cpi_components if by_key.get(k)]
            total_v = sum(v for _, v, _ in values) or 1
            for label, v, dir_default in values:
                share_pct = round((v / total_v) * 100, 1)
                slices.append(
                    CompositionSlice(
                        label=label,
                        share_pct=share_pct,
                        direction=dir_default,
                        note=f"Reported value contribution proxied by relative magnitude.",
                    )
                )

    return slices


def _compute_revision_adjustment(
    metrics: list[MetricFinding],
    report_text: str = "",
) -> RevisionAdjustment | None:
    by_key = {m.key: m for m in metrics}
    headline = by_key.get("headline_payroll_claim")
    revision = by_key.get("prior_revisions")
    adjusted = by_key.get("revision_adjusted_headline")
    if not (headline and revision and adjusted):
        return None
    rev_amt = revision.numeric_value or 0
    direction = "negative" if rev_amt < 0 else "positive" if rev_amt > 0 else "neutral"
    return RevisionAdjustment(
        headline_value=headline.value,
        revision_total=revision.value,
        adjusted_value=adjusted.value,
        periods_revised=_extract_revision_periods(
            (revision.math or "") + " " + report_text
        ),
        direction=direction,
        note=adjusted.interpretation,
    )


def _extract_revision_periods(text: str) -> list[str]:
    """Pull month names out of sentences that talk about revisions."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    months: list[str] = []
    for sentence in sentences:
        if not re.search(r"revis", sentence, flags=re.IGNORECASE):
            continue
        for m in re.findall(
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b",
            sentence,
        ):
            label = m.capitalize()
            if label not in months:
                months.append(label)
    return months[:6]


def _verdict(score: int) -> str:
    if score >= 75:
        return "Headline mostly supported"
    if score >= 45:
        return "Headline directionally right, but quality is mixed"
    return "Headline likely overstates the report"


def _summary(verdict: str, supporting: list[str], contradicting: list[str], caveats: list[str]) -> str:
    details = contradicting or caveats or supporting
    if not details:
        return verdict
    return f"{verdict}. {details[0]}"
