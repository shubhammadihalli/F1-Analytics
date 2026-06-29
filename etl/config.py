"""ETL runtime configuration, loaded from environment variables / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ETLSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/f1_analytics"
    openf1_api_key: str | None = None
    api_sports_key: str | None = None
    default_season: int = 2026


settings = ETLSettings()
