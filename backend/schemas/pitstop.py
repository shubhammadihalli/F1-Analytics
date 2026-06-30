"""Response model for pit lane stop timing."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class PitStopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_key: int
    driver_number: int
    lap_number: int
    date: dt.datetime | None
    pit_duration: float | None
    stop_duration: float | None
    lane_duration: float | None
