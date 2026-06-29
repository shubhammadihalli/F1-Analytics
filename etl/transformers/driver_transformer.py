"""Transform raw OpenF1 driver payloads into ORM-ready Constructor/Driver rows."""

from __future__ import annotations

from typing import Any


def to_constructor_rows(raw_drivers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for d in raw_drivers:
        team_name = d.get("team_name")
        if team_name:
            seen[team_name] = {"team_name": team_name, "team_colour": d.get("team_colour")}
    return list(seen.values())


def to_driver_rows(raw_drivers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[int, dict[str, Any]] = {}
    for d in raw_drivers:
        number = d.get("driver_number")
        if number is None:
            continue
        seen[number] = {
            "driver_number": number,
            "full_name": d.get("full_name"),
            "broadcast_name": d.get("broadcast_name"),
            "name_acronym": d.get("name_acronym"),
            "first_name": d.get("first_name"),
            "last_name": d.get("last_name"),
            "country_code": d.get("country_code"),
            "headshot_url": d.get("headshot_url"),
            "team_name": d.get("team_name"),
        }
    return list(seen.values())
