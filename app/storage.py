from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "report"


def save_raw_report(*, source: str, report_type: str, release_date: str, text: str) -> str:
    settings = get_settings()
    folder = settings.storage_root / "raw-reports" / slugify(source) / slugify(report_type)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{slugify(release_date)}.txt"
    path.write_text(text, encoding="utf-8")
    return str(path)


def read_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
