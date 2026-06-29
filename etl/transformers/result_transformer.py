"""Transform raw OpenF1 session_result payloads into ORM-ready Result rows."""

from __future__ import annotations

from typing import Any


def to_result_rows(session_key: int, raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": session_key,
            "driver_number": r["driver_number"],
            "position": r.get("position"),
            "number_of_laps": r.get("number_of_laps"),
            "points": r.get("points"),
            "dnf": bool(r.get("dnf", False)),
            "dns": bool(r.get("dns", False)),
            "dsq": bool(r.get("dsq", False)),
            "duration": _to_float_or_none(r.get("duration")),
            "gap_to_leader": _to_float_or_none(r.get("gap_to_leader")),
        }
        for r in raw_results
        if r.get("driver_number") is not None
    ]


def _to_float_or_none(value: Any) -> float | None:
    """Normalize OpenF1's duration/gap_to_leader quirks to a plain float.

    Non-race sessions (e.g. qualifying) report these as a per-segment list;
    lapped race finishers report gap_to_leader as a string like "+1 LAP".
    """
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, (int, float)):
        return float(value)
    return None
