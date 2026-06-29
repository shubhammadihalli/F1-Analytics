"""Fetch and persist car telemetry for every driver in a session.

OpenF1's /car_data endpoint rejects whole-session requests as "too much data
at once", so each driver must be fetched separately, and each driver's
batch can be tens of thousands of rows. Unlike the other pipelines, this one
commits per driver instead of letting the caller wrap the whole session in
one transaction: holding a single multi-minute transaction open across ~20
sequential HTTP fetches risks long lock hold times, and a failure on driver
15 of 20 would otherwise roll back drivers 1-14's already-fetched data too.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import dedupe_by, replace_for_driver_session, to_records
from models.telemetry import Telemetry
from utils.logger import get_logger

logger = get_logger(__name__)


async def run(
    client: OpenF1Client, db: DBSession, session_key: int, driver_numbers: list[int]
) -> int:
    total = 0
    for driver_number in driver_numbers:
        df = await client.get_car_data(session_key=session_key, driver_number=driver_number)
        raw: list[dict[str, Any]] = to_records(df)
        rows = [
            {
                "session_key": r["session_key"],
                "driver_number": r["driver_number"],
                "date": r["date"],
                "speed": r.get("speed"),
                "throttle": r.get("throttle"),
                "brake": r.get("brake"),
                "rpm": r.get("rpm"),
                "n_gear": r.get("n_gear"),
                "drs": r.get("drs"),
            }
            for r in raw
            if r.get("date") is not None
        ]
        rows = dedupe_by(rows, "session_key", "driver_number", "date")
        with db.begin():
            total += replace_for_driver_session(db, Telemetry, session_key, driver_number, rows)
    return total
