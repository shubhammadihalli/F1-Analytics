"""Tests for /drivers and /driver/{id}."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_drivers_returns_paginated_page(client: TestClient) -> None:
    response = client.get("/api/v1/drivers", params={"page": 1, "page_size": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5
    assert body["total"] >= len(body["items"])


def test_list_drivers_filters_by_team(client: TestClient) -> None:
    response = client.get("/api/v1/drivers", params={"team_name": "McLaren"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(d["team_name"] == "McLaren" for d in body["items"])


def test_list_drivers_rejects_unknown_sort_field(client: TestClient) -> None:
    response = client.get("/api/v1/drivers", params={"sort": "not_a_real_field"})
    assert response.status_code == 422


def test_get_driver_returns_career_stats_consistent_with_standings(client: TestClient) -> None:
    response = client.get("/api/v1/driver/1")
    assert response.status_code == 200
    body = response.json()
    assert body["driver_number"] == 1
    assert body["full_name"] == "Lando NORRIS"
    assert body["career_stats"]["wins"] >= 0
    assert body["career_stats"]["races_entered"] >= body["career_stats"]["wins"]
    # Career wins/points should reconcile with the season standing they roll up into.
    season_standing = next(s for s in body["standings"] if s["year"] == 2026)
    assert season_standing["wins"] == body["career_stats"]["wins"]
    assert season_standing["points"] == body["career_stats"]["points_total"]


def test_get_driver_404_for_unknown_driver_number(client: TestClient) -> None:
    response = client.get("/api/v1/driver/999999")
    assert response.status_code == 404
    assert "999999" in response.json()["detail"]
