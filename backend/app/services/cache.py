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
    """Valkey-backed cache with stale fallbacks and single-flight guards."""

    _STALE_SUFFIX = ":stale"
    _LOCK_SUFFIX = ":lock"

    def __init__(self, client: valkey.Valkey) -> None:
        self._client = client
        self._fallback_store: dict[str, tuple[str, float | None]] = {}
        self._fallback_lock = asyncio.Lock()
        self._circuit_open_until = 0.0

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a JSON document and decode it."""
        payload = await self._get_from_valkey(key)
        if payload is not None:
            return json.loads(payload)
        fallback_payload = await self._get_fallback(key)
        if fallback_payload is None:
            return None
        return json.loads(fallback_payload)

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a stale JSON document stored for graceful fallbacks."""
        stale_key = f"{key}{self._STALE_SUFFIX}"
        payload = await self._get_from_valkey(stale_key)
        if payload is not None:
            return json.loads(payload)
        fallback_payload = await self._get_fallback(stale_key)
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
        wrote_valkey = False
        stale_key = f"{key}{self._STALE_SUFFIX}"

        if not self._is_circuit_open():
            try:
                if ttl_seconds and ttl_seconds > 0:
                    await self._client.set(key, encoded, ex=ttl_seconds)
                else:
                    await self._client.set(key, encoded)
                if stale_ttl_seconds is not None:
                    if stale_ttl_seconds > 0:
                        await self._client.set(stale_key, encoded, ex=stale_ttl_seconds)
                    else:
                        await self._client.set(stale_key, encoded)
                self._reset_circuit()
                wrote_valkey = True
            except Exception:
                self._open_circuit_breaker()

        ttl_for_fallback = ttl_seconds if ttl_seconds and ttl_seconds > 0 else None
        stale_ttl_for_fallback = (
            stale_ttl_seconds if stale_ttl_seconds and stale_ttl_seconds > 0 else None
        )

        # Always store a copy locally so circuit breaker + stale paths have data.
        await self._set_fallback(key, encoded, ttl_for_fallback)
        if stale_ttl_seconds is not None:
            await self._set_fallback(stale_key, encoded, stale_ttl_for_fallback)

        if wrote_valkey:
            return

    async def delete(self, key: str) -> None:
        if not self._is_circuit_open():
            try:
                await self._client.delete(key)
                await self._client.delete(f"{key}{self._STALE_SUFFIX}")
            except Exception:
                self._open_circuit_breaker()
        await self._delete_fallback(key)
        await self._delete_fallback(f"{key}{self._STALE_SUFFIX}")

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
                if self._is_circuit_open():
                    acquired = True
                    break
                try:
                    acquired = await self._client.set(
                        lock_key, "1", nx=True, ex=max(1, int(ttl_seconds))
                    )
                except Exception:
                    self._open_circuit_breaker()
                    acquired = True
                if acquired:
                    break
                await asyncio.sleep(retry_delay)
            if not acquired:
                raise TimeoutError(f"Timed out while acquiring cache lock for key '{key}'.")
            yield
        finally:
            if acquired and not self._is_circuit_open():
                try:
                    await self._client.delete(lock_key)
                except Exception:
                    self._open_circuit_breaker()

    async def _get_from_valkey(self, key: str) -> str | None:
        if self._is_circuit_open():
            return None
        try:
            payload = await self._client.get(key)
        except Exception:
            self._open_circuit_breaker()
            return None
        self._reset_circuit()
        return payload

    def _is_circuit_open(self) -> bool:
        return time.monotonic() < self._circuit_open_until

    def _open_circuit_breaker(self) -> None:
        timeout = get_settings().cache_circuit_breaker_timeout_seconds
        if timeout <= 0:
            timeout = 0
        self._circuit_open_until = time.monotonic() + timeout

    def _reset_circuit(self) -> None:
        self._circuit_open_until = 0.0

    async def _set_fallback(self, key: str, encoded: str, ttl_seconds: int | None) -> None:
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = time.monotonic() + ttl_seconds
        async with self._fallback_lock:
            self._fallback_store[key] = (encoded, expires_at)

    async def _get_fallback(self, key: str) -> str | None:
        async with self._fallback_lock:
            entry = self._fallback_store.get(key)
            if entry is None:
                return None
            encoded, expires_at = entry
        if expires_at is not None and expires_at <= time.monotonic():
            await self._delete_fallback(key)
            return None
        return encoded

    async def _delete_fallback(self, key: str) -> None:
        async with self._fallback_lock:
            self._fallback_store.pop(key, None)


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
