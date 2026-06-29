"""Response model for car telemetry samples."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: int
    driver_number: int
    date: dt.datetime
    speed: int | None
    throttle: int | None
    brake: int | None
    rpm: int | None
    n_gear: int | None
    drs: int | None
