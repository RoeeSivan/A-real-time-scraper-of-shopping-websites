from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Resolve repo root so we read the shared top-level .env from the backend.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    firecrawl_api_key: str | None = None

    # CORS — frontend runs on Next.js default port.
    frontend_origin: str = "http://localhost:3000"


settings = Settings()
