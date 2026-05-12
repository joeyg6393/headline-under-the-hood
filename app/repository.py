from __future__ import annotations

import re
from typing import Any

from app.db import connect, decode, encode, row_to_dict, utc_now
from app.schemas import AnalysisResult, ReportResponse


def create_report(
    *,
    source: str,
    report_type: str,
    release_date: str,
    headline: str,
    raw_file_path: str,
) -> int:
    now = utc_now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reports (
                source, report_type, release_date, headline, raw_file_path,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source, report_type, release_date, headline, raw_file_path, "pending", now, now),
        )
        return int(cursor.lastrowid)


def find_report_id(*, source: str, report_type: str, release_date: str, headline: str) -> int | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM reports
            WHERE source = ? AND report_type = ? AND release_date = ? AND headline = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source, report_type, release_date, headline),
        ).fetchone()
    return int(row["id"]) if row else None


def update_report_status(report_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
            (status, utc_now(), report_id),
        )


def save_analysis(report_id: int, analysis: AnalysisResult) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO analyses (
                report_id, verdict, summary, score, confidence, metrics_json,
                score_components_json, supporting_factors_json, contradicting_factors_json,
                caveats_json, citations_json, model_used, created_at,
                headline_claims_json, composition_json, revision_adjustment_json,
                tone_json, coverage_gaps_json, verdict_probability_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                verdict = excluded.verdict,
                summary = excluded.summary,
                score = excluded.score,
                confidence = excluded.confidence,
                metrics_json = excluded.metrics_json,
                score_components_json = excluded.score_components_json,
                supporting_factors_json = excluded.supporting_factors_json,
                contradicting_factors_json = excluded.contradicting_factors_json,
                caveats_json = excluded.caveats_json,
                citations_json = excluded.citations_json,
                model_used = excluded.model_used,
                created_at = excluded.created_at,
                headline_claims_json = excluded.headline_claims_json,
                composition_json = excluded.composition_json,
                revision_adjustment_json = excluded.revision_adjustment_json,
                tone_json = excluded.tone_json,
                coverage_gaps_json = excluded.coverage_gaps_json,
                verdict_probability_json = excluded.verdict_probability_json
            """,
            (
                report_id,
                analysis.verdict,
                analysis.summary,
                analysis.score,
                analysis.confidence,
                encode([item.model_dump() for item in analysis.metrics]),
                encode([item.model_dump() for item in analysis.score_components]),
                encode(analysis.supporting_factors),
                encode(analysis.contradicting_factors),
                encode(analysis.caveats),
                encode([item.model_dump() for item in analysis.citations]),
                analysis.model_used,
                utc_now(),
                encode([item.model_dump() for item in analysis.headline_claims]),
                encode([item.model_dump() for item in analysis.composition]),
                encode(analysis.revision_adjustment.model_dump()) if analysis.revision_adjustment else None,
                encode(analysis.tone.model_dump()) if analysis.tone else None,
                encode([item.model_dump() for item in analysis.coverage_gaps]),
                encode(analysis.verdict_probability.model_dump()) if analysis.verdict_probability else None,
            ),
        )
        conn.execute("DELETE FROM report_metrics WHERE report_id = ?", (report_id,))
        conn.execute("DELETE FROM score_components WHERE report_id = ?", (report_id,))
        for metric in analysis.metrics:
            conn.execute(
                """
                INSERT INTO report_metrics (
                    report_id, metric_key, name, value, numeric_value, unit, prior_value,
                    delta, direction, source, math, interpretation, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    metric.key,
                    metric.name,
                    metric.value,
                    metric.numeric_value,
                    metric.unit,
                    metric.prior_value,
                    metric.delta,
                    metric.direction,
                    metric.source,
                    metric.math,
                    metric.interpretation,
                    utc_now(),
                ),
            )
        for component in analysis.score_components:
            conn.execute(
                """
                INSERT INTO score_components (
                    report_id, label, points, math, evidence, direction, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    component.label,
                    component.points,
                    component.math,
                    component.evidence,
                    component.direction,
                    utc_now(),
                ),
            )
    update_report_status(report_id, "complete")


def get_report(report_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        report = row_to_dict(conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone())
        if report is None:
            return None
        analysis = row_to_dict(conn.execute("SELECT * FROM analyses WHERE report_id = ?", (report_id,)).fetchone())
        report["analysis"] = _analysis_from_row(analysis) if analysis else None
        return report


def list_reports() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()
    return [get_report(int(row["id"])) for row in rows if row is not None]


def get_report_response(report_id: int) -> ReportResponse | None:
    report = get_report(report_id)
    if report is None:
        return None
    return ReportResponse(**report)


def _analysis_from_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "verdict": row["verdict"],
        "summary": row["summary"],
        "score": row["score"],
        "confidence": row["confidence"],
        "metrics": [_normalize_metric(metric) for metric in decode(row["metrics_json"])],
        "score_components": decode(row["score_components_json"]),
        "supporting_factors": decode(row["supporting_factors_json"]),
        "contradicting_factors": decode(row["contradicting_factors_json"]),
        "caveats": decode(row["caveats_json"]),
        "citations": decode(row["citations_json"]),
        "model_used": row["model_used"],
        "headline_claims": _decode_list(row, "headline_claims_json"),
        "composition": _decode_list(row, "composition_json"),
        "revision_adjustment": _decode_obj(row, "revision_adjustment_json"),
        "tone": _decode_obj(row, "tone_json"),
        "coverage_gaps": _decode_list(row, "coverage_gaps_json"),
        "verdict_probability": _decode_obj(row, "verdict_probability_json"),
    }


def _decode_list(row: dict[str, Any], key: str) -> list[Any]:
    try:
        v = row[key]
    except (KeyError, IndexError):
        return []
    if v is None:
        return []
    return decode(v)


def _decode_obj(row: dict[str, Any], key: str) -> dict[str, Any] | None:
    try:
        v = row[key]
    except (KeyError, IndexError):
        return None
    if v is None:
        return None
    return decode(v)


def _normalize_metric(metric: dict[str, Any]) -> dict[str, Any]:
    if "key" not in metric:
        metric["key"] = re.sub(r"[^a-z0-9]+", "_", metric.get("name", "metric").lower()).strip("_") or "metric"
    metric.setdefault("numeric_value", None)
    metric.setdefault("unit", None)
    metric.setdefault("prior_value", None)
    metric.setdefault("delta", None)
    metric.setdefault("direction", "neutral")
    metric.setdefault("source", None)
    metric.setdefault("math", None)
    return metric
