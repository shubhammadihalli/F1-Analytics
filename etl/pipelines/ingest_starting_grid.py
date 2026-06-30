"""Fetch and persist starting grid positions for a Race or Sprint session.

OpenF1 keys grid data to the qualifying session, not the race - this
resolves "which qualifying session set this race's grid" from the sessions
already loaded in the DB, then stores the result keyed to the race's own
session_key so it can be queried the same way as every other per-race table.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import replace_for_session, to_records
from etl.pipelines.ingest_drivers import ensure_minimal_drivers
from models.session import Session as SessionModel
from models.starting_grid import StartingGridPosition

_GRID_SOURCE_NAME = {
    "Race": "Qualifying",
    "Sprint": "Sprint Qualifying",
}


def _qualifying_session_key(db: DBSession, race_session: SessionModel) -> int | None:
    """The session_key of the Qualifying/Sprint Qualifying session that set this race's grid."""
    source_name = _GRID_SOURCE_NAME.get(race_session.session_name or "")
    if source_name is None or race_session.meeting_key is None:
        return None
    return db.scalar(
        select(SessionModel.session_key).where(
            SessionModel.meeting_key == race_session.meeting_key,
            SessionModel.session_type == "Qualifying",
            SessionModel.session_name == source_name,
        )
    )


async def run(client: OpenF1Client, db: DBSession, session_key: int) -> int:
    race_session = db.get(SessionModel, session_key)
    if race_session is None:
        return 0
    qualifying_session_key = _qualifying_session_key(db, race_session)
    if qualifying_session_key is None:
        return 0

    df = await client.get_starting_grid(session_key=qualifying_session_key)
    raw_grid: list[dict[str, Any]] = to_records(df)
    rows = [
        {
            "session_key": session_key,
            "driver_number": g["driver_number"],
            "grid_position": g["position"],
            "qualifying_lap_duration": g.get("lap_duration"),
        }
        for g in raw_grid
        if g.get("position") is not None and g.get("driver_number") is not None
    ]
    ensure_minimal_drivers(db, {r["driver_number"] for r in rows})
    return replace_for_session(db, StartingGridPosition, session_key, rows)
