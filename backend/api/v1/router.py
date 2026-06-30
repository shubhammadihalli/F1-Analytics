"""Aggregates all v1 endpoint routers under one APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1.endpoints import (
    constructors,
    drivers,
    head_to_head,
    health,
    laps,
    pitstops,
    positions,
    races,
    results,
    standings,
    starting_grid,
    stints,
    telemetry,
    weather,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(drivers.router)
router.include_router(races.router)
router.include_router(laps.router)
router.include_router(telemetry.router)
router.include_router(weather.router)
router.include_router(results.router)
router.include_router(standings.router)
router.include_router(constructors.router)
router.include_router(head_to_head.router)
router.include_router(stints.router)
router.include_router(positions.router)
router.include_router(pitstops.router)
router.include_router(starting_grid.router)
