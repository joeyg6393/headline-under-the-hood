from __future__ import annotations

try:
    from temporalio import activity
except ModuleNotFoundError:
    class _LocalActivity:
        @staticmethod
        def defn(fn):
            return fn

    activity = _LocalActivity()

from app.analyzer import ReportContext, analyze_report
from app.repository import get_report, save_analysis, update_report_status
from app.storage import read_text_file


@activity.defn
def analyze_report_activity(report_id: int) -> None:
    report = get_report(report_id)
    if report is None:
        raise ValueError(f"Report {report_id} was not found")

    update_report_status(report_id, "processing")
    text = read_text_file(report["raw_file_path"])
    analysis = analyze_report(
        ReportContext(
            source=report["source"],
            report_type=report["report_type"],
            release_date=report["release_date"],
            headline=report["headline"],
            report_text=text,
        )
    )
    save_analysis(report_id, analysis)
