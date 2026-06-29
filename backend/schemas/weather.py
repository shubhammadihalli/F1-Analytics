"""Response model for track/air weather samples."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class WeatherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: int
    date: dt.datetime
    air_temperature: float | None
    track_temperature: float | None
    humidity: float | None
    pressure: float | None
    rainfall: float | None
    wind_direction: int | None
    wind_speed: float | None
