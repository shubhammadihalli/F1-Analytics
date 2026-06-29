"""Fetch and persist team radio messages for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import dedupe_by, replace_for_session, to_records
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.message import Message


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_team_radio(session_key=session_key)
    raw_messages: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": m["session_key"],
            "driver_number": m["driver_number"],
            "date": m["date"],
            "recording_url": m.get("recording_url"),
        }
        for m in raw_messages
        if m.get("driver_number") is not None and m.get("date") is not None
    ]
    rows = dedupe_by(rows, "session_key", "driver_number", "date")
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return replace_for_session(db, Message, session_key, rows)
