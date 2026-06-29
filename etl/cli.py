"""Command-line entry point for running ETL ingestion pipelines."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from api_clients.openf1_client import OpenF1Client
from database.session import SessionLocal
from etl.config import settings
from etl.pipelines import (
    ingest_circuits,
    ingest_constructors,
    ingest_drivers,
    ingest_laps,
    ingest_messages,
    ingest_pitstops,
    ingest_positions,
    ingest_race_control,
    ingest_results,
    ingest_seasons,
    ingest_sessions,
    ingest_standings,
    ingest_telemetry,
    ingest_weather,
)
from models.result import Result
from models.session import Session as SessionModel
from models.telemetry import Telemetry
from utils.logger import get_logger

app = typer.Typer(help="F1 Analytics ETL commands")
logger = get_logger(__name__)


def _completed_session_keys(db: DBSession) -> set[int]:
    """Session keys that need no further work: already have results, or were cancelled."""
    has_results = set(db.execute(select(Result.session_key).distinct()).scalars())
    cancelled = set(
        db.execute(select(SessionModel.session_key).where(SessionModel.is_cancelled.is_(True))).scalars()
    )
    return has_results | cancelled


def _season_points_results(db: DBSession, year: int) -> list[dict[str, Any]]:
    """Every Race/Sprint classification row for `year`, straight from the DB.

    Standings are recomputed from the full season state on every run (not
    just the sessions ingested in this run), so an incremental run still
    produces a correct, complete standings table.
    """
    rows = db.execute(
        select(Result.driver_number, Result.position, Result.points)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(SessionModel.year == year, SessionModel.session_type.in_(["Race", "Sprint"]))
    ).all()
    return [{"driver_number": r.driver_number, "position": r.position, "points": r.points} for r in rows]


def _sessions_missing_telemetry(db: DBSession, year: int) -> list[int]:
    """Session keys for `year` where at least one classified driver's telemetry is missing.

    Compares per-driver coverage rather than just "session has any telemetry
    rows": if a backfill fails partway through (e.g. one driver's fetch
    errors out), the session must still be picked up again next run instead
    of being considered done because *some* driver's data landed.

    Telemetry is intentionally excluded from `_completed_session_keys`: it's
    fetched/backfilled as a separate, much heavier step (see
    `backfill-telemetry`) so the core dataset isn't held hostage to it.
    """
    result_drivers = db.execute(
        select(Result.session_key, Result.driver_number)
        .join(SessionModel, SessionModel.session_key == Result.session_key)
        .where(SessionModel.year == year)
    ).all()
    telemetry_drivers = set(db.execute(select(Telemetry.session_key, Telemetry.driver_number).distinct()))

    needed: dict[int, set[int]] = {}
    for session_key, driver_number in result_drivers:
        needed.setdefault(session_key, set()).add(driver_number)

    return sorted(
        session_key
        for session_key, drivers in needed.items()
        if any((session_key, driver_number) not in telemetry_drivers for driver_number in drivers)
    )


async def ingest_season(year: int, *, include_future: bool = False, force: bool = False) -> None:
    """Pull one season's sessions, drivers, and per-session data (including
    telemetry) from OpenF1 into Postgres, skipping sessions already fully
    ingested, then recompute that season's standings from the full DB state.
    """
    async with OpenF1Client(api_key=settings.openf1_api_key) as client:
        with SessionLocal() as db:
            with db.begin():
                ingest_seasons.run(db, year)

            raw_sessions = await ingest_sessions.fetch(client, year)
            if not include_future:
                now = datetime.now(timezone.utc)
                raw_sessions = [
                    s for s in raw_sessions if datetime.fromisoformat(s["date_start"]) <= now
                ]

            with db.begin():
                ingest_circuits.run(db, raw_sessions)
                ingest_sessions.run(db, raw_sessions)

            meeting_keys = sorted({s["meeting_key"] for s in raw_sessions if s.get("meeting_key")})
            raw_drivers = await ingest_drivers.fetch(client, meeting_keys)
            with db.begin():
                ingest_constructors.run(db, raw_drivers)
                ingest_drivers.run(db, raw_drivers)

            meeting_to_drivers: dict[int, set[int]] = {}
            for d in raw_drivers:
                meeting_key, driver_number = d.get("meeting_key"), d.get("driver_number")
                if meeting_key is not None and driver_number is not None:
                    meeting_to_drivers.setdefault(meeting_key, set()).add(driver_number)

            with db.begin():
                completed = set() if force else _completed_session_keys(db)
            missing_sessions = [
                s
                for s in raw_sessions
                if not s.get("is_cancelled") and s["session_key"] not in completed
            ]
            logger.info(
                "season %d: %d sessions in scope, %d already ingested, %d missing",
                year,
                len(raw_sessions),
                len(raw_sessions) - len(missing_sessions),
                len(missing_sessions),
            )

            for session in missing_sessions:
                session_key = session["session_key"]
                try:
                    with db.begin():
                        await ingest_results.run(client, db, session_key)
                        await ingest_laps.run(client, db, session_key)
                        await ingest_pitstops.run(client, db, session_key)
                        await ingest_weather.run(client, db, session_key)
                        await ingest_positions.run(client, db, session_key)
                        await ingest_race_control.run(client, db, session_key)
                        await ingest_messages.run(client, db, session_key)
                except Exception:
                    logger.exception(
                        "failed to ingest session_key=%s; rolled back, will retry next run",
                        session_key,
                    )
                    continue

                # New sessions get telemetry automatically; backfilling it for
                # sessions ingested before telemetry support existed is a
                # separate, explicit step (`backfill-telemetry`) given its size.
                meeting_key = session.get("meeting_key")
                driver_numbers = sorted(meeting_to_drivers.get(meeting_key, set()) if meeting_key is not None else set())
                try:
                    await ingest_telemetry.run(client, db, session_key, driver_numbers)
                except Exception:
                    logger.exception(
                        "failed to ingest telemetry for session_key=%s; will retry next run",
                        session_key,
                    )

            driver_to_team = {
                d["driver_number"]: d["team_name"]
                for d in raw_drivers
                if d.get("driver_number") is not None and d.get("team_name")
            }
            with db.begin():
                points_results = _season_points_results(db, year)
                ingest_standings.run(db, year, points_results, driver_to_team)

    logger.info("season %d ingestion complete", year)


async def backfill_telemetry(year: int, *, only_session_key: int | None = None) -> None:
    """Backfill telemetry for sessions that already have results but no telemetry yet."""
    async with OpenF1Client(api_key=settings.openf1_api_key) as client:
        with SessionLocal() as db:
            with db.begin():
                target_keys = _sessions_missing_telemetry(db, year)
            if only_session_key is not None:
                target_keys = [k for k in target_keys if k == only_session_key]

            logger.info("telemetry backfill: %d session(s) to process for season %d", len(target_keys), year)

            for session_key in target_keys:
                with db.begin():
                    driver_numbers = sorted(
                        db.execute(
                            select(Result.driver_number).where(Result.session_key == session_key)
                        ).scalars()
                    )
                try:
                    total = await ingest_telemetry.run(client, db, session_key, driver_numbers)
                    logger.info("telemetry backfill: session_key=%s -> %d rows", session_key, total)
                except Exception:
                    logger.exception(
                        "telemetry backfill failed for session_key=%s; will retry next run", session_key
                    )

    logger.info("telemetry backfill complete")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    year: int = typer.Option(settings.default_season, help="Championship year to ingest."),
    include_future: bool = typer.Option(
        False, help="Also ingest sessions scheduled after now (results/laps will be empty)."
    ),
    force: bool = typer.Option(
        False, help="Re-ingest every session even if already fully loaded, instead of only missing ones."
    ),
) -> None:
    """Ingest one F1 season from OpenF1 into Postgres (default action, fetches only missing sessions)."""
    if ctx.invoked_subcommand is not None:
        return
    asyncio.run(ingest_season(year, include_future=include_future, force=force))


@app.command("backfill-telemetry")
def backfill_telemetry_command(
    year: int = typer.Option(settings.default_season, help="Championship year to backfill."),
    session_key: int | None = typer.Option(
        None, help="Only backfill this one session (useful for testing before a full backfill)."
    ),
) -> None:
    """Backfill telemetry for sessions that already have results but predate telemetry support."""
    asyncio.run(backfill_telemetry(year, only_session_key=session_key))


if __name__ == "__main__":
    app()
