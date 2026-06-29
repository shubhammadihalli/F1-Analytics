"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import router as v1_router
from backend.core.config import settings
from backend.core.exceptions import register_exception_handlers

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Read-only analytics API over F1 session, lap, telemetry, weather, and results data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(v1_router, prefix="/api/v1")
