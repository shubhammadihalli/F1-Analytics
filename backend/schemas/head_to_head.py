"""Response model for the driver-vs-driver head-to-head comparison."""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.driver import DriverOut


class HeadToHeadSessionOut(BaseModel):
    session_key: int
    session_name: str | None
    session_type: str | None
    year: int | None
    driver1_position: int | None
    driver2_position: int | None
    driver1_points: float | None
    driver2_points: float | None


class HeadToHeadOut(BaseModel):
    driver1: DriverOut
    driver2: DriverOut
    sessions_compared: int
    driver1_ahead: int
    driver2_ahead: int
    driver1_points_total: float
    driver2_points_total: float
    sessions: list[HeadToHeadSessionOut]
