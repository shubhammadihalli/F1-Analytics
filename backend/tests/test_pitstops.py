"""Tests for /pit-stops."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_pit_stops_filters_by_session(client: TestClient) -> None:
    response = client.get("/api/v1/pit-stops", params={"session_key": 11234})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(p["session_key"] == 11234 for p in body["items"])
