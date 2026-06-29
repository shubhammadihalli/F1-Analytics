"""Persist the distinct constructors found in a season's driver rosters."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from etl.loaders.postgres_loader import upsert
from etl.transformers.driver_transformer import to_constructor_rows
from models.constructor import Constructor


def run(db: DBSession, raw_drivers: list[dict[str, Any]]) -> None:
    upsert(db, Constructor, to_constructor_rows(raw_drivers))
