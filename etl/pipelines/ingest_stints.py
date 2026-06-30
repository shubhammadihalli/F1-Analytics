"""Fetch and persist tyre stint data (compound, lap range, tyre age) for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import replace_for_session, to_records
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.stint import Stint


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_stints(session_key=session_key)
    raw_stints: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": s["session_key"],
            "driver_number": s["driver_number"],
            "stint_number": s["stint_number"],
            "compound": s.get("compound"),
            "lap_start": s["lap_start"],
            "lap_end": s.get("lap_end"),
            "tyre_age_at_start": s.get("tyre_age_at_start") or 0,
        }
        for s in raw_stints
        if s.get("stint_number") is not None and s.get("lap_start") is not None
    ]
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return replace_for_session(db, Stint, session_key, rows)
