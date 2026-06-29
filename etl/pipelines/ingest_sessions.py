"""Fetch and persist race-weekend sessions for a season from OpenF1."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import to_records, upsert
from etl.transformers.session_transformer import to_session_rows
from models.session import Session


async def fetch(client: OpenF1Client, year: int) -> list[dict[str, Any]]:
    df = await client.get_sessions(year=year)
    return to_records(df)


def run(db: DBSession, raw_sessions: list[dict[str, Any]]) -> None:
    upsert(db, Session, to_session_rows(raw_sessions))
