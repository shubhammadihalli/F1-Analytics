"""Response model for per-session driver classification."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_key: int
    driver_number: int
    position: int | None
    number_of_laps: int | None
    points: float | None
    dnf: bool
    dns: bool
    dsq: bool
    duration: float | None
    gap_to_leader: float | None
