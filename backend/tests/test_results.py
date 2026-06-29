"""Tests for /results."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_results_for_session_sorted_by_position(client: TestClient) -> None:
    response = client.get("/api/v1/results", params={"session_key": 11234, "sort": "position"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 22
    positions = [r["position"] for r in body["items"] if r["position"] is not None]
    assert positions == sorted(positions)
    assert positions[0] == 1


def test_list_results_filters_by_driver(client: TestClient) -> None:
    response = client.get("/api/v1/results", params={"driver_number": 1})
    assert response.status_code == 200
    body = response.json()
    assert all(r["driver_number"] == 1 for r in body["items"])
