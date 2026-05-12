# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Headline Under The Hood** — a local-first FastAPI app that compares financial/economic news headlines against the underlying official release text, producing a deterministic score plus a structured explanation.

## Commands

All commands assume PowerShell on Windows with the venv at `.venv`.

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env

# Run web server (with Temporal — needs `temporal server start-dev` and `python -m app.worker`)
uvicorn app.main:app --reload

# Run web server without Temporal (synchronous analysis — set USE_TEMPORAL=false in .env)
uvicorn app.main:app --reload

# Tests
pytest                              # whole suite
pytest tests/test_local_analysis.py # single file
pytest tests/test_local_analysis.py::test_local_analysis_flags_payroll_quality_caveats  # single test

# Historical data pull (writes under data/historical-reports/)
python scripts\pull_historical_reports.py
```

## Architecture

### Score-first, explanation-second

The core invariant is that **the deterministic Python analyzer owns the score, metrics, and score components**. The optional OpenAI layer only rewrites the prose around them — it never invents the number. See `app/analyzer.py:75-90` (`analyze_report`) and `app/openai_analysis.py:19-53`: the OpenAI result has its `score`, `metrics`, and `score_components` overwritten with the baseline before being returned. If you change scoring logic, change it in `_local_analysis` only.

### Request lifecycle

`POST /api/reports` → `save_raw_report` writes the text to disk under `data/storage/raw-reports/<source>/<type>/<date>.txt` → `create_report` inserts a SQLite row with status `pending` → `_start_analysis` either runs `analyze_report_activity` synchronously (when `USE_TEMPORAL=false`) or kicks off a Temporal workflow → activity reads the file, runs `analyze_report`, persists results via `save_analysis`, sets status to `complete`.

The Temporal workflow (`app/workflows.py`) is intentionally thin: a single activity with retry policy. The activity (`app/activities.py`) shims `temporalio.activity` with a no-op `defn` decorator when temporalio is missing, so the analyzer is importable in environments that can't install Temporal.

### Storage layout

- **SQLite** (`data/app.db`): `reports`, `analyses`, `report_metrics`, `score_components`. `init_db` is idempotent and uses `_ensure_column` for additive migrations — prefer that pattern over manual ALTERs when extending tables.
- **Filesystem** (`data/storage/`): raw report text, organized by source/type/date slug.
- **Historical pulls** (`data/historical-reports/`): outputs of `scripts/pull_historical_reports.py`, with a `manifest.json` recording blocked/unavailable sources rather than silently skipping them.

### Analyzer contract (`app/analyzer.py`)

Two parallel extraction pipelines: jobs-style integer extraction (`_extract_jobs_number`, `_extract_estimate_number`) and percentage-style extraction (`_extract_percent_number`, `_extract_estimate_percent`). Both feed into the same `score_components` list, where each component carries `label`, `points`, `math` (the literal arithmetic shown to the user), `evidence`, and `direction`. The frontend renders `math` verbatim — keep it human-readable.

`KEYWORD_RULES` and `metric_specs` are the two extension points for new caveats/metrics. Adding a new release type usually means adding a metric spec (with keywords, max penalty, divisor) rather than new top-level logic.

### Frontend

Plain static HTML/JS/CSS under `web/`, served by FastAPI's `StaticFiles` mount at `/static`. `index.html` is the dashboard; `report.html` is the per-report deep dive (rendered server-side as a 404 check, then hydrated via `/api/reports/{id}`).

## Conventions

- **Settings are cached.** `get_settings()` uses `@lru_cache`. Tests that mutate env vars must call `get_settings.cache_clear()` after `monkeypatch.setenv` — see existing tests for the pattern.
- **Dates are strings (ISO `YYYY-MM-DD`).** No `date` objects on the wire or in SQLite.
- **JSON columns** in `analyses` are encoded via `app.db.encode/decode` (plain `json.dumps`/`loads` with `ensure_ascii=True`).
- **The `model_used` field** distinguishes `local-heuristic-v0` from the OpenAI model id; tests assert against it to confirm which path ran.
