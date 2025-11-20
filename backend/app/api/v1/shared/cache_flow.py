"""Cache lookup and refresh flows shared across MVG endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, TypeVar

from fastapi import BackgroundTasks, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import Settings
from app.core.metrics import observe_cache_refresh, record_cache_event
from app.services.cache import CacheService
from app.services.mvg_errors import (
    MVGServiceError,
    RouteNotFoundError,
    StationNotFoundError,
)

from .cache_protocols import CacheRefreshProtocol, CacheResult

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


async def handle_cache_lookup(
    cache: CacheService,
    cache_key: str,
    cache_name: str,
    response: Response,
    background_tasks: BackgroundTasks,
    refresh_func: Callable[..., Any],
    refresh_kwargs: dict[str, Any],
    model_class: type[T],
    allow_stale: bool = True,
) -> CacheResult[T]:
    """Standard cache lookup pattern used across all endpoints."""
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
    """Standard error handling pattern for cache operations."""
    if isinstance(exc, TimeoutError):
        record_cache_event(cache_name, "lock_timeout")
        if allow_stale_fallback:
            stale_payload = await cache.get_stale_json(cache_key)
            if (
                stale_payload is not None
                and stale_payload.get("__status") != "not_found"
            ):
                record_cache_event(cache_name, "stale_return")
                return CacheResult(
                    data=model_class.model_validate(stale_payload),
                    status="stale",
                    headers={"X-Cache-Status": "stale"},
                )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if isinstance(exc, (StationNotFoundError, RouteNotFoundError)):
        record_cache_event(cache_name, "not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    if isinstance(exc, MVGServiceError):
        if allow_stale_fallback:
            stale_payload = await cache.get_stale_json(cache_key)
            if (
                stale_payload is not None
                and stale_payload.get("__status") != "not_found"
            ):
                record_cache_event(cache_name, "stale_return")
                return CacheResult(
                    data=model_class.model_validate(stale_payload),
                    status="stale",
                    headers={"X-Cache-Status": "stale"},
                )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    raise


async def execute_cache_refresh(
    protocol: CacheRefreshProtocol[T],
    cache: CacheService,
    cache_key: str,
    settings: Settings,
    **fetch_kwargs: Any,
) -> T:
    """Execute cache refresh using single-flight pattern with metrics."""
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            if cached_payload.get("__status") == "not_found":
                detail = cached_payload["detail"]
                record_cache_event(protocol.cache_name(), "refresh_cached_not_found")
                if protocol.cache_name() in ["mvg_departures", "mvg_station_search"]:
                    raise StationNotFoundError(detail)
                if protocol.cache_name() == "mvg_route":
                    raise RouteNotFoundError(detail)
                raise MVGServiceError(detail)
            record_cache_event(protocol.cache_name(), "refresh_skip_hit")
            return protocol.get_model_class().model_validate(cached_payload)

        start = time.perf_counter()
        try:
            fresh_data = await protocol.fetch_data(**fetch_kwargs)
        except (StationNotFoundError, RouteNotFoundError) as exc:
            detail = str(exc)
            await cache.set_json(
                cache_key,
                {"__status": "not_found", "detail": detail},
                ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
                stale_ttl_seconds=getattr(
                    settings, f"{protocol.cache_name()}_cache_stale_ttl_seconds", 300
                ),
            )
            record_cache_event(protocol.cache_name(), "refresh_not_found")
            raise
        except MVGServiceError:
            record_cache_event(protocol.cache_name(), "refresh_error")
            raise

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
    """Background task wrapper for cache refresh with error handling."""
    try:
        await execute_cache_refresh(
            protocol, cache, cache_key, settings, **fetch_kwargs
        )
    except (StationNotFoundError, RouteNotFoundError):
        record_cache_event(protocol.cache_name(), "background_not_found")
    except MVGServiceError:
        record_cache_event(protocol.cache_name(), "background_error")
        logger.warning(
            "MVG service error while refreshing %s cache.",
            protocol.cache_name(),
            exc_info=True,
        )
    except TimeoutError:
        record_cache_event(protocol.cache_name(), "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(protocol.cache_name(), "background_unexpected_error")
        logger.exception(
            "Unexpected error while refreshing %s cache.", protocol.cache_name()
        )


__all__ = [
    "execute_background_refresh",
    "execute_cache_refresh",
    "handle_cache_errors",
    "handle_cache_lookup",
]
