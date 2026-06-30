"""Response model for driver position-over-time samples."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: int
    driver_number: int
    date: dt.datetime
    position: int
