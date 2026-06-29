"""Tests for /standings."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_driver_standings_ordered_by_position(client: TestClient) -> None:
    response = client.get("/api/v1/standings", params={"year": 2026, "type": "driver"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(s["type"] == "driver" for s in body)
    positions = [s["position"] for s in body]
    assert positions == sorted(positions)


def test_constructor_standings_ordered_by_position(client: TestClient) -> None:
    response = client.get("/api/v1/standings", params={"year": 2026, "type": "constructor"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(s["type"] == "constructor" and s["driver_number"] is None for s in body)
    positions = [s["position"] for s in body]
    assert positions == sorted(positions)


def test_standings_requires_year(client: TestClient) -> None:
    response = client.get("/api/v1/standings")
    assert response.status_code == 422
