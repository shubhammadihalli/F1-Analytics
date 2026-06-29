"""Response model for race weekend sessions (practice/qualifying/sprint/race).

Exposed at `/races` even though it covers every session type, not just
races: the underlying `sessions` table is the only place this data lives,
and `session_type` is filterable for callers who want races specifically.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class RaceOut(BaseModel):
    session_key: int
    meeting_key: int | None
    circuit_key: int | None
    circuit_short_name: str | None = None
    year: int | None
    session_type: str | None
    session_name: str | None
    date_start: dt.datetime | None
    date_end: dt.datetime | None
    is_cancelled: bool
