"""Unit tests for AsyncRateLimiter."""

from __future__ import annotations

import time

import pytest

from api_clients.rate_limiter import AsyncRateLimiter


@pytest.mark.asyncio
async def test_allows_calls_up_to_the_limit_without_delay() -> None:
    limiter = AsyncRateLimiter(max_calls=3, period=1.0)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    assert time.monotonic() - start < 0.2


@pytest.mark.asyncio
async def test_blocks_until_window_clears() -> None:
    limiter = AsyncRateLimiter(max_calls=2, period=0.2)
    await limiter.acquire()
    await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.15


def test_rejects_non_positive_max_calls() -> None:
    with pytest.raises(ValueError):
        AsyncRateLimiter(max_calls=0, period=1.0)


def test_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError):
        AsyncRateLimiter(max_calls=1, period=0)
