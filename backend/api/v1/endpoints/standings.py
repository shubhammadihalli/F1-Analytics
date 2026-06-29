"""Driver and constructor championship standings endpoint.

Not paginated: a season's standings are bounded by the grid size (~20
drivers, ~10 constructors), so pagination would add complexity with no
real benefit here.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.cache import make_key, response_cache
from backend.dependencies import get_db
from backend.schemas.standing import StandingOut
from models.constructor_standing import ConstructorStanding
from models.driver import Driver
from models.driver_standing import DriverStanding

router = APIRouter(tags=["standings"])


@router.get("/standings", response_model=list[StandingOut])
def list_standings(
    year: int = Query(..., description="Championship year (required)."),
    type: Literal["driver", "constructor"] = Query(
        "driver", description="Which championship to return."
    ),
    db: Session = Depends(get_db),
) -> list[StandingOut]:
    key = make_key("standings", year=year, type=type)
    cached = response_cache.get(key)
    if cached is not None:
        return cached

    result: list[StandingOut]
    if type == "driver":
        rows = db.execute(
            select(DriverStanding, Driver.full_name, Driver.team_name)
            .join(Driver, Driver.driver_number == DriverStanding.driver_number)
            .where(DriverStanding.year == year)
            .order_by(DriverStanding.position)
        ).all()
        result = [
            StandingOut(
                type="driver",
                year=standing.year,
                position=standing.position,
                points=standing.points,
                wins=standing.wins,
                driver_number=standing.driver_number,
                full_name=full_name,
                team_name=team_name,
            )
            for standing, full_name, team_name in rows
        ]
    else:
        result = [
            StandingOut(
                type="constructor",
                year=standing.year,
                position=standing.position,
                points=standing.points,
                wins=standing.wins,
                team_name=standing.team_name,
            )
            for standing in db.scalars(
                select(ConstructorStanding)
                .where(ConstructorStanding.year == year)
                .order_by(ConstructorStanding.position)
            )
        ]

    response_cache.set(key, result)
    return result
