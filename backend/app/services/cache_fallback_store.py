"""In-memory fallback store used by the cache service when Valkey is unavailable."""

from __future__ import annotations

import asyncio
import time
from typing import Any


class InMemoryFallbackStore:
    """
    Thread-safe in-memory fallback cache with automatic cleanup.

    This store relies on opportunistic cleanup to keep memory usage bounded.
    Consider adding a max-size or LRU policy if growth becomes a concern.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: str, ttl_seconds: int | None) -> None:
        """Store a value with optional TTL."""
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = time.monotonic() + ttl_seconds

        async with self._lock:
            self._store[key] = (value, expires_at)

    async def get(self, key: str) -> str | None:
        """Retrieve a value, returning None if expired or not found."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None

            value, expires_at = entry
            if expires_at is not None and expires_at <= time.monotonic():
                del self._store[key]
                return None

            return value

    async def delete(self, key: str) -> None:
        """Delete a value from the store."""
        async with self._lock:
            self._store.pop(key, None)

    async def cleanup_expired(self) -> None:
        """Remove all expired entries from the store."""
        current_time = time.monotonic()
        async with self._lock:
            expired_keys = [
                key for key, (_, expires_at) in self._store.items()
                if expires_at is not None and expires_at <= current_time
            ]
            for key in expired_keys:
                del self._store[key]


__all__ = ["InMemoryFallbackStore"]
