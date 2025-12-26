"""
Heatmap endpoint for cancellation data visualization.

Provides an endpoint to retrieve cancellation heatmap data for map visualization.
"""

import time
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory, get_session
from app.models.heatmap import HeatmapResponse, TimeRangePreset
from app.services.cache import CacheService, get_cache_service
from app.services.heatmap_cache import heatmap_cancellations_cache_key
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.heatmap_service import HeatmapService, resolve_max_points

import logging

logger = logging.getLogger(__name__)

router = APIRouter()

_HEATMAP_SINGLEFLIGHT_LOCK_TTL_SECONDS = 60
_SLOW_HEATMAP_REQUEST_LOG_MS = 1500


def _append_server_timing(
    response: Response, *, name: str, duration_ms: float, description: str | None = None
) -> None:
    existing = response.headers.get("Server-Timing")
    desc = f';desc="{description}"' if description else ""
    entry = f"{name};dur={duration_ms:.2f}{desc}"
    response.headers["Server-Timing"] = f"{existing}, {entry}" if existing else entry


async def _refresh_heatmap_cache(
    *,
    cache: CacheService,
    cache_key: str,
    time_range: TimeRangePreset | None,
    transport_modes: str | None,
    bucket_width_minutes: int,
    zoom_level: int,
    max_points: int,
) -> None:
    settings = get_settings()

    try:
        async with cache.single_flight(
            cache_key,
            ttl_seconds=max(
                _HEATMAP_SINGLEFLIGHT_LOCK_TTL_SECONDS,
                settings.cache_singleflight_lock_ttl_seconds,
            ),
            wait_timeout=0.1,
            retry_delay=settings.cache_singleflight_retry_delay_seconds,
        ):
            cached = await cache.get_json(cache_key)
            if cached:
                return

            async with AsyncSessionFactory() as session:
                gtfs_schedule = GTFSScheduleService(session)
                service = HeatmapService(gtfs_schedule, cache, session=session)
                result = await service.get_cancellation_heatmap(
                    time_range=time_range,
                    transport_modes=transport_modes,
                    bucket_width_minutes=bucket_width_minutes,
                    zoom_level=zoom_level,
                    max_points=max_points,
                )
                await cache.set_json(
                    cache_key,
                    result.model_dump(mode="json"),
                    ttl_seconds=settings.heatmap_cache_ttl_seconds,
                    stale_ttl_seconds=settings.heatmap_cache_stale_ttl_seconds,
                )
    except TimeoutError:
        return
    except Exception:
        logger.exception("Heatmap background refresh failed for key '%s'", cache_key)


async def get_gtfs_schedule(
    db: AsyncSession = Depends(get_session),
) -> GTFSScheduleService:
    """Create GTFSScheduleService with database session."""
    return GTFSScheduleService(db)


@router.get(
    "/cancellations",
    response_model=HeatmapResponse,
    summary="Get cancellation heatmap data",
    description=(
        "Returns aggregated cancellation data for all transit stations, "
        "suitable for rendering as a heatmap overlay on a map."
    ),
)
async def get_cancellation_heatmap(
    response: Response,
    background_tasks: BackgroundTasks,
    time_range: Annotated[
        TimeRangePreset | None,
        Query(
            description="Time range preset for data aggregation. Options: 1h, 6h, 24h, 7d, 30d. Default: 24h.",
        ),
    ] = "24h",
    transport_modes: Annotated[
        str | None,
        Query(
            description=(
                "Comma-separated transport types to include. "
                "Options: UBAHN, SBAHN, TRAM, BUS, BAHN, REGIONAL_BUS, SCHIFF, SEV. "
                "Default: all types."
            ),
        ),
    ] = None,
    bucket_width: Annotated[
        int,
        Query(
            ge=15,
            le=1440,
            description="Time bucket width in minutes for aggregation. Default: 60.",
        ),
    ] = 60,
    zoom: Annotated[
        int,
        Query(
            ge=1,
            le=18,
            description="Map zoom level for density control. Default: 10.",
        ),
    ] = 10,
    max_points: Annotated[
        int | None,
        Query(
            ge=10,
            le=5000,
            description="Maximum number of data points to return. Default: based on zoom.",
        ),
    ] = None,
    db: AsyncSession = Depends(get_session),
    gtfs_schedule: GTFSScheduleService = Depends(get_gtfs_schedule),
    cache: CacheService = Depends(get_cache_service),
) -> HeatmapResponse:
    """
    Get cancellation heatmap data for map visualization.

    Returns aggregated cancellation statistics for all transit stations within
    the specified time range. The data includes:

    - Station locations (latitude/longitude)
    - Total departures and cancellation counts
    - Cancellation rates per station
    - Breakdown by transport type
    - Summary statistics

    The response is cached for 5 minutes to balance freshness with performance.
    When historical data is available, real GTFS-RT observations are used.
    """
    logger.info(
        f"Heatmap request: time_range={time_range}, transport_modes={transport_modes}, "
        f"bucket_width={bucket_width}, zoom={zoom}, max_points={max_points}"
    )

    try:
        request_started = time.monotonic()
        settings = get_settings()

        max_points_effective = resolve_max_points(zoom, max_points)

        # Generate cache key
        cache_key = heatmap_cancellations_cache_key(
            time_range=time_range,
            transport_modes=transport_modes,
            bucket_width_minutes=bucket_width,
            max_points=max_points_effective,
        )

        # Try to get from cache
        cache_get_started = time.monotonic()
        cached_data = await cache.get_json(cache_key)
        cache_get_ms = (time.monotonic() - cache_get_started) * 1000
        _append_server_timing(response, name="cache", duration_ms=cache_get_ms)
        if cached_data:
            response.headers["X-Cache-Status"] = "hit"
            logger.debug("Cache hit for heatmap data")
            return HeatmapResponse.model_validate(cached_data)

        stale_get_started = time.monotonic()
        stale_data = await cache.get_stale_json(cache_key)
        stale_get_ms = (time.monotonic() - stale_get_started) * 1000
        _append_server_timing(response, name="stale", duration_ms=stale_get_ms)
        if stale_data:
            response.headers["X-Cache-Status"] = "stale-refresh"
            background_tasks.add_task(
                _refresh_heatmap_cache,
                cache=cache,
                cache_key=cache_key,
                time_range=time_range,
                transport_modes=transport_modes,
                bucket_width_minutes=bucket_width,
                zoom_level=zoom,
                max_points=max_points_effective,
            )
            return HeatmapResponse.model_validate(stale_data)

        logger.info("Cache miss - generating fresh heatmap data")

        lock_ttl = max(
            _HEATMAP_SINGLEFLIGHT_LOCK_TTL_SECONDS,
            settings.cache_singleflight_lock_ttl_seconds,
        )
        async with cache.single_flight(
            cache_key,
            ttl_seconds=lock_ttl,
            wait_timeout=settings.cache_singleflight_lock_wait_seconds,
            retry_delay=settings.cache_singleflight_retry_delay_seconds,
        ):
            # Double-check after acquiring lock in case another request filled it.
            cached_data = await cache.get_json(cache_key)
            if cached_data:
                response.headers["X-Cache-Status"] = "hit"
                return HeatmapResponse.model_validate(cached_data)

            generate_started = time.monotonic()
            service = HeatmapService(gtfs_schedule, cache, session=db)
            result = await service.get_cancellation_heatmap(
                time_range=time_range,
                transport_modes=transport_modes,
                bucket_width_minutes=bucket_width,
                zoom_level=zoom,
                max_points=max_points_effective,
            )
            generate_ms = (time.monotonic() - generate_started) * 1000
            _append_server_timing(response, name="generate", duration_ms=generate_ms)

            # Cache the result (and keep a stale copy for fast fallbacks)
            await cache.set_json(
                cache_key,
                result.model_dump(mode="json"),
                ttl_seconds=settings.heatmap_cache_ttl_seconds,
                stale_ttl_seconds=settings.heatmap_cache_stale_ttl_seconds,
            )

        response.headers["X-Cache-Status"] = "miss"
        total_ms = (time.monotonic() - request_started) * 1000
        _append_server_timing(response, name="total", duration_ms=total_ms)
        logger.info(f"Generated heatmap with {len(result.data_points)} data points")
        if total_ms >= _SLOW_HEATMAP_REQUEST_LOG_MS:
            logger.warning(
                "Slow heatmap request (%dms): time_range=%s zoom=%s max_points=%s bucket_width=%s transport_modes=%s",
                int(total_ms),
                time_range,
                zoom,
                max_points_effective,
                bucket_width,
                transport_modes,
            )
        return result

    except Exception as e:
        logger.error(f"Heatmap generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate heatmap data")


@router.get("/health")
async def heatmap_health_check():
    """Health check endpoint for heatmap service."""
    try:
        # Test database connectivity
        async with AsyncSessionFactory() as session:
            result = await session.execute(text("SELECT 1"))
            # Validate connection by fetching the scalar result
            result.scalar_one_or_none()

        return {
            "status": "healthy",
            "database": "connected",
            "message": "Heatmap service is operational",
        }

    except Exception as e:
        logger.error(f"Heatmap health check failed: {str(e)}")
        return {"status": "unhealthy", "database": "disconnected"}


# Test the health endpoint directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
