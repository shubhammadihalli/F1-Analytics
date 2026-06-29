"""Generic Postgres upsert (INSERT ... ON CONFLICT DO UPDATE) loader."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import Table, inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.base import Base
from utils.logger import get_logger

logger = get_logger(__name__)


def to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to dict rows, replacing pandas NaN/NaT with None.

    OpenF1 represents missing values (DNS/DNF, untimed sectors, etc.) as NaN.
    Reassigning None into a float64 *column* gets silently re-coerced back to
    NaN by pandas, so the substitution has to happen per-value after the
    DataFrame is already flattened to plain Python dicts. Some OpenF1 fields
    (e.g. qualifying segment durations) hold lists rather than scalars, so
    `pd.isna` is only applied to non-list values to avoid its array-ambiguous
    truth value error.
    """
    records = df.to_dict("records")
    return [
        {
            key: (None if not isinstance(value, list) and pd.isna(value) else value)
            for key, value in row.items()
        }
        for row in records
    ]


def dedupe_by(rows: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    """Keep the last row for each distinct combination of `keys`.

    OpenF1 occasionally retransmits an identical sample (same timestamp, same
    values) within one response; that collides with a unique constraint on
    those same columns, so duplicates are dropped before insertion.
    """
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {tuple(row[key] for key in keys): row for row in rows}
    return list(deduped.values())


def upsert(session: Session, model: type[Base], rows: list[dict[str, Any]]) -> int:
    """Bulk insert `rows` into `model`'s table, updating non-key columns on conflict.

    Returns the number of rows written; no-ops on an empty `rows` list. Does
    *not* commit - the caller owns the transaction boundary (see `cli.py`),
    so a failure anywhere in a logical unit of work rolls back everything in
    it rather than leaving partial writes.
    """
    if not rows:
        return 0

    table = model.__table__
    assert isinstance(table, Table)
    pk_columns = [col.name for col in inspect(model).primary_key]
    update_columns = [col.name for col in table.columns if col.name not in pk_columns]

    stmt = insert(table).values(rows)
    if update_columns:
        stmt = stmt.on_conflict_do_update(
            index_elements=pk_columns,
            set_={name: stmt.excluded[name] for name in update_columns},
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)

    session.execute(stmt)
    logger.info("upserted %d rows into %s", len(rows), table.name)
    return len(rows)


def replace_for_session(
    session: Session, model: type[Base], session_key: int, rows: list[dict[str, Any]]
) -> int:
    """Delete a session's existing rows and bulk-insert `rows` in their place.

    For surrogate-key tables with no natural conflict target (weather,
    positions, messages, race control), re-running the same session through
    `upsert` would just keep inserting duplicates. Scoping a delete+insert to
    one session_key keeps re-ingestion idempotent without needing a unique
    business key. Does not commit; see `upsert` above.
    """
    table = model.__table__
    assert isinstance(table, Table)
    session.execute(table.delete().where(table.c.session_key == session_key))
    if rows:
        session.execute(table.insert(), rows)
    logger.info("replaced %d rows in %s for session_key=%s", len(rows), table.name, session_key)
    return len(rows)


def replace_for_driver_session(
    session: Session,
    model: type[Base],
    session_key: int,
    driver_number: int,
    rows: list[dict[str, Any]],
) -> int:
    """Delete one driver's existing rows for a session and bulk-insert `rows` in their place.

    Like `replace_for_session`, but scoped to (session_key, driver_number)
    for tables that must be fetched one driver at a time (telemetry), so
    re-running one driver's fetch doesn't wipe out other drivers already
    loaded for the same session. Does not commit; see `upsert` above.
    """
    table = model.__table__
    assert isinstance(table, Table)
    session.execute(
        table.delete().where(table.c.session_key == session_key, table.c.driver_number == driver_number)
    )
    if rows:
        session.execute(table.insert(), rows)
    logger.info(
        "replaced %d rows in %s for session_key=%s driver_number=%s",
        len(rows),
        table.name,
        session_key,
        driver_number,
    )
    return len(rows)
