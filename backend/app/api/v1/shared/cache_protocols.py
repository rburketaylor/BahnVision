"""Protocol and result primitives for shared caching flows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.config import Settings
from app.services.cache import CacheService

T = TypeVar("T", bound=BaseModel)


class CacheResult(Generic[T]):
    """Container for cache lookup results with status metadata."""

    def __init__(
        self,
        data: T | None = None,
        status: str = "miss",
        headers: dict[str, str] | None = None,
    ):
        self.data = data
        self.status = status
        self.headers = headers or {}


class CacheRefreshProtocol(ABC, Generic[T]):
    """Base protocol for cache refresh operations."""

    @abstractmethod
    async def fetch_data(self, **kwargs: Any) -> T:
        """Fetch fresh data from the source service."""
        ...

    @abstractmethod
    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: T,
        settings: Settings,
    ) -> None:
        """Store data in cache with appropriate TTL settings."""
        ...

    @abstractmethod
    def cache_name(self) -> str:
        """Return the cache name for metrics."""
        ...

    @abstractmethod
    def get_model_class(self) -> type[T]:
        """Return the Pydantic model class for data validation."""
        ...


class MvgCacheProtocol(CacheRefreshProtocol[T]):
    """
    MVG cache protocol that reduces boilerplate by auto-configuring TTL settings.

    Subclasses only need to define fetch_data and the cache configuration properties.
    """

    @abstractmethod
    def get_ttl_setting_name(self) -> str:
        """Return the settings attribute name for TTL (e.g., 'mvg_departures_cache_ttl_seconds')."""
        ...

    @abstractmethod
    def get_stale_ttl_setting_name(self) -> str:
        """Return the settings attribute name for stale TTL (e.g., 'mvg_departures_cache_stale_ttl_seconds')."""
        ...

    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: T,
        settings: Settings,
    ) -> None:
        """Store data in cache with automatically configured TTL settings."""
        ttl_seconds = getattr(settings, self.get_ttl_setting_name())
        stale_ttl_seconds = getattr(settings, self.get_stale_ttl_setting_name())

        await cache.set_json(  # type: ignore
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=ttl_seconds,
            stale_ttl_seconds=stale_ttl_seconds,
        )


__all__ = ["CacheResult", "CacheRefreshProtocol", "MvgCacheProtocol"]
