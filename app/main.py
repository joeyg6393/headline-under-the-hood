from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.activities import analyze_report_activity
from app.config import get_settings
from app.db import init_db
from app.repository import create_report, find_report_id, get_report_response, list_reports
from app.sample_data import MAJOR_RELEASE_SAMPLES, REPORT_PRESETS
from app.schemas import ReportCreate, ReportResponse
from app.storage import save_raw_report


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_settings().storage_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Headline Under The Hood", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path("web/index.html"))


@app.get("/reports/{report_id}")
def report_page(report_id: int) -> FileResponse:
    if get_report_response(report_id) is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(Path("web/report.html"))


@app.get("/api/reports", response_model=list[ReportResponse])
def reports() -> list[ReportResponse]:
    return [ReportResponse(**report) for report in list_reports()]


@app.get("/api/report-presets")
def report_presets() -> list[dict[str, str]]:
    return REPORT_PRESETS


@app.get("/api/reports/{report_id}", response_model=ReportResponse)
def report_detail(report_id: int) -> ReportResponse:
    report = get_report_response(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/api/reports", response_model=ReportResponse)
async def submit_report(payload: ReportCreate) -> ReportResponse:
    raw_file_path = save_raw_report(
        source=payload.source,
        report_type=payload.report_type,
        release_date=payload.release_date,
        text=payload.report_text,
    )
    report_id = create_report(
        source=payload.source,
        report_type=payload.report_type,
        release_date=payload.release_date,
        headline=payload.headline,
        raw_file_path=raw_file_path,
    )
    await _start_analysis(report_id)
    report = get_report_response(report_id)
    if report is None:
        raise HTTPException(status_code=500, detail="Report was not created")
    return report


@app.post("/api/reports/demo", response_model=ReportResponse)
async def demo_report() -> ReportResponse:
    payload = ReportCreate(
        source="BLS",
        report_type="Nonfarm Payrolls",
        release_date="2026-05-08",
        headline="Payrolls jump by 150k, crushing the 65k estimate",
        report_text=(
            "Total nonfarm payroll employment increased by 150,000 in April. "
            "Employment continued to trend up in health care and government employment. "
            "The change in total nonfarm payroll employment for February was revised down by 35,000 "
            "and the change for March was revised down by 22,000. "
            "The number of persons employed part time for economic reasons increased by 42,000. "
            "Multiple jobholders also increased by 25,000 over the month. "
            "Government employment increased by 38,000. "
            "The labor force participation rate was little changed, and the household survey showed "
            "civilian employment was roughly flat."
        ),
    )
    return await submit_report(payload)


@app.post("/api/reports/demo-set", response_model=list[ReportResponse])
async def demo_report_set() -> list[ReportResponse]:
    created: list[ReportResponse] = []
    for sample in MAJOR_RELEASE_SAMPLES:
        existing_id = find_report_id(
            source=sample.source,
            report_type=sample.report_type,
            release_date=sample.release_date,
            headline=sample.headline,
        )
        if existing_id:
            existing = get_report_response(existing_id)
            if existing:
                created.append(existing)
                continue
        created.append(await submit_report(sample))
    return created


async def _start_analysis(report_id: int) -> None:
    settings = get_settings()
    if not settings.use_temporal:
        analyze_report_activity(report_id)
        return

    from temporalio.client import Client

    from app.workflows import ReportAnalysisWorkflow

    client = await Client.connect(settings.temporal_address)
    await client.start_workflow(
        ReportAnalysisWorkflow.run,
        report_id,
        id=f"report-analysis-{report_id}",
        task_queue=settings.temporal_task_queue,
    )
