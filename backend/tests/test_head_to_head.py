"""Tests for /head-to-head."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_head_to_head_compares_two_real_drivers(client: TestClient) -> None:
    response = client.get("/api/v1/head-to-head", params={"driver1": 1, "driver2": 3, "year": 2026})
    assert response.status_code == 200
    body = response.json()
    assert body["driver1"]["driver_number"] == 1
    assert body["driver2"]["driver_number"] == 3
    assert body["sessions_compared"] == len(body["sessions"])
    assert body["driver1_ahead"] + body["driver2_ahead"] <= body["sessions_compared"]


def test_head_to_head_rejects_comparing_a_driver_to_themselves(client: TestClient) -> None:
    response = client.get("/api/v1/head-to-head", params={"driver1": 1, "driver2": 1})
    assert response.status_code == 422


def test_head_to_head_404_for_unknown_driver(client: TestClient) -> None:
    response = client.get("/api/v1/head-to-head", params={"driver1": 1, "driver2": 999999})
    assert response.status_code == 404
