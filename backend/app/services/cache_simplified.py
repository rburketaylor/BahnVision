from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache, wraps
from typing import Any, AsyncIterator, Callable, TypeVar

import valkey.asyncio as valkey

from app.core.config import get_settings

T = TypeVar("T")


@dataclass
class TTLConfig:
    """Centralized TTL configuration with validation."""

    def __init__(self) -> None:
        settings = get_settings()

        # Cache TTLs
        self.valkey_cache_ttl = settings.valkey_cache_ttl_seconds
        self.valkey_cache_ttl_not_found = settings.valkey_cache_ttl_not_found_seconds
        self.mvg_departures_cache_ttl = settings.mvg_departures_cache_ttl_seconds
        self.mvg_departures_cache_stale_ttl = settings.mvg_departures_cache_stale_ttl_seconds
        self.mvg_station_search_cache_ttl = settings.mvg_station_search_cache_ttl_seconds
        self.mvg_station_search_cache_stale_ttl = settings.mvg_station_search_cache_stale_ttl_seconds
        self.mvg_station_list_cache_ttl = settings.mvg_station_list_cache_ttl_seconds
        self.mvg_station_list_cache_stale_ttl = settings.mvg_station_list_cache_stale_ttl_seconds
        self.mvg_route_cache_ttl = settings.mvg_route_cache_ttl_seconds
        self.mvg_route_cache_stale_ttl = settings.mvg_route_cache_stale_ttl_seconds

        # Single flight configuration
        self.singleflight_lock_ttl = settings.cache_singleflight_lock_ttl_seconds
        self.singleflight_lock_wait = settings.cache_singleflight_lock_wait_seconds
        self.singleflight_retry_delay = settings.cache_singleflight_retry_delay_seconds

        # Circuit breaker configuration
        self.circuit_breaker_timeout = settings.cache_circuit_breaker_timeout_seconds

        # Validate all TTL values
        self._validate_ttls()

    def _validate_ttls(self) -> None:
        """Validate that all TTL values are non-negative."""
        for attr_name, value in self.__dict__.items():
            if 'ttl' in attr_name and isinstance(value, (int, float)):
                if value < 0:
                    raise ValueError(f"TTL value for {attr_name} cannot be negative: {value}")

    def get_effective_ttl(self, ttl_seconds: int | None) -> int | None:
        """Get the effective TTL, using default if none provided."""
        if ttl_seconds is not None:
            return ttl_seconds if ttl_seconds > 0 else None
        return self.valkey_cache_ttl if self.valkey_cache_ttl > 0 else None

    def get_effective_stale_ttl(self, stale_ttl_seconds: int | None) -> int | None:
        """Get the effective stale TTL, using default if none provided."""
        if stale_ttl_seconds is not None:
            return stale_ttl_seconds if stale_ttl_seconds > 0 else None
        return None  # No default stale TTL


class CircuitBreaker:
    """Simple circuit breaker decorator pattern."""

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

    def protect(self, func: Callable[T, Any]) -> Callable[T, Any]:
        """Decorator to protect a function from circuit breaker failures."""
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open():
                return None
            try:
                result = await func(*args, **kwargs)
                self.close()
                return result
            except Exception:
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
            except Exception:
                self.open()
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class SimpleFallbackStore:
    """Thread-safe in-memory fallback cache with automatic cleanup."""

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

            # Check if expired
            if expires_at is not None and expires_at <= time.monotonic():
                # Clean up expired entry
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
        self._fallback_store = SimpleFallbackStore()
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
        wrote_to_valkey = await self._set_to_valkey(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._set_to_valkey(stale_key, encoded, effective_stale_ttl)

        # Always store in fallback for resilience
        await self._fallback_store.set(key, encoded, effective_ttl)
        if effective_stale_ttl is not None:
            await self._fallback_store.set(stale_key, encoded, effective_stale_ttl)

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


def get_cache_service_original() -> "CacheService":
    """Factory for original cache service to maintain compatibility."""
    from .cache import CacheService
    return CacheService(get_valkey_client())