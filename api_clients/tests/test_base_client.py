"""Unit tests for BaseAPIClient's cross-cutting HTTP behaviour."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
import respx

from api_clients.base_client import BaseAPIClient
from api_clients.exceptions import (
    APIAuthenticationError,
    APIClientError,
    APIRateLimitError,
    APIResponseError,
)

BASE_URL = "https://example.test/v1"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[BaseAPIClient, None]:
    instance = BaseAPIClient(
        BASE_URL,
        api_key="secret",
        api_key_header="x-api-key",
        max_retries=3,
        backoff_factor=0.01,
        cache_ttl_seconds=5.0,
    )
    yield instance
    await instance.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_get_returns_parsed_json(client: BaseAPIClient) -> None:
    respx.get(f"{BASE_URL}/drivers").mock(
        return_value=httpx.Response(200, json=[{"driver_number": 1}])
    )
    result = await client._request("GET", "/drivers")
    assert result == [{"driver_number": 1}]


@pytest.mark.asyncio
@respx.mock
async def test_sends_api_key_header(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=[]))
    await client._request("GET", "/drivers")
    assert route.calls.last.request.headers["x-api-key"] == "secret"


@pytest.mark.asyncio
@respx.mock
async def test_caches_repeated_requests(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(
        return_value=httpx.Response(200, json=[{"driver_number": 1}])
    )
    await client._request("GET", "/drivers")
    await client._request("GET", "/drivers")
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_bypasses_cache_when_disabled(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=[]))
    await client._request("GET", "/drivers", use_cache=False)
    await client._request("GET", "/drivers", use_cache=False)
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_retries_transient_server_errors_then_succeeds(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=[{"driver_number": 1}])]
    )
    result = await client._request("GET", "/drivers")
    assert result == [{"driver_number": 1}]
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_exhausts_retries_and_raises(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(503))
    with pytest.raises(APIResponseError):
        await client._request("GET", "/drivers")
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_does_not_retry_client_errors(client: BaseAPIClient) -> None:
    route = respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(404))
    with pytest.raises(APIResponseError) as exc_info:
        await client._request("GET", "/drivers")
    assert exc_info.value.status_code == 404
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_maps_401_to_authentication_error(client: BaseAPIClient) -> None:
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(401))
    with pytest.raises(APIAuthenticationError):
        await client._request("GET", "/drivers")


@pytest.mark.asyncio
@respx.mock
async def test_maps_429_to_rate_limit_error(client: BaseAPIClient) -> None:
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(429))
    with pytest.raises(APIRateLimitError):
        await client._request("GET", "/drivers")


@pytest.mark.asyncio
@respx.mock
async def test_maps_connect_error(client: BaseAPIClient) -> None:
    respx.get(f"{BASE_URL}/drivers").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(APIClientError):
        await client._request("GET", "/drivers")


@pytest.mark.asyncio
async def test_get_all_pages_follows_pagination(client: BaseAPIClient) -> None:
    pages = {
        1: {"response": [{"id": 1}], "paging": {"current": 1, "total": 2}},
        2: {"response": [{"id": 2}], "paging": {"current": 2, "total": 2}},
    }

    async def fake_request(method: str, path: str, *, params=None, use_cache=True):
        return pages[params.get("page", 1)]

    client._request = fake_request  # type: ignore[method-assign]

    items = await client._get_all_pages(
        "/races",
        {"page": 1},
        extract_items=lambda payload: payload["response"],
        next_page_params=lambda payload, params: (
            {**params, "page": payload["paging"]["current"] + 1}
            if payload["paging"]["current"] < payload["paging"]["total"]
            else None
        ),
    )
    assert items == [{"id": 1}, {"id": 2}]
