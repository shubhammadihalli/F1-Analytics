"""Response model for starting grid positions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StartingGridOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_key: int
    driver_number: int
    grid_position: int
    qualifying_lap_duration: float | None
