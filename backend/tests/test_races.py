"""Tests for /races."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_races_filters_by_year_and_session_type(client: TestClient) -> None:
    response = client.get("/api/v1/races", params={"year": 2026, "session_type": "Race"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(r["year"] == 2026 and r["session_type"] == "Race" for r in body["items"])


def test_list_races_includes_circuit_name(client: TestClient) -> None:
    response = client.get(
        "/api/v1/races", params={"year": 2026, "session_type": "Race", "page_size": 1}
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["circuit_short_name"]


def test_list_races_sort_is_validated(client: TestClient) -> None:
    response = client.get("/api/v1/races", params={"sort": "bogus"})
    assert response.status_code == 422
