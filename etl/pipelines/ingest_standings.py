"""Compute and persist cumulative driver/constructor standings for a season."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from etl.loaders.postgres_loader import upsert
from etl.transformers.standing_transformer import (
    compute_constructor_standings,
    compute_driver_standings,
)
from models.constructor_standing import ConstructorStanding
from models.driver_standing import DriverStanding


def run(
    db: DBSession,
    year: int,
    results: list[dict[str, Any]],
    driver_to_team: dict[int, str],
) -> None:
    upsert(db, DriverStanding, compute_driver_standings(year, results))
    upsert(db, ConstructorStanding, compute_constructor_standings(year, results, driver_to_team))
