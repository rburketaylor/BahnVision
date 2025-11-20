from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, AsyncIterator

import valkey.asyncio as valkey

from app.core.config import get_settings
from app.services.cache_circuit_breaker import CircuitBreaker
from app.services.cache_fallback_store import InMemoryFallbackStore
from app.services.cache_ttl_config import TTLConfig


class SingleFlightLock:
    """Simplified single-flight lock with clear separation of concerns."""

    def __init__(self, client: valkey.Valkey, config: TTLConfig) -> None:
        self._client = client
        self._config = config

    @asynccontextmanager
    async def acquire(
        self,
        key: str,
        lock_ttl_seconds: int,
        wait_timeout: float,
        retry_delay: float,
    ) -> AsyncIterator[bool]:
        """Acquire a single-flight lock, yielding True if lock was acquired."""
        lock_key = f"{key}:lock"
        deadline = time.monotonic() + wait_timeout
        acquired = False

        try:
            # Try to acquire lock with retries
            while time.monotonic() < deadline:
                try:
                    # Try to set the lock atomically
                    acquired = await self._client.set(
                        lock_key, "1", nx=True, ex=max(1, int(lock_ttl_seconds))
                    )
                    if acquired:
                        break
                except Exception:
                    # If we can't acquire due to Valkey issues, allow the operation
                    acquired = True
                    break

                # Wait before retrying
                await asyncio.sleep(retry_delay)

            yield acquired

        finally:
            # Always try to clean up the lock
            if acquired:
                try:
                    await self._client.delete(lock_key)
                except Exception:
                    # Ignore cleanup errors
                    pass


class SimplifiedCacheService:
    """Simplified cache service with cleaner component separation."""

    _STALE_SUFFIX = ":stale"

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client
        self._config = TTLConfig()
        self._circuit_breaker = CircuitBreaker(self._config)
        self._fallback_store = InMemoryFallbackStore()
        self._single_flight = SingleFlightLock(client, self._config)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a JSON document and decode it."""
        # Try primary cache first
        payload = await self._get_from_valkey(key)
        if payload is not None:
            return json.loads(payload)

        # Fallback to in-memory cache
        fallback_payload = await self._fallback_store.get(key)
        if fallback_payload is None:
            return None

        return json.loads(fallback_payload)

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a stale JSON document stored for graceful fallbacks."""
        stale_key = f"{key}{self._STALE_SUFFIX}"

        # Try primary cache first
        payload = await self._get_from_valkey(stale_key)
        if payload is not None:
            return json.loads(payload)

        # Fallback to in-memory cache
        fallback_payload = await self._fallback_store.get(stale_key)
        if fallback_payload is None:
            return None

        return json.loads(fallback_payload)

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        stale_ttl_seconds: int | None = None,
    ) -> None:
        """Serialize and store a JSON-compatible document."""
        encoded = json.dumps(value)
        stale_key = f"{key}{self._STALE_SUFFIX}"

        # Get effective TTLs
        effective_ttl = self._config.get_effective_ttl(ttl_seconds)
        effective_stale_ttl = self._config.get_effective_stale_ttl(stale_ttl_seconds)

        # Try to store in primary cache
        await self._set_to_valkey(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._set_to_valkey(stale_key, encoded, effective_stale_ttl)

        # Always store in fallback for resilience
        await self._fallback_store.set(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._fallback_store.set(stale_key, encoded, effective_stale_ttl)
        # Opportunistic cleanup to prevent unbounded growth
        await self._fallback_store.cleanup_expired()

    async def delete(self, key: str, *, remove_stale: bool = False) -> None:
        """Remove a cache entry, optionally clearing the stale backup."""
        stale_key = f"{key}{self._STALE_SUFFIX}"

        # Try to delete from primary cache
        if not self._circuit_breaker.is_open():
            try:
                if remove_stale:
                    await self._client.delete(key, stale_key)
                else:
                    await self._client.delete(key)
            except Exception:
                self._circuit_breaker.open()

        # Always delete from fallback
        await self._fallback_store.delete(key)
        if remove_stale:
            await self._fallback_store.delete(stale_key)
        # Opportunistic cleanup to prevent unbounded growth
        await self._fallback_store.cleanup_expired()

    @asynccontextmanager
    async def single_flight(
        self,
        key: str,
        ttl_seconds: int,
        wait_timeout: float,
        retry_delay: float,
    ) -> AsyncIterator[None]:
        """Guard cache miss fills so only one worker refreshes a key."""
        # If circuit breaker is open, allow operation without lock
        if self._circuit_breaker.is_open():
            yield
            return

        # Acquire single-flight lock
        async with self._single_flight.acquire(
            key, ttl_seconds, wait_timeout, retry_delay
        ) as acquired:
            if not acquired:
                raise TimeoutError(f"Timed out while acquiring cache lock for key '{key}'.")
            yield

    async def _get_from_valkey(self, key: str) -> str | None:
        """Get value from Valkey with circuit breaker protection."""
        @self._circuit_breaker.protect
        async def _get() -> str | None:
            return await self._client.get(key)

        return await _get()

    async def _set_to_valkey(self, key: str, value: str, ttl_seconds: int | None) -> bool:
        """Set value in Valkey with circuit breaker protection."""
        @self._circuit_breaker.protect
        async def _set() -> bool:
            if ttl_seconds and ttl_seconds > 0:
                await self._client.set(key, value, ex=ttl_seconds)
            else:
                await self._client.set(key, value)
            return True

        result = await _set()
        return result is not None


@lru_cache
def get_valkey_client() -> valkey.Valkey:
    """Return a shared Valkey client instance."""
    settings = get_settings()
    return valkey.from_url(
        settings.valkey_url,
        encoding="utf-8",
        decode_responses=True,
    )


def get_cache_service() -> SimplifiedCacheService:
    """FastAPI dependency hook for cache usage."""
    return SimplifiedCacheService(get_valkey_client())


# For backward compatibility, alias the simplified service as CacheService
CacheService = SimplifiedCacheService
