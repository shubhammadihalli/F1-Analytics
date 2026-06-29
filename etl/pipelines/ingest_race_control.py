"""Fetch and persist race control messages (flags, safety car, incidents) for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import replace_for_session, to_records
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.race_control import RaceControlMessage


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_race_control(session_key=session_key)
    raw_messages: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": m["session_key"],
            "driver_number": m.get("driver_number"),
            "date": m["date"],
            "category": m.get("category"),
            "flag": m.get("flag"),
            "scope": m.get("scope"),
            "sector": m.get("sector"),
            "lap_number": m.get("lap_number"),
            "message": m.get("message"),
        }
        for m in raw_messages
        if m.get("date") is not None
    ]
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows if r["driver_number"] is not None})
    return replace_for_session(db, RaceControlMessage, session_key, rows)
