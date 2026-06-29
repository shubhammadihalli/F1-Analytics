"""Persist the distinct circuits referenced by a season's sessions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session as DBSession

from etl.loaders.postgres_loader import upsert
from etl.transformers.session_transformer import to_circuit_rows
from models.circuit import Circuit


def run(db: DBSession, raw_sessions: list[dict[str, Any]]) -> None:
    upsert(db, Circuit, to_circuit_rows(raw_sessions))
