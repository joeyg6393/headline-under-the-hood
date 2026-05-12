# Headline Under The Hood MVP

A local-first MVP for comparing financial/economic news headlines with the details inside official releases.

The first version uses:

- FastAPI for the local web/API server
- SQLite for report metadata and analysis records
- Local file storage under `data/`
- Temporal for durable report-analysis workflows
- Optional OpenAI analysis when `OPENAI_API_KEY` is set
- A deterministic fallback analyzer so the MVP works offline

## What It Does

The MVP lets you submit:

- report source, such as BLS
- report type, such as Nonfarm Payrolls
- release date
- headline text
- report text or a text file

Then it:

1. Stores the raw report locally.
2. Creates a report record in SQLite.
3. Starts a Temporal workflow.
4. Parses the report for concrete labor-market, inflation, growth, and activity metrics.
5. Computes deterministic score components with visible math.
6. Produces an AI-style structured headline-vs-report explanation.
7. Displays the result in a release dashboard with standardized scorecards, report blurbs, source/release/month filters, a date rail, quick-fill presets, a detail panel, and a dedicated full-analysis page for each report.

The score is computed by code first. The explanation layer describes the computed evidence instead of inventing the number.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and add `OPENAI_API_KEY` if you want model-backed analysis. Without it, the local analyzer is used.

## Run With Temporal

Install and start a local Temporal server:

```powershell
temporal server start-dev
```

In another terminal, start the worker:

```powershell
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

In a third terminal, start the web server:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Run Without Temporal

For quick local testing, set this in `.env`:

```text
USE_TEMPORAL=false
```

Then run:

```powershell
uvicorn app.main:app --reload
```

Submissions will be processed synchronously.

## Useful Endpoints

- `GET /` - web app
- `GET /reports/{id}` - full-page report analysis view
- `GET /api/reports` - list reports
- `GET /api/report-presets` - list quick-fill release templates for the form
- `GET /api/reports/{id}` - report detail
- `POST /api/reports` - submit a report
- `POST /api/reports/demo` - create a demo Nonfarm Payrolls-style report
- `POST /api/reports/demo-set` - idempotently seed major monthly releases across PCE, CPI, PPI, NFP, ADP, retail sales, GDP, ISM, claims, JOLTS, and FOMC

## Historical Pulls

The repo includes a repeatable historical pull script:

```powershell
python scripts\pull_historical_reports.py
```

It writes raw source files and normalized CSV/JSON summaries under:

```text
data/historical-reports/
```

Current coverage:

- BLS API data: 12 monthly observations for NFP, CPI, PPI, and JOLTS.
- Census API data: 12 monthly observations for retail sales.
- DOL weekly claims: current and prior calendar-year spreadsheet export.
- ADP: public PDF reports found through ADP's static report pattern.
- BEA: PCE report pages/PDFs and GDP report pages/PDFs.

BEA table data requires a valid API key. Set `BEA_API_KEY` before running the script to pull BEA NIPA table data. The script records blocked or unavailable sources in `data/historical-reports/manifest.json` instead of silently skipping them.

## Next Steps

- Add Supabase Postgres and Storage adapters.
- Add official BLS/FRED/BEA/Census API ingestion.
- Add release-calendar polling.
- Add quote-level citations from official PDFs/HTML.
- Add real forecast/estimate ingestion from a market-data provider.
- Add Temporal retries, failure alerts, and backfills.
