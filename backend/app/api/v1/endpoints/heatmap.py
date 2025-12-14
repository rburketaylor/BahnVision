"""
Heatmap endpoint for cancellation data visualization.

Provides an endpoint to retrieve cancellation heatmap data for map visualization.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.heatmap import HeatmapResponse, TimeRangePreset
from app.services.cache import CacheService, get_cache_service
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.heatmap_service import HeatmapService

router = APIRouter()

# Cache configuration for heatmap
_CACHE_HEATMAP = "heatmap"
_HEATMAP_CACHE_TTL_SECONDS = 300  # 5 minutes


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
    # Generate cache key
    cache_key = f"heatmap:cancellations:{time_range}:{transport_modes or 'all'}:{bucket_width}:{zoom}:{max_points or 'default'}"

    # Try to get from cache
    cached_data = await cache.get_json(cache_key)
    if cached_data:
        response.headers["X-Cache-Status"] = "hit"
        return HeatmapResponse.model_validate(cached_data)

    # Generate fresh data with database session for real aggregations
    service = HeatmapService(gtfs_schedule, cache, session=db)
    result = await service.get_cancellation_heatmap(
        time_range=time_range,
        transport_modes=transport_modes,
        bucket_width_minutes=bucket_width,
        zoom_level=zoom,
        max_points=max_points,
    )

    # Cache the result
    await cache.set_json(
        cache_key,
        result.model_dump(mode="json"),
        ttl_seconds=_HEATMAP_CACHE_TTL_SECONDS,
    )

    response.headers["X-Cache-Status"] = "miss"
    return result
