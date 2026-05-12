from __future__ import annotations

from datetime import timedelta

from temporalio.common import RetryPolicy
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities import analyze_report_activity


@workflow.defn
class ReportAnalysisWorkflow:
    @workflow.run
    async def run(self, report_id: int) -> None:
        await workflow.execute_activity(
            analyze_report_activity,
            report_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
