"""Fetch and persist pit lane stop timing for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import to_records, upsert
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.pitstop import PitStop


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_pit_stops(session_key=session_key)
    raw_pits: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": p["session_key"],
            "driver_number": p["driver_number"],
            "lap_number": p["lap_number"],
            "date": p.get("date"),
            "pit_duration": p.get("pit_duration"),
            "stop_duration": p.get("stop_duration"),
            "lane_duration": p.get("lane_duration"),
        }
        for p in raw_pits
        if p.get("lap_number") is not None
    ]
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return upsert(db, PitStop, rows)
