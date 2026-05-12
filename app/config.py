from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Headline Under The Hood"
    database_path: Path = Path("data/app.db")
    storage_root: Path = Path("data/storage")
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "financial-report-analysis"
    use_temporal: bool = True
    # Gemini (Google AI) — used for LLM-only structured fields.
    # Get an API key at https://aistudio.google.com/apikey
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = "gemini-2.5-flash-lite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
