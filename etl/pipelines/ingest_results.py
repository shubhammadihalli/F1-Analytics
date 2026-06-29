"""Fetch and persist the classification/result rows for a single session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import to_records, upsert
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from etl.transformers.result_transformer import to_result_rows
from models.result import Result


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> list[dict[str, Any]]:
    df = await client.get_results(session_key=session_key)
    raw_results = to_records(df)
    rows = to_result_rows(session_key, raw_results)
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    upsert(db, Result, rows)
    return rows
