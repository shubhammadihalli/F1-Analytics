"""Transform raw OpenF1 session payloads into ORM-ready Circuit/Session rows."""

from __future__ import annotations

from typing import Any


def to_circuit_rows(raw_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[int, dict[str, Any]] = {}
    for s in raw_sessions:
        circuit_key = s.get("circuit_key")
        if circuit_key is None:
            continue
        seen[circuit_key] = {
            "circuit_key": circuit_key,
            "circuit_short_name": s.get("circuit_short_name"),
            "country_code": s.get("country_code"),
            "country_name": s.get("country_name"),
            "location": s.get("location"),
        }
    return list(seen.values())


def to_session_rows(raw_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": s["session_key"],
            "meeting_key": s.get("meeting_key"),
            "circuit_key": s.get("circuit_key"),
            "year": s.get("year"),
            "session_type": s.get("session_type"),
            "session_name": s.get("session_name"),
            "date_start": s.get("date_start"),
            "date_end": s.get("date_end"),
            "is_cancelled": bool(s.get("is_cancelled", False)),
        }
        for s in raw_sessions
        if s.get("session_key") is not None
    ]
