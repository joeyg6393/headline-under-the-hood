from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                report_type TEXT NOT NULL,
                release_date TEXT NOT NULL,
                headline TEXT NOT NULL,
                raw_file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL UNIQUE,
                verdict TEXT NOT NULL,
                summary TEXT NOT NULL,
                score INTEGER NOT NULL,
                confidence REAL NOT NULL,
                metrics_json TEXT NOT NULL,
                score_components_json TEXT NOT NULL DEFAULT '[]',
                supporting_factors_json TEXT NOT NULL,
                contradicting_factors_json TEXT NOT NULL,
                caveats_json TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                model_used TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES reports(id)
            )
            """
        )
        _ensure_column(conn, "analyses", "score_components_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "analyses", "headline_claims_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "analyses", "composition_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "analyses", "revision_adjustment_json", "TEXT")
        _ensure_column(conn, "analyses", "tone_json", "TEXT")
        _ensure_column(conn, "analyses", "coverage_gaps_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "analyses", "verdict_probability_json", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                metric_key TEXT NOT NULL,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                numeric_value REAL,
                unit TEXT,
                prior_value REAL,
                delta REAL,
                direction TEXT NOT NULL,
                source TEXT,
                math TEXT,
                interpretation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES reports(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS score_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                points INTEGER NOT NULL,
                math TEXT NOT NULL,
                evidence TEXT NOT NULL,
                direction TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES reports(id)
            )
            """
        )


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def decode(value: str) -> Any:
    return json.loads(value)
