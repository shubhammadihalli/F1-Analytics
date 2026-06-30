"""Unit tests for OpenF1Client's endpoint-to-method mapping."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import pandas as pd
import pytest
import pytest_asyncio
import respx

from api_clients.openf1_client import OPENF1_BASE_URL, OpenF1Client


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[OpenF1Client, None]:
    instance = OpenF1Client(cache_ttl_seconds=0, rate_limits=[])
    yield instance
    await instance.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_laps_returns_dataframe(client: OpenF1Client) -> None:
    respx.get(f"{OPENF1_BASE_URL}/laps").mock(
        return_value=httpx.Response(
            200, json=[{"driver_number": 44, "lap_number": 1, "lap_duration": 91.2}]
        )
    )
    df = await client.get_laps(session_key=9472, driver_number=44)
    assert isinstance(df, pd.DataFrame)
    assert df.loc[0, "lap_duration"] == 91.2


@pytest.mark.asyncio
@respx.mock
async def test_get_weather_returns_empty_dataframe_when_no_data(client: OpenF1Client) -> None:
    respx.get(f"{OPENF1_BASE_URL}/weather").mock(return_value=httpx.Response(200, json=[]))
    df = await client.get_weather(session_key=9472)
    assert df.empty


@pytest.mark.asyncio
@respx.mock
async def test_get_results_hits_session_result_endpoint(client: OpenF1Client) -> None:
    route = respx.get(f"{OPENF1_BASE_URL}/session_result").mock(
        return_value=httpx.Response(200, json=[{"position": 1, "driver_number": 1}])
    )
    df = await client.get_results(session_key=9472)
    assert route.called
    assert df.loc[0, "position"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_params_dict_supports_comparison_operator_keys(client: OpenF1Client) -> None:
    route = respx.get(f"{OPENF1_BASE_URL}/laps").mock(return_value=httpx.Response(200, json=[]))
    await client.get_laps(params={"lap_number<=": 3}, driver_number=44)
    sent_params = route.calls.last.request.url.params
    assert sent_params["lap_number<="] == "3"
    assert sent_params["driver_number"] == "44"


@pytest.mark.asyncio
@respx.mock
async def test_authorization_header_sent_when_api_key_provided() -> None:
    client = OpenF1Client(api_key="token123", cache_ttl_seconds=0, rate_limits=[])
    route = respx.get(f"{OPENF1_BASE_URL}/sessions").mock(return_value=httpx.Response(200, json=[]))
    await client.get_sessions()
    assert route.calls.last.request.headers["Authorization"] == "Bearer token123"
    await client.aclose()


@pytest.mark.parametrize(
    ("method_name", "path"),
    [
        ("get_sessions", "/sessions"),
        ("get_drivers", "/drivers"),
        ("get_positions", "/position"),
        ("get_laps", "/laps"),
        ("get_weather", "/weather"),
        ("get_pit_stops", "/pit"),
        ("get_results", "/session_result"),
        ("get_race_control", "/race_control"),
        ("get_team_radio", "/team_radio"),
        ("get_car_data", "/car_data"),
        ("get_stints", "/stints"),
        ("get_starting_grid", "/starting_grid"),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_each_method_hits_expected_endpoint(client: OpenF1Client, method_name: str, path: str) -> None:
    route = respx.get(f"{OPENF1_BASE_URL}{path}").mock(return_value=httpx.Response(200, json=[]))
    method = getattr(client, method_name)
    result = await method()
    assert route.called
    assert isinstance(result, pd.DataFrame)
