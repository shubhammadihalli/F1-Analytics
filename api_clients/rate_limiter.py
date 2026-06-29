"""Async sliding-window rate limiter shared by all api_clients clients."""

from __future__ import annotations

import asyncio
import time
from collections import deque


class AsyncRateLimiter:
    """Caps calls to `max_calls` within any rolling `period`-second window.

    Callers `await acquire()` immediately before issuing a request. The
    coroutine returns immediately while under the limit and otherwise sleeps
    just long enough for the oldest call in the window to expire.
    """

    def __init__(self, max_calls: int, period: float = 1.0) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be a positive integer")
        if period <= 0:
            raise ValueError("period must be a positive number of seconds")
        self._max_calls = max_calls
        self._period = period
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._period:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return
                sleep_for = self._period - (now - self._timestamps[0])
                await asyncio.sleep(max(sleep_for, 0))

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None
 