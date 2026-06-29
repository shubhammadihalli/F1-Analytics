"""Response model for lap-by-lap timing data."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class LapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_key: int
    driver_number: int
    lap_number: int
    date_start: dt.datetime | None
    lap_duration: float | None
    duration_sector_1: float | None
    duration_sector_2: float | None
    duration_sector_3: float | None
    i1_speed: int | None
    i2_speed: int | None
    st_speed: int | None
    is_pit_out_lap: bool
