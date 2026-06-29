"""Fetch and persist driver position-over-time samples for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import dedupe_by, replace_for_session, to_records
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.position import Position


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_positions(session_key=session_key)
    raw_positions: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": p["session_key"],
            "driver_number": p["driver_number"],
            "date": p["date"],
            "position": p["position"],
        }
        for p in raw_positions
        if p.get("date") is not None and p.get("position") is not None
    ]
    rows = dedupe_by(rows, "session_key", "driver_number", "date")
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return replace_for_session(db, Position, session_key, rows)
