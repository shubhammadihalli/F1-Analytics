"""Tests for /telemetry."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_telemetry_requires_session_key_and_driver_number(client: TestClient) -> None:
    assert client.get("/api/v1/telemetry").status_code == 422
    assert client.get("/api/v1/telemetry", params={"session_key": 11234}).status_code == 422
    assert client.get("/api/v1/telemetry", params={"driver_number": 63}).status_code == 422


def test_list_telemetry_returns_samples_for_one_driver(client: TestClient) -> None:
    response = client.get(
        "/api/v1/telemetry", params={"session_key": 11234, "driver_number": 63, "page_size": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert all(
        sample["session_key"] == 11234 and sample["driver_number"] == 63
        for sample in body["items"]
    )
