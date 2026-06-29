"""Response models for driver resources."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.schemas.standing import StandingOut


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_number: int
    full_name: str | None
    broadcast_name: str | None
    name_acronym: str | None
    first_name: str | None
    last_name: str | None
    country_code: str | None
    headshot_url: str | None
    team_name: str | None


class DriverCareerStatsOut(BaseModel):
    races_entered: int
    wins: int
    podiums: int
    points_total: float


class DriverDetailOut(DriverOut):
    career_stats: DriverCareerStatsOut
    standings: list[StandingOut]
