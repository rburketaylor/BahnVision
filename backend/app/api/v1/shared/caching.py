"""Shared caching patterns for MVG API endpoints.

This module provides reusable caching abstractions to eliminate code duplication
across all MVG endpoints while maintaining security, performance, and observability.
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Generic, TypeVar

from fastapi import BackgroundTasks, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import Settings
from app.core.metrics import observe_cache_refresh, record_cache_event
from app.services.cache import CacheService
from app.services.mvg_client import (
    MVGServiceError,
    RouteNotFoundError,
    StationNotFoundError,
)

logger = logging.getLogger(__name__)

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


async def handle_cache_lookup(
    cache: CacheService,
    cache_key: str,
    cache_name: str,
    response: Response,
    background_tasks: BackgroundTasks,
    refresh_func: Callable,
    refresh_kwargs: dict[str, Any],
    model_class: type[T],
    allow_stale: bool = True,
) -> CacheResult[T]:
    """
    Standard cache lookup pattern used across all endpoints.

    Args:
        cache: CacheService instance
        cache_key: Cache key to lookup
        cache_name: Cache name for metrics
        response: FastAPI Response object for headers
        background_tasks: FastAPI BackgroundTasks for stale refresh
        refresh_func: Function to call for cache refresh
        refresh_kwargs: Arguments to pass to refresh function
        allow_stale: Whether to return stale data during refresh

    Returns:
        CacheResult with data and status information
    """
    # Check fresh cache first
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        record_cache_event(cache_name, "hit")
        if cached_payload.get("__status") == "not_found":
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        response.headers["X-Cache-Status"] = "hit"
        return CacheResult(
            data=model_class.model_validate(cached_payload),
            status="hit",
            headers={"X-Cache-Status": "hit"},
        )

    # Check stale cache if allowed
    if allow_stale:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(cache_name, "stale_return")
            response.headers["X-Cache-Status"] = "stale-refresh"
            background_tasks.add_task(refresh_func, **refresh_kwargs)
            return CacheResult(
                data=model_class.model_validate(stale_payload),
                status="stale-refresh",
                headers={"X-Cache-Status": "stale-refresh"},
            )

    record_cache_event(cache_name, "miss")
    return CacheResult(status="miss", headers={"X-Cache-Status": "miss"})


async def handle_cache_errors(
    cache: CacheService,
    cache_key: str,
    cache_name: str,
    exc: Exception,
    model_class: type[T],
    allow_stale_fallback: bool = True,
) -> CacheResult[T] | None:
    """
    Standard error handling pattern for cache operations.

    Args:
        cache: CacheService instance
        cache_key: Cache key to check for stale data
        cache_name: Cache name for metrics
        exc: Exception that occurred during cache operation
        model_class: Pydantic model class for data validation
        allow_stale_fallback: Whether to return stale data on error

    Returns:
        CacheResult with stale data if available and allowed, None otherwise
    """
    if isinstance(exc, TimeoutError):
        record_cache_event(cache_name, "lock_timeout")
        if allow_stale_fallback:
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(cache_name, "stale_return")
                return CacheResult(
                    data=model_class.model_validate(stale_payload),
                    status="stale",
                    headers={"X-Cache-Status": "stale"},
                )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    elif isinstance(exc, (StationNotFoundError, RouteNotFoundError)):
        record_cache_event(cache_name, "not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    elif isinstance(exc, MVGServiceError):
        if allow_stale_fallback:
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(cache_name, "stale_return")
                return CacheResult(
                    data=model_class.model_validate(stale_payload),
                    status="stale",
                    headers={"X-Cache-Status": "stale"},
                )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    # Re-raise unexpected exceptions
    raise


async def execute_cache_refresh(
    protocol: CacheRefreshProtocol[T],
    cache: CacheService,
    cache_key: str,
    settings: Settings,
    **fetch_kwargs: Any,
) -> T:
    """
    Execute cache refresh using single-flight pattern with metrics.

    Args:
        protocol: CacheRefreshProtocol implementation
        cache: CacheService instance
        cache_key: Cache key to refresh
        settings: Application settings
        **fetch_kwargs: Arguments to pass to fetch_data

    Returns:
        Fresh data from the service
    """
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        # Check if another request already refreshed the cache
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            if cached_payload.get("__status") == "not_found":
                detail = cached_payload["detail"]
                record_cache_event(protocol.cache_name(), "refresh_cached_not_found")
                # Determine which exception to raise based on protocol type
                if protocol.cache_name() in ["mvg_departures", "mvg_station_search"]:
                    raise StationNotFoundError(detail)
                elif protocol.cache_name() == "mvg_route":
                    raise RouteNotFoundError(detail)
                else:
                    raise MVGServiceError(detail)
            record_cache_event(protocol.cache_name(), "refresh_skip_hit")
            return protocol.get_model_class().model_validate(cached_payload)

        # Fetch fresh data
        start = time.perf_counter()
        try:
            fresh_data = await protocol.fetch_data(**fetch_kwargs)
        except (StationNotFoundError, RouteNotFoundError) as exc:
            # Cache not-found responses with shorter TTL
            detail = str(exc)
            await cache.set_json(
                cache_key,
                {"__status": "not_found", "detail": detail},
                ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
                stale_ttl_seconds=getattr(settings, f"{protocol.cache_name()}_cache_stale_ttl_seconds", 300),
            )
            record_cache_event(protocol.cache_name(), "refresh_not_found")
            raise
        except MVGServiceError:
            record_cache_event(protocol.cache_name(), "refresh_error")
            raise

        # Store fresh data and record metrics
        observe_cache_refresh(protocol.cache_name(), time.perf_counter() - start)
        await protocol.store_data(cache, cache_key, fresh_data, settings)
        record_cache_event(protocol.cache_name(), "refresh_success")
        return fresh_data


async def execute_background_refresh(
    protocol: CacheRefreshProtocol[T],
    cache: CacheService,
    cache_key: str,
    settings: Settings,
    **fetch_kwargs: Any,
) -> None:
    """
    Background task wrapper for cache refresh with error handling.

    Args:
        protocol: CacheRefreshProtocol implementation
        cache: CacheService instance
        cache_key: Cache key to refresh
        settings: Application settings
        **fetch_kwargs: Arguments to pass to fetch_data
    """
    try:
        await execute_cache_refresh(protocol, cache, cache_key, settings, **fetch_kwargs)
    except (StationNotFoundError, RouteNotFoundError):
        record_cache_event(protocol.cache_name(), "background_not_found")
        # No need to log at error level; cache already stores not-found marker
    except MVGServiceError:
        record_cache_event(protocol.cache_name(), "background_error")
        logger.warning(
            f"MVG service error while refreshing {protocol.cache_name()} cache.",
            exc_info=True
        )
    except TimeoutError:
        record_cache_event(protocol.cache_name(), "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(protocol.cache_name(), "background_unexpected_error")
        logger.exception(f"Unexpected error while refreshing {protocol.cache_name()} cache.")


class CacheManager(Generic[T]):
    """
    High-level cache manager that provides a simplified interface for common caching patterns.

    This class encapsulates the complete cache lookup, refresh, and error handling flow
    used across all MVG endpoints.
    """

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
        """
        Get data from cache with automatic refresh and error handling.

        This method implements the complete caching pattern:
        1. Check fresh cache
        2. Check stale cache (if allowed)
        3. Refresh cache on miss
        4. Handle errors with stale fallback
        5. Record metrics and set headers

        Args:
            cache_key: Cache key to lookup
            response: FastAPI Response object for headers
            background_tasks: FastAPI BackgroundTasks for stale refresh
            settings: Application settings
            allow_stale: Whether to return stale data during refresh
            **fetch_kwargs: Arguments to pass to fetch_data

        Returns:
            Data from cache or fresh from service
        """
        # Step 1: Check cache
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
            # Set response headers from cache result
            for header, value in cache_result.headers.items():
                response.headers[header] = value
            return cache_result.data

        # Step 2: Cache miss - refresh data
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
            # Step 3: Handle errors with stale fallback
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

            # Re-raise if no stale fallback available
            raise