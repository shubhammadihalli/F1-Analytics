"""Tests for /laps."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_laps_filters_by_session_and_driver(client: TestClient) -> None:
    response = client.get("/api/v1/laps", params={"session_key": 11234, "driver_number": 63})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(
        lap["session_key"] == 11234 and lap["driver_number"] == 63 for lap in body["items"]
    )


def test_list_laps_sort_by_lap_duration_descending(client: TestClient) -> None:
    response = client.get(
        "/api/v1/laps",
        params={"session_key": 11234, "driver_number": 63, "sort": "-lap_duration", "page_size": 50},
    )
    assert response.status_code == 200
    durations = [lap["lap_duration"] for lap in response.json()["items"] if lap["lap_duration"] is not None]
    assert durations == sorted(durations, reverse=True)
