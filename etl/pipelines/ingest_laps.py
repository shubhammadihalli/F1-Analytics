"""Fetch and persist lap-by-lap timing for every driver in a session."""

from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import to_records, upsert
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from etl.transformers.lap_transformer import to_lap_rows
from models.lap import Lap


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_laps(session_key=session_key)
    raw_laps = to_records(df)
    rows = to_lap_rows(raw_laps)
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return upsert(db, Lap, rows)
