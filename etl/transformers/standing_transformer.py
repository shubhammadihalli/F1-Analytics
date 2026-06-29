"""Compute cumulative driver/constructor standings from a season's results."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_driver_standings(year: int, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: dict[int, float] = defaultdict(float)
    wins: dict[int, int] = defaultdict(int)
    for r in results:
        driver_number = r["driver_number"]
        points[driver_number] += r.get("points") or 0.0
        if r.get("position") == 1:
            wins[driver_number] += 1

    ranked = sorted(points.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "year": year,
            "driver_number": driver_number,
            "points": total_points,
            "wins": wins[driver_number],
            "position": rank,
        }
        for rank, (driver_number, total_points) in enumerate(ranked, start=1)
    ]


def compute_constructor_standings(
    year: int, results: list[dict[str, Any]], driver_to_team: dict[int, str]
) -> list[dict[str, Any]]:
    points: dict[str, float] = defaultdict(float)
    wins: dict[str, int] = defaultdict(int)
    for r in results:
        team_name = driver_to_team.get(r["driver_number"])
        if team_name is None:
            continue
        points[team_name] += r.get("points") or 0.0
        if r.get("position") == 1:
            wins[team_name] += 1

    ranked = sorted(points.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "year": year,
            "team_name": team_name,
            "points": total_points,
            "wins": wins[team_name],
            "position": rank,
        }
        for rank, (team_name, total_points) in enumerate(ranked, start=1)
    ]
