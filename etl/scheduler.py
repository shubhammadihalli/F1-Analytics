"""Periodic re-ingestion of the current season via APScheduler."""

from __future__ import annotations

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from etl.cli import ingest_season
from etl.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def start(*, interval_minutes: int = 30) -> AsyncIOScheduler:
    """Schedule recurring ingestion of `settings.default_season` and start the scheduler."""
    scheduler = AsyncIOScheduler()

    async def job() -> None:
        logger.info("scheduled ingestion starting for season %d", settings.default_season)
        await ingest_season(settings.default_season)

    scheduler.add_job(job, trigger=IntervalTrigger(minutes=interval_minutes), next_run_time=None)
    scheduler.start()
    logger.info("scheduler started: every %d minutes", interval_minutes)
    return scheduler


async def _run_forever() -> None:
    start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(_run_forever())
