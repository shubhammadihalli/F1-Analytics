"""Ingest the Season row for a given championship year."""

from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from etl.loaders.postgres_loader import upsert
from models.season import Season


def run(db: DBSession, year: int) -> None:
    upsert(db, Season, [{"year": year}])
