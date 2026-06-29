"""Async client for the API-Sports Formula-1 API
(https://api-sports.io/documentation/formula-1/v1)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api_clients.base_client import BaseAPIClient
from api_clients.exceptions import UnsupportedEndpointError

API_SPORTS_BASE_URL = "https://v1.formula-1.api-sports.io"


class APISportsClient(BaseAPIClient):
    """Async client for API-Sports' Formula-1 API.

    Every response is wrapped in `{"response": [...], "paging": {"current",
    "total"}}`; `_fetch_dataframe` follows that pagination transparently so
    callers always get a fully materialized DataFrame. A `x-apisports-key`
    header is required on every request.
    """

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        cache_ttl_seconds: float = 60.0,
        rate_limits: list[tuple[int, float]] | None = None,
        base_url: str = API_SPORTS_BASE_URL,
    ) -> None:
        super().__init__(
            base_url,
            api_key=api_key,
            api_key_header="x-apisports-key",
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_limits=rate_limits or [(10, 1.0)],
        )

    async def get_sessions(self, *, season: int, **filters: Any) -> pd.DataFrame:
        """Fetch the race calendar (sessions) for a season."""
        return await self._fetch_dataframe("/races", {"season": season, **filters})

    async def get_drivers(self, **filters: Any) -> pd.DataFrame:
        """Fetch driver profiles, optionally filtered (e.g. `search="hamilton"`)."""
        return await self._fetch_dataframe("/drivers", filters)

    async def get_positions(self, *, race: int, **filters: Any) -> pd.DataFrame:
        """Fetch the per-driver classification/positions for a race."""
        return await self._fetch_dataframe("/rankings/races", {"race": race, **filters})

    async def get_laps(self, *, race: int, **filters: Any) -> pd.DataFrame:
        """Fetch fastest-lap rankings for a race."""
        return await self._fetch_dataframe("/rankings/fastestlaps", {"race": race, **filters})

    async def get_weather(self, **filters: Any) -> pd.DataFrame:
        """Not available: API-Sports' Formula-1 API has no weather endpoint."""
        raise UnsupportedEndpointError(
            "API-Sports Formula-1 API does not expose weather data; "
            "use OpenF1Client.get_weather instead."
        )

    async def get_pit_stops(self, *, race: int, **filters: Any) -> pd.DataFrame:
        """Fetch pit stop timing for every driver in a race."""
        return await self._fetch_dataframe("/pitstops", {"race": race, **filters})

    async def get_results(self, *, race_id: int, **filters: Any) -> pd.DataFrame:
        """Fetch the full result/classification for a single race."""
        return await self._fetch_dataframe("/races", {"id": race_id, **filters})

    async def _fetch_dataframe(self, path: str, params: dict[str, Any]) -> pd.DataFrame:
        rows = await self._get_all_pages(
            path,
            params,
            extract_items=lambda payload: payload.get("response", []),
            next_page_params=self._next_page_params,
        )
        return pd.DataFrame(rows)

    @staticmethod
    def _next_page_params(payload: dict[str, Any], params: dict[str, Any]) -> dict[str, Any] | None:
        paging = payload.get("paging") or {}
        current, total = paging.get("current", 1), paging.get("total", 1)
        if current >= total:
            return None
        return {**params, "page": current + 1}
