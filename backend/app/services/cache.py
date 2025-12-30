"""
Cache service with resilience patterns.

Provides distributed caching via Valkey with:
- Circuit breaker for graceful degradation when Valkey is unavailable
- In-memory fallback cache for resilience during outages
- Single-flight locking to prevent cache stampedes
- Stale data fallback for improved availability
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from functools import lru_cache, wraps
from typing import Any, AsyncIterator, Callable, TypeVar

import valkey.asyncio as valkey

from app.core.config import get_settings
from app.core.metrics import record_cache_event

logger = logging.getLogger(__name__)
T = TypeVar("T")


# =============================================================================
# TTL Configuration
# =============================================================================


class TTLConfig:
    """Centralized TTL configuration with validation."""

    def __init__(self) -> None:
        settings = get_settings()

        self.valkey_cache_ttl = settings.valkey_cache_ttl_seconds
        self.valkey_cache_ttl_not_found = settings.valkey_cache_ttl_not_found_seconds
        self.circuit_breaker_timeout = settings.cache_circuit_breaker_timeout_seconds

        self._validate_ttls()

    def _validate_ttls(self) -> None:
        """Validate that all TTL values are non-negative."""
        for attr_name, value in self.__dict__.items():
            if "ttl" in attr_name and isinstance(value, (int, float)) and value < 0:
                raise ValueError(
                    f"TTL value for {attr_name} cannot be negative: {value}"
                )

    def get_effective_ttl(self, ttl_seconds: int | None) -> int | None:
        """Get the effective TTL, using default if none provided."""
        if ttl_seconds is not None:
            return ttl_seconds if ttl_seconds > 0 else None
        return self.valkey_cache_ttl if self.valkey_cache_ttl > 0 else None

    def get_effective_stale_ttl(self, stale_ttl_seconds: int | None) -> int | None:
        """Get the effective stale TTL, using default if none provided."""
        if stale_ttl_seconds is not None:
            return stale_ttl_seconds if stale_ttl_seconds > 0 else None
        return None


# =============================================================================
# Circuit Breaker
# =============================================================================


class CircuitBreaker:
    """
    Circuit breaker for cache operations.

    When Valkey becomes unavailable, the circuit opens and operations
    fail fast, falling back to the in-memory cache instead.
    """

    def __init__(self, config: TTLConfig) -> None:
        self._config = config
        self._open_until = 0.0

    def is_open(self) -> bool:
        """Check if the circuit breaker is currently open."""
        return time.monotonic() < self._open_until

    def open(self) -> None:
        """Open the circuit breaker for the configured timeout."""
        self._open_until = time.monotonic() + self._config.circuit_breaker_timeout

    def close(self) -> None:
        """Close the circuit breaker immediately."""
        self._open_until = 0.0

    def protect(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to protect a function with circuit breaker logic."""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open():
                return None
            try:
                result = await func(*args, **kwargs)
                self.close()
                return result
            except Exception as exc:
                logger.warning(
                    "Circuit breaker opened for %s", func.__name__, exc_info=exc
                )
                self.open()
                return None

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open():
                return None
            try:
                result = func(*args, **kwargs)
                self.close()
                return result
            except Exception as exc:
                logger.warning(
                    "Circuit breaker opened for %s", func.__name__, exc_info=exc
                )
                self.open()
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


# =============================================================================
# Fallback Cache
# =============================================================================


class FallbackCache:
    """
    In-memory fallback cache used when Valkey is unavailable.

    Thread-safe with automatic cleanup of expired entries.
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
                key
                for key, (_, expires_at) in self._store.items()
                if expires_at is not None and expires_at <= current_time
            ]
            for key in expired_keys:
                del self._store[key]


# =============================================================================
# Single-Flight Lock
# =============================================================================


class SingleFlightLock:
    """
    Distributed lock for cache stampede protection.

    Ensures only one worker refreshes a cache key at a time,
    preventing thundering herd problems during cache misses.
    """

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client

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
            while time.monotonic() < deadline:
                try:
                    acquired = await self._client.set(
                        lock_key, "1", nx=True, ex=max(1, int(lock_ttl_seconds))
                    )
                    if acquired:
                        break
                except Exception:
                    # If Valkey is unavailable, allow the operation to proceed
                    acquired = True
                    break

                await asyncio.sleep(retry_delay)

            yield acquired

        finally:
            if acquired:
                try:
                    await self._client.delete(lock_key)
                except Exception:
                    pass


# =============================================================================
# Cache Service
# =============================================================================


class CacheService:
    """
    Cache service with resilience patterns.

    Provides JSON caching with:
    - Primary storage in Valkey
    - Circuit breaker for graceful degradation
    - In-memory fallback during outages
    - Stale data support for improved availability
    - Single-flight locking to prevent stampedes
    """

    _STALE_SUFFIX = ":stale"

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client
        self._config = TTLConfig()
        self._circuit_breaker = CircuitBreaker(self._config)
        self._fallback = FallbackCache()
        self._single_flight = SingleFlightLock(client)

    async def get(self, key: str) -> str | None:
        """Retrieve a raw string value from the cache.

        Used for simple key-value storage like trip deduplication.
        Falls back to in-memory cache if Valkey is unavailable.
        """
        value = await self._get_from_valkey(key)
        if value is not None:
            record_cache_event("raw", "hit")
            return value
        fallback = await self._fallback.get(key)
        record_cache_event("raw", "miss")
        return fallback

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a raw string value in the cache.

        Used for simple key-value storage like trip deduplication.
        Also stores in fallback cache for resilience.
        """
        effective_ttl = self._config.get_effective_ttl(ttl_seconds)
        await self._set_to_valkey(key, value, effective_ttl)
        await self._fallback.set(key, value, effective_ttl)

    async def mget(self, keys: list[str]) -> dict[str, str | None]:
        """Retrieve multiple raw string values from the cache in a single call.

        Uses Valkey's MGET for efficient batch lookups.
        Falls back to in-memory cache for keys not found in Valkey.

        Args:
            keys: List of cache keys to retrieve

        Returns:
            Dict mapping keys to their values (None if not found)
        """
        if not keys:
            return {}

        result: dict[str, str | None] = {k: None for k in keys}

        # Try Valkey first
        if not self._circuit_breaker.is_open():
            try:
                values = await self._client.mget(keys)
                for key, value in zip(keys, values):
                    if value is not None:
                        result[key] = value
                self._circuit_breaker.close()
            except Exception as exc:
                logger.warning("MGET failed, falling back: %s", exc)
                self._circuit_breaker.open()

        # Fall back to in-memory for any missing keys
        missing_keys = [k for k, v in result.items() if v is None]
        for key in missing_keys:
            fallback_value = await self._fallback.get(key)
            if fallback_value is not None:
                result[key] = fallback_value

        return result

    async def mget_json(self, keys: list[str]) -> dict[str, Any | None]:
        """Retrieve multiple JSON documents and decode them.

        Args:
            keys: List of cache keys to retrieve

        Returns:
            Dict mapping keys to their decoded values (None if not found or invalid)
        """
        raw_values = await self.mget(keys)
        result = {}

        for key, value in raw_values.items():
            if value is not None:
                try:
                    result[key] = json.loads(value)
                    record_cache_event("json", "hit")
                except json.JSONDecodeError:
                    logger.warning("Failed to decode JSON for key %s", key)
                    result[key] = None
                    record_cache_event("json", "miss")
            else:
                result[key] = None
                record_cache_event("json", "miss")

        return result

    async def mset(
        self,
        items: dict[str, str],
        ttl_seconds: int | None = None,
    ) -> None:
        """Store multiple raw string values in the cache in a single call.

        Uses Valkey's pipelining for efficient batch writes.

        Args:
            items: Dict mapping keys to values to store
            ttl_seconds: Optional TTL for all keys
        """
        if not items:
            return

        effective_ttl = self._config.get_effective_ttl(ttl_seconds)

        # Write to Valkey using pipeline
        if not self._circuit_breaker.is_open():
            try:
                pipe = self._client.pipeline()
                for key, value in items.items():
                    if effective_ttl and effective_ttl > 0:
                        pipe.set(key, value, ex=effective_ttl)
                    else:
                        pipe.set(key, value)
                await pipe.execute()
                self._circuit_breaker.close()
            except Exception as exc:
                logger.warning("MSET pipeline failed: %s", exc)
                self._circuit_breaker.open()

        # Always store in fallback for resilience
        for key, value in items.items():
            await self._fallback.set(key, value, effective_ttl)

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a JSON document and decode it."""
        payload = await self._get_from_valkey(key)
        if payload is not None:
            record_cache_event("json", "hit")
            return json.loads(payload)

        fallback_payload = await self._fallback.get(key)
        record_cache_event("json", "miss")
        if fallback_payload is None:
            return None
        return json.loads(fallback_payload)

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a stale JSON document stored for graceful fallbacks."""
        stale_key = f"{key}{self._STALE_SUFFIX}"

        payload = await self._get_from_valkey(stale_key)
        if payload is not None:
            record_cache_event("stale", "hit")
            return json.loads(payload)

        fallback_payload = await self._fallback.get(stale_key)
        record_cache_event("stale", "miss")
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

        effective_ttl = self._config.get_effective_ttl(ttl_seconds)
        effective_stale_ttl = self._config.get_effective_stale_ttl(stale_ttl_seconds)

        await self._set_to_valkey(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._set_to_valkey(stale_key, encoded, effective_stale_ttl)

        # Always store in fallback for resilience
        await self._fallback.set(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._fallback.set(stale_key, encoded, effective_stale_ttl)
        await self._fallback.cleanup_expired()

    async def delete(self, key: str, *, remove_stale: bool = False) -> None:
        """Remove a cache entry, optionally clearing the stale backup."""
        stale_key = f"{key}{self._STALE_SUFFIX}"

        if not self._circuit_breaker.is_open():
            try:
                if remove_stale:
                    await self._client.delete(key, stale_key)
                else:
                    await self._client.delete(key)
            except Exception:
                self._circuit_breaker.open()

        await self._fallback.delete(key)
        if remove_stale:
            await self._fallback.delete(stale_key)
        await self._fallback.cleanup_expired()

    @asynccontextmanager
    async def single_flight(
        self,
        key: str,
        ttl_seconds: int,
        wait_timeout: float,
        retry_delay: float,
    ) -> AsyncIterator[None]:
        """Guard cache miss fills so only one worker refreshes a key."""
        if self._circuit_breaker.is_open():
            yield
            return

        async with self._single_flight.acquire(
            key, ttl_seconds, wait_timeout, retry_delay
        ) as acquired:
            if not acquired:
                raise TimeoutError(
                    f"Timed out while acquiring cache lock for key '{key}'."
                )
            yield

    async def _get_from_valkey(self, key: str) -> str | None:
        """Get value from Valkey with circuit breaker protection."""

        @self._circuit_breaker.protect
        async def _get() -> str | None:
            return await self._client.get(key)

        return await _get()

    async def _set_to_valkey(
        self, key: str, value: str, ttl_seconds: int | None
    ) -> bool:
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


# =============================================================================
# Factory Functions
# =============================================================================


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


__all__ = ["CacheService", "get_cache_service", "get_valkey_client", "TTLConfig"]
