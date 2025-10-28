from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator

import valkey.asyncio as valkey

from app.core.config import get_settings


class CacheService:
    """Simple Valkey-backed cache for JSON payloads."""

    _STALE_SUFFIX = ":stale"
    _LOCK_SUFFIX = ":lock"

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a JSON document and decode it."""
        payload = await self._client.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a stale JSON document stored for graceful fallbacks."""
        return await self.get_json(f"{key}{self._STALE_SUFFIX}")

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        stale_ttl_seconds: int | None = None,
    ) -> None:
        """Serialize and store a JSON-compatible document."""
        encoded = json.dumps(value)
        if ttl_seconds and ttl_seconds > 0:
            await self._client.set(key, encoded, ex=ttl_seconds)
        else:
            await self._client.set(key, encoded)
        if stale_ttl_seconds is not None:
            stale_key = f"{key}{self._STALE_SUFFIX}"
            if stale_ttl_seconds > 0:
                await self._client.set(stale_key, encoded, ex=stale_ttl_seconds)
            else:
                await self._client.set(stale_key, encoded)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    @asynccontextmanager
    async def single_flight(
        self,
        key: str,
        ttl_seconds: int,
        wait_timeout: float,
        retry_delay: float,
    ) -> AsyncIterator[None]:
        """Guard cache miss fills so only one worker refreshes a key."""
        lock_key = f"{key}{self._LOCK_SUFFIX}"
        deadline = time.monotonic() + wait_timeout
        acquired = False
        try:
            while time.monotonic() < deadline:
                acquired = await self._client.set(lock_key, "1", nx=True, ex=max(1, int(ttl_seconds)))
                if acquired:
                    break
                await asyncio.sleep(retry_delay)
            if not acquired:
                raise TimeoutError(f"Timed out while acquiring cache lock for key '{key}'.")
            yield
        finally:
            if acquired:
                await self._client.delete(lock_key)


@lru_cache
def get_valkey_client() -> valkey.Valkey:
    """Return a shared Valkey client instance."""
    settings = get_settings()
    return valkey.from_url(
        settings.valkey_url,
        encoding="utf-8",
        decode_responses=True,
    )


def get_cache_service() -> CacheService:
    """FastAPI dependency hook for cache usage."""
    return CacheService(get_valkey_client())
