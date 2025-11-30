"""
Heatmap endpoint for cancellation data visualization.

Provides an endpoint to retrieve cancellation heatmap data for map visualization.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.v1.endpoints.mvg.shared.utils import get_client
from app.core.config import get_settings
from app.models.heatmap import HeatmapResponse, TimeRangePreset
from app.services.cache import CacheService, get_cache_service
from app.services.heatmap_service import HeatmapService
from app.services.mvg_client import MVGClient

router = APIRouter()

# Cache configuration for heatmap
_CACHE_HEATMAP = "heatmap"
_HEATMAP_CACHE_TTL_SECONDS = 300  # 5 minutes


@router.get(
    "/cancellations",
    response_model=HeatmapResponse,
    summary="Get cancellation heatmap data",
    description=(
        "Returns aggregated cancellation data for all MVG stations, "
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
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> HeatmapResponse:
    """
    Get cancellation heatmap data for map visualization.

    Returns aggregated cancellation statistics for all MVG stations within
    the specified time range. The data includes:

    - Station locations (latitude/longitude)
    - Total departures and cancellation counts
    - Cancellation rates per station
    - Breakdown by transport type
    - Summary statistics

    The response is cached for 5 minutes to balance freshness with performance.
    """
    settings = get_settings()

    # Generate cache key
    cache_key = f"heatmap:cancellations:{time_range}:{transport_modes or 'all'}:{bucket_width}"

    # Try to get from cache
    cached_data = await cache.get_json(cache_key)
    if cached_data:
        response.headers["X-Cache-Status"] = "hit"
        return HeatmapResponse.model_validate(cached_data)

    # Generate fresh data
    service = HeatmapService(client, cache)
    result = await service.get_cancellation_heatmap(
        time_range=time_range,
        transport_modes=transport_modes,
        bucket_width_minutes=bucket_width,
    )

    # Cache the result
    await cache.set_json(
        cache_key,
        result.model_dump(mode="json"),
        ttl_seconds=_HEATMAP_CACHE_TTL_SECONDS,
    )

    response.headers["X-Cache-Status"] = "miss"
    return result
