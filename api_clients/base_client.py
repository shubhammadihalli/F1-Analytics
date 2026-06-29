"""Shared async HTTP client: retries, backoff, timeouts, rate limiting,
caching, pagination, and exception translation for all F1 data clients."""

from __future__ import annotations

import time
from typing import Any, Callable, Self

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from api_clients.exceptions import (
    APIAuthenticationError,
    APIConnectionError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
)
from api_clients.rate_limiter import AsyncRateLimiter
from utils.logger import get_logger

JSONType = list[dict[str, Any]] | dict[str, Any]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, APIRateLimitError)):
        return True
    if isinstance(exc, APIResponseError):
        return exc.status_code >= 500
    return False


class _TTLCache:
    """Minimal in-process TTL cache keyed by request signature."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, JSONType]] = {}

    def get(self, key: str) -> JSONType | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: JSONType) -> None:
        if self._ttl <= 0:
            return
        self._store[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        self._store.clear()


class BaseAPIClient:
    """Reusable async REST client for Formula 1 data providers.

    Subclasses supply `base_url` and authentication placement; this class
    owns the cross-cutting concerns: timeouts, retries with exponential
    backoff, multi-window rate limiting, response caching, and translation of
    transport/HTTP failures into the `api_clients.exceptions` hierarchy.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        api_key_header: str | None = None,
        api_key_scheme: str | None = None,
        api_key_param: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        rate_limits: list[tuple[int, float]] | None = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._api_key_param = api_key_param
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._cache = _TTLCache(cache_ttl_seconds)
        self._rate_limiters = [
            AsyncRateLimiter(max_calls, period) for max_calls, period in (rate_limits or [])
        ]
        self._logger = get_logger(self.__class__.__module__)

        headers = {"Accept": "application/json"}
        if api_key and api_key_header:
            headers[api_key_header] = f"{api_key_scheme} {api_key}" if api_key_scheme else api_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout),
            headers=headers,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def clear_cache(self) -> None:
        self._cache.clear()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> JSONType:
        params = self._with_api_key_param(params or {})
        cache_key = self._cache_key(method, path, params)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._logger.debug("cache hit for %s %s params=%s", method, path, params)
                return cached

        for limiter in self._rate_limiters:
            await limiter.acquire()

        data = await self._send_with_retries(method, path, params)

        if use_cache:
            self._cache.set(cache_key, data)
        return data

    async def _send_with_retries(self, method: str, path: str, params: dict[str, Any]) -> JSONType:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._backoff_factor, min=self._backoff_factor, max=30),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                self._logger.info("%s %s params=%s", method, path, params)
                return await self._send_once(method, path, params)
        raise AssertionError("unreachable: AsyncRetrying always raises or returns")

    async def _send_once(self, method: str, path: str, params: dict[str, Any]) -> JSONType:
        try:
            response = await self._client.request(method, path, params=params)
        except httpx.TimeoutException as exc:
            self._logger.warning("timeout calling %s %s: %s", method, path, exc)
            raise APITimeoutError(f"Timed out calling {method} {path}") from exc
        except httpx.TransportError as exc:
            self._logger.warning("connection error calling %s %s: %s", method, path, exc)
            raise APIConnectionError(f"Connection error calling {method} {path}") from exc
        return self._raise_for_status(response)

    def _raise_for_status(self, response: httpx.Response) -> JSONType:
        if response.status_code in (401, 403):
            raise APIAuthenticationError(
                f"Authentication failed ({response.status_code}) for {response.request.url}"
            )
        if response.status_code == 429:
            raise APIRateLimitError(f"Rate limited (429) for {response.request.url}")
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise APIResponseError(
                f"Request to {response.request.url} failed with {response.status_code}",
                status_code=response.status_code,
                payload=payload,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise APIResponseError(
                f"Non-JSON response from {response.request.url}",
                status_code=response.status_code,
                payload=response.text,
            ) from exc

    async def _get_all_pages(
        self,
        path: str,
        params: dict[str, Any],
        *,
        extract_items: Callable[[dict[str, Any]], list[dict[str, Any]]],
        next_page_params: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None],
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch every page of a dict-enveloped paginated endpoint and flatten the results.

        `extract_items` pulls the row list out of one page's payload.
        `next_page_params` inspects that payload and returns the params for
        the next request, or `None` once there are no more pages.
        """
        items: list[dict[str, Any]] = []
        current_params: dict[str, Any] | None = dict(params)
        while current_params is not None:
            page = await self._request("GET", path, params=current_params, use_cache=use_cache)
            assert isinstance(page, dict), "_get_all_pages requires a dict-enveloped response"
            items.extend(extract_items(page))
            current_params = next_page_params(page, current_params)
        return items

    def _with_api_key_param(self, params: dict[str, Any]) -> dict[str, Any]:
        if self._api_key and self._api_key_param:
            return {**params, self._api_key_param: self._api_key}
        return params

    @staticmethod
    def _cache_key(method: str, path: str, params: dict[str, Any]) -> str:
        normalized = sorted((str(k), str(v)) for k, v in params.items())
        return f"{method}:{path}:{normalized}"
