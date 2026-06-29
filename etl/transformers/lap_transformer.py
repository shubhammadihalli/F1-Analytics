"""Transform raw OpenF1 laps payloads into ORM-ready Lap rows."""

from __future__ import annotations

from typing import Any


def to_lap_rows(raw_laps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "session_key": lap["session_key"],
            "driver_number": lap["driver_number"],
            "lap_number": lap["lap_number"],
            "date_start": lap.get("date_start"),
            "lap_duration": lap.get("lap_duration"),
            "duration_sector_1": lap.get("duration_sector_1"),
            "duration_sector_2": lap.get("duration_sector_2"),
            "duration_sector_3": lap.get("duration_sector_3"),
            "i1_speed": lap.get("i1_speed"),
            "i2_speed": lap.get("i2_speed"),
            "st_speed": lap.get("st_speed"),
            "is_pit_out_lap": bool(lap.get("is_pit_out_lap", False)),
        }
        for lap in raw_laps
        if lap.get("lap_number") is not None
    ]
