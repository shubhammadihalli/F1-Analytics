"""Fetch and persist the driver roster for every meeting in a season."""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from etl.loaders.postgres_loader import to_records, upsert
from etl.transformers.driver_transformer import to_driver_rows
from models.driver import Driver


async def fetch(client: OpenF1Client, meeting_keys: list[int]) -> list[dict[str, Any]]:
    """Fetch the driver roster for each meeting and flatten into one list."""
    raw_drivers: list[dict[str, Any]] = []
    for meeting_key in meeting_keys:
        df = await client.get_drivers(meeting_key=meeting_key)
        raw_drivers.extend(to_records(df))
    return raw_drivers


def run(db: DBSession, raw_drivers: list[dict[str, Any]]) -> None:
    upsert(db, Driver, to_driver_rows(raw_drivers))


def ensure_minimal_drivers(db: DBSession, driver_numbers: set[int]) -> None:
    """Insert bare driver_number-only rows for drivers missing profile data.

    OpenF1 omits some entries (e.g. preseason test/reserve drivers) from the
    /drivers endpoint even though they appear in /laps, /pit, and
    /session_result. A no-op-on-conflict insert satisfies the foreign key
    without ever overwriting a driver we already know the profile for. Does
    not commit; participates in the caller's transaction.
    """
    if not driver_numbers:
        return
    stmt = insert(Driver).values([{"driver_number": n} for n in sorted(driver_numbers)])
    stmt = stmt.on_conflict_do_nothing(index_elements=["driver_number"])
    db.execute(stmt)
