"""Backend runtime configuration, loaded from environment variables / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/f1_analytics"
    api_title: str = "F1 Analytics API"
    api_version: str = "1.0.0"
    cors_origins: list[str] = ["*"]
    cache_ttl_seconds: float = 60.0
    default_page_size: int = 50
    max_page_size: int = 500


settings = BackendSettings()
