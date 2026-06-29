"""Response model for driver and constructor championship standings.

A single shape covers both: `driver_number`/`full_name` are populated only
for driver standings, `team_name` is populated for both (a driver's team for
that season, or the constructor itself).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StandingOut(BaseModel):
    type: Literal["driver", "constructor"]
    year: int
    position: int | None
    points: float
    wins: int
    driver_number: int | None = None
    full_name: str | None = None
    team_name: str | None = None
