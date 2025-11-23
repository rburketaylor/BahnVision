"""Thin orchestrator that wires cache protocols to shared flows."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi import BackgroundTasks, Response
from pydantic import BaseModel

from app.core.config import Settings
from app.services.cache import CacheService

from .cache_flow import (
    execute_background_refresh,
    execute_cache_refresh,
    handle_cache_errors,
    handle_cache_lookup,
)
from .cache_protocols import CacheRefreshProtocol

T = TypeVar("T", bound=BaseModel)


class CacheManager(Generic[T]):
    """High-level cache manager that orchestrates lookup, refresh, and error handling."""

    def __init__(
        self,
        protocol: CacheRefreshProtocol[T],
        cache: CacheService,
        cache_name: str,
    ):
        self.protocol = protocol
        self.cache = cache
        self.cache_name = cache_name

    async def get_cached_data(
        self,
        cache_key: str,
        response: Response,
        background_tasks: BackgroundTasks,
        settings: Settings,
        allow_stale: bool = True,
        **fetch_kwargs: Any,
    ) -> T:
        """Get data from cache with automatic refresh and error handling."""
        cache_result = await handle_cache_lookup(
            cache=self.cache,
            cache_key=cache_key,
            cache_name=self.cache_name,
            response=response,
            background_tasks=background_tasks,
            refresh_func=execute_background_refresh,
            refresh_kwargs={
                "protocol": self.protocol,
                "cache": self.cache,
                "cache_key": cache_key,
                "settings": settings,
                **fetch_kwargs,
            },
            model_class=self.protocol.get_model_class(),
            allow_stale=allow_stale,
        )

        if cache_result.data is not None:
            for header, value in cache_result.headers.items():
                response.headers[header] = value
            return cache_result.data

        try:
            fresh_data = await execute_cache_refresh(
                protocol=self.protocol,
                cache=self.cache,
                cache_key=cache_key,
                settings=settings,
                **fetch_kwargs,
            )
            response.headers["X-Cache-Status"] = "miss"
            return fresh_data

        except Exception as exc:
            stale_result = await handle_cache_errors(
                cache=self.cache,
                cache_key=cache_key,
                cache_name=self.cache_name,
                exc=exc,
                model_class=self.protocol.get_model_class(),
                allow_stale_fallback=allow_stale,
            )

            if stale_result is not None and stale_result.data is not None:
                for header, value in stale_result.headers.items():
                    response.headers[header] = value
                return stale_result.data

            raise


__all__ = ["CacheManager"]
