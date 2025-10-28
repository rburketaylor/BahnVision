from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings


class CacheService:
    """Simple Redis-backed cache for JSON payloads."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Retrieve a JSON document and decode it."""
        payload = await self._client.get(key)
        if payload is None:
            return None
        return json.loads(payload)

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Serialize and store a JSON-compatible document."""
        encoded = json.dumps(value)
        if ttl_seconds and ttl_seconds > 0:
            await self._client.set(key, encoded, ex=ttl_seconds)
        else:
            await self._client.set(key, encoded)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)


@lru_cache
def get_redis_client() -> Redis:
    """Return a shared Redis client instance."""
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


def get_cache_service() -> CacheService:
    """FastAPI dependency hook for cache usage."""
    return CacheService(get_redis_client())
