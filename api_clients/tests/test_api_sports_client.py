"""Unit tests for APISportsClient's endpoint mapping and pagination handling."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
import respx

from api_clients.api_sports_client import API_SPORTS_BASE_URL, APISportsClient
from api_clients.exceptions import UnsupportedEndpointError


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[APISportsClient, None]:
    instance = APISportsClient(api_key="key123", cache_ttl_seconds=0, rate_limits=[])
    yield instance
    await instance.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_drivers_sends_api_key_header(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/drivers").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": [{"id": 1, "name": "Lewis Hamilton"}],
                "paging": {"current": 1, "total": 1},
            },
        )
    )
    df = await client.get_drivers(search="hamilton")
    assert route.calls.last.request.headers["x-apisports-key"] == "key123"
    assert df.loc[0, "name"] == "Lewis Hamilton"


@pytest.mark.asyncio
@respx.mock
async def test_get_positions_follows_pagination(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/rankings/races").mock(
        side_effect=[
            httpx.Response(
                200, json={"response": [{"position": 1}], "paging": {"current": 1, "total": 2}}
            ),
            httpx.Response(
                200, json={"response": [{"position": 2}], "paging": {"current": 2, "total": 2}}
            ),
        ]
    )
    df = await client.get_positions(race=12345)
    assert route.call_count == 2
    assert list(df["position"]) == [1, 2]


@pytest.mark.asyncio
async def test_get_weather_raises_unsupported(client: APISportsClient) -> None:
    with pytest.raises(UnsupportedEndpointError):
        await client.get_weather()


@pytest.mark.asyncio
@respx.mock
async def test_get_pit_stops_hits_pitstops_endpoint(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/pitstops").mock(
        return_value=httpx.Response(
            200,
            json={"response": [{"driver": "VER", "stops": 2}], "paging": {"current": 1, "total": 1}},
        )
    )
    df = await client.get_pit_stops(race=12345)
    assert route.called
    assert df.loc[0, "stops"] == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_laps_hits_fastestlaps_endpoint(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/rankings/fastestlaps").mock(
        return_value=httpx.Response(
            200, json={"response": [{"driver": "VER"}], "paging": {"current": 1, "total": 1}}
        )
    )
    await client.get_laps(race=12345)
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_get_sessions_hits_races_endpoint_with_season(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/races").mock(
        return_value=httpx.Response(
            200, json={"response": [{"id": 1}], "paging": {"current": 1, "total": 1}}
        )
    )
    await client.get_sessions(season=2024)
    assert route.calls.last.request.url.params["season"] == "2024"


@pytest.mark.asyncio
@respx.mock
async def test_get_results_queries_races_by_id(client: APISportsClient) -> None:
    route = respx.get(f"{API_SPORTS_BASE_URL}/races").mock(
        return_value=httpx.Response(
            200, json={"response": [{"id": 555, "status": "Finished"}], "paging": {"current": 1, "total": 1}}
        )
    )
    await client.get_results(race_id=555)
    assert route.calls.last.request.url.params["id"] == "555"


def test_requires_api_key() -> None:
    with pytest.raises(TypeError):
        APISportsClient()  # type: ignore[call-arg]
