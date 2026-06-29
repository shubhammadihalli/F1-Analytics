"""Tests for /constructors."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_constructors_includes_driver_numbers(client: TestClient) -> None:
    response = client.get("/api/v1/constructors")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    mclaren = next(c for c in body["items"] if c["team_name"] == "McLaren")
    assert 1 in mclaren["driver_numbers"]
