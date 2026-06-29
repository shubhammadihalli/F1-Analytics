"""Tests for /weather."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_weather_filters_by_session(client: TestClient) -> None:
    response = client.get("/api/v1/weather", params={"session_key": 11234, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(sample["session_key"] == 11234 for sample in body["items"])
