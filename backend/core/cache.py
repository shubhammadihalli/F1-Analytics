"""In-process TTL cache for read-heavy GET endpoints.

A single dict-backed cache is enough at this scale: the API runs as one
process per deployment, and responses only need to stay fresh relative to
the ETL's own refresh cadence (minutes), not real time.
"""

from __future__ import annotations

import json
import time
from typing import Any

from backend.core.config import settings


class TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        self._store.clear()


def make_key(prefix: str, **params: Any) -> str:
    """Build a stable cache key from an endpoint name and its query parameters."""
    return f"{prefix}:{json.dumps(params, sort_keys=True, default=str)}"


response_cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
