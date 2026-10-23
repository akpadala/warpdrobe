from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = f"sqlite:///{REPO_ROOT / 'backend' / 'warpdrobe.db'}"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Output of spark/pairings_job.py. Falls back to built-in color rules when missing.
    pairings_path: Path = REPO_ROOT / "data" / "pairings.json"
    # Built React app, served by the API in production.
    frontend_dist: Path = REPO_ROOT / "frontend" / "dist"
    # Comma-separated emails allowed to see /api/admin/metrics.
    admin_emails: str = ""
    cors_origins: str = "http://localhost:5173"

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
