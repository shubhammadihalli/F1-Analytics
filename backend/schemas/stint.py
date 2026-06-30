"""Response model for tyre stint data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: int
    driver_number: int
    stint_number: int
    compound: str | None
    lap_start: int
    lap_end: int | None
    tyre_age_at_start: int
