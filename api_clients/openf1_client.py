"""Async client for the OpenF1 API (https://openf1.org)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api_clients.base_client import BaseAPIClient
from api_clients.exceptions import APIResponseError

OPENF1_BASE_URL = "https://api.openf1.org/v1"


class OpenF1Client(BaseAPIClient):
    """Async client for OpenF1's real-time and historical F1 telemetry data.

    Historical data (2023 onward) needs no API key. Live data during an
    active session requires a sponsor-tier bearer token passed as `api_key`.
    The free tier is rate limited to 3 requests/second *and* 30 requests/
    minute; both windows are enforced client-side by default.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        cache_ttl_seconds: float = 60.0,
        rate_limits: list[tuple[int, float]] | None = None,
        base_url: str = OPENF1_BASE_URL,
    ) -> None:
        super().__init__(
            base_url,
            api_key=api_key,
            api_key_header="Authorization" if api_key else None,
            api_key_scheme="Bearer" if api_key else None,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            cache_ttl_seconds=cache_ttl_seconds,
            rate_limits=rate_limits or [(3, 1.0), (30, 60.0)],
        )

    async def get_sessions(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch session metadata (practice/qualifying/race) matching `filters`."""
        return await self._fetch_dataframe("/sessions", params, filters)

    async def get_drivers(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch driver info (number, name, team) for a session or meeting."""
        return await self._fetch_dataframe("/drivers", params, filters)

    async def get_positions(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch driver position-over-time data for a session."""
        return await self._fetch_dataframe("/position", params, filters)

    async def get_laps(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch lap-by-lap timing data for a session."""
        return await self._fetch_dataframe("/laps", params, filters)

    async def get_weather(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch track/air weather samples for a session."""
        return await self._fetch_dataframe("/weather", params, filters)

    async def get_pit_stops(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch pit lane entry/duration data for a session."""
        return await self._fetch_dataframe("/pit", params, filters)

    async def get_results(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch final classification for a session."""
        return await self._fetch_dataframe("/session_result", params, filters)

    async def get_race_control(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch race control messages (flags, safety car, incidents) for a session."""
        return await self._fetch_dataframe("/race_control", params, filters)

    async def get_team_radio(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch team radio message metadata (driver, timestamp, recording URL) for a session."""
        return await self._fetch_dataframe("/team_radio", params, filters)

    async def get_car_data(
        self, *, params: dict[str, Any] | None = None, **filters: Any
    ) -> pd.DataFrame:
        """Fetch car telemetry (speed/throttle/brake/RPM/gear/DRS) for a session.

        OpenF1 rejects whole-session requests as "too much data at once";
        callers must pass `driver_number` to scope the request to one car.
        """
        return await self._fetch_dataframe("/car_data", params, filters)

    async def _fetch_dataframe(
        self, path: str, params: dict[str, Any] | None, filters: dict[str, Any]
    ) -> pd.DataFrame:
        # `params` accepts OpenF1's comparison-operator query keys (e.g.
        # "lap_number<=3") that aren't valid Python keyword arguments.
        merged = {**(params or {}), **filters}
        try:
            rows = await self._request("GET", path, params=merged)
        except APIResponseError as exc:
            # OpenF1 returns 404 "No results found" instead of [] when a
            # session has no matching rows (e.g. a cancelled session).
            if exc.status_code == 404:
                return pd.DataFrame()
            raise
        return pd.DataFrame(rows if isinstance(rows, list) else [rows])
