from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import analyze_report_activity
from app.config import get_settings
from app.db import init_db
from app.workflows import ReportAnalysisWorkflow


async def main() -> None:
    settings = get_settings()
    init_db()
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ReportAnalysisWorkflow],
        activities=[analyze_report_activity],
    )
    print(f"Worker listening on task queue: {settings.temporal_task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
