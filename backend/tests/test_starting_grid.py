"""Tests for /starting-grid."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_starting_grid_requires_session_key(client: TestClient) -> None:
    assert client.get("/api/v1/starting-grid").status_code == 422


def test_starting_grid_ordered_by_position(client: TestClient) -> None:
    response = client.get("/api/v1/starting-grid", params={"session_key": 11234})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 22
    positions = [g["grid_position"] for g in body["items"]]
    assert positions == sorted(positions)
    assert positions[0] == 1
