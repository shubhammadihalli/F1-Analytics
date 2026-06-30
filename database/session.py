"""SQLAlchemy engine and session factory, configured from DATABASE_URL."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

def _normalize_database_url(url: str) -> str:
    """Render's fromDatabase binding (and most managed Postgres providers)
    hand back a plain postgresql:// URL; SQLAlchemy defaults that to
    psycopg2, which isn't installed (only psycopg[binary] v3 is)."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/f1_analytics")
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
