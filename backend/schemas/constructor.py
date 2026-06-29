"""Response model for constructor (team) resources."""

from __future__ import annotations

from pydantic import BaseModel


class ConstructorOut(BaseModel):
    team_name: str
    team_colour: str | None
    driver_numbers: list[int] = []
