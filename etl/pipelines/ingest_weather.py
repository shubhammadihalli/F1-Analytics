"""Fetch and persist weather samples for a session."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import dedupe_by, replace_for_session, to_records
from models.weather import Weather


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    df = await client.get_weather(session_key=session_key)
    raw_weather: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": w["session_key"],
            "date": w["date"],
            "air_temperature": w.get("air_temperature"),
            "track_temperature": w.get("track_temperature"),
            "humidity": w.get("humidity"),
            "pressure": w.get("pressure"),
            "rainfall": w.get("rainfall"),
            "wind_direction": w.get("wind_direction"),
            "wind_speed": w.get("wind_speed"),
        }
        for w in raw_weather
        if w.get("date") is not None
    ]
    return replace_for_session(db, Weather, session_key, dedupe_by(rows, "session_key", "date"))
