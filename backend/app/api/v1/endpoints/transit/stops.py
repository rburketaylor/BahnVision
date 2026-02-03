"""
Stops endpoints for Transit API.

Provides stop search and information using GTFS data.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

from app.api.v1.shared import (
    RATE_LIMIT_EXPENSIVE,
    RATE_LIMIT_NEARBY,
    RATE_LIMIT_SEARCH,
    gtfs_stop_to_transit_stop,
    set_station_search_cache_header,
    set_stats_cache_header,
    set_transit_cache_header,
    station_not_found,
    stop_not_found,
)
from app.api.v1.shared.dependencies import get_transit_data_service
from app.api.v1.shared.rate_limit import limiter
from app.core.database import get_session
from app.models.heatmap import HeatmapResponse, TimeRangePreset
from app.models.station_stats import (
    StationStats,
    StationTrends,
    TransportBreakdown,
    TrendGranularity,
)
from app.models.transit import (
    TransitStop,
    TransitStopSearchResponse,
)
from app.services.cache import CacheService, get_cache_service
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.heatmap_cache import heatmap_live_snapshot_cache_key
from app.services.heatmap_service import TRANSPORT_TYPE_NAMES
from app.services.station_stats_service import StationStatsService
from app.services.transit_data import TransitDataService

router = APIRouter()

# Cache names for metrics


@dataclass
class _StopLikeAdapter:
    stop_id: Any
    stop_name: Any
    stop_lat: Any
    stop_lon: Any
    zone_id: Any = None
    wheelchair_boarding: Any = 0


async def _get_station_stats_from_live_snapshot(
    stop_id: str,
    cache: CacheService,
    *,
    include_network_averages: bool,
) -> StationStats | None:
    """Extract station stats from the live snapshot cache.

    For live mode, the heatmap overview has fresh data from GTFS-RT,
    but the database may not have corresponding realtime_station_stats.
    This function extracts the specific station's data from the live snapshot.
    """
    cache_key = heatmap_live_snapshot_cache_key()
    cached_data = await cache.get_json(cache_key)
    if not cached_data:
        cached_data = await cache.get_stale_json(cache_key)

    if not cached_data:
        return None

    snapshot = HeatmapResponse.model_validate(cached_data)

    # Find the station in the snapshot
    for point in snapshot.data_points:
        if point.station_id == stop_id:
            # Convert by_transport dict to TransportBreakdown list
            by_transport = [
                TransportBreakdown(
                    transport_type=transport_type,
                    display_name=TRANSPORT_TYPE_NAMES.get(
                        transport_type, transport_type
                    ),
                    total_departures=stats.total,
                    cancelled_count=stats.cancelled,
                    cancellation_rate=min(stats.cancelled / stats.total, 1.0)
                    if stats.total > 0
                    else 0,
                    delayed_count=stats.delayed,
                    delay_rate=min(stats.delayed / stats.total, 1.0)
                    if stats.total > 0
                    else 0,
                )
                for transport_type, stats in point.by_transport.items()
            ]

            return StationStats(
                station_id=stop_id,
                station_name=point.station_name,
                time_range="live",
                total_departures=point.total_departures,
                cancelled_count=point.cancelled_count,
                cancellation_rate=point.cancellation_rate,
                delayed_count=point.delayed_count,
                delay_rate=point.delay_rate,
                network_avg_cancellation_rate=(
                    snapshot.summary.overall_cancellation_rate
                    if include_network_averages
                    else None
                ),
                network_avg_delay_rate=(
                    snapshot.summary.overall_delay_rate
                    if include_network_averages
                    else None
                ),
                performance_score=None,  # Not calculated for live
                by_transport=by_transport,
                data_from=snapshot.time_range.from_time,
                data_to=snapshot.time_range.to_time,
            )

    return None


async def get_station_stats_service(
    db: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
) -> StationStatsService:
    """Create StationStatsService with dependencies."""
    gtfs_schedule = GTFSScheduleService(db)
    return StationStatsService(db, gtfs_schedule, cache)


@router.get(
    "/stops/search",
    response_model=TransitStopSearchResponse,
    summary="Search for stops by name",
    description="Find transit stops matching a search query.",
)
@limiter.limit(RATE_LIMIT_SEARCH.value)
async def search_stops(
    request: Request,
    query: Annotated[
        str,
        Query(
            min_length=1,
            max_length=100,
            description="Search text for stop name.",
        ),
    ],
    response: Response,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of results to return (default: 10).",
        ),
    ] = 10,
    transit_service: TransitDataService = Depends(get_transit_data_service),
) -> TransitStopSearchResponse:
    """Search for transit stops by name."""
    stop_infos = await transit_service.search_stops(query, limit)

    # Convert to response models
    results = [gtfs_stop_to_transit_stop(stop) for stop in stop_infos]

    # Set cache headers using the correct search TTL
    set_station_search_cache_header(response)

    return TransitStopSearchResponse(
        query=query,
        results=results,
    )


@router.get(
    "/stops/nearby",
    response_model=list[TransitStop],
    summary="Find stops near a location",
    description="Find transit stops within a radius of a given location.",
)
@limiter.limit(RATE_LIMIT_NEARBY.value)
async def get_nearby_stops(
    request: Request,
    latitude: Annotated[
        float,
        Query(
            ge=-90,
            le=90,
            description="Latitude of the center point.",
        ),
    ],
    longitude: Annotated[
        float,
        Query(
            ge=-180,
            le=180,
            description="Longitude of the center point.",
        ),
    ],
    response: Response,
    radius_meters: Annotated[
        int,
        Query(
            ge=100,
            le=10000,
            description="Search radius in meters (default: 500).",
        ),
    ] = 500,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of results to return (default: 10).",
        ),
    ] = 10,
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_session),
) -> list[TransitStop]:
    """Find transit stops near a location."""
    # Set cache header for GTFS stop data
    set_transit_cache_header(response)

    # Bucket coordinates to reduce cache key cardinality
    # Using ~100m precision (0.001 degrees ≈ 111m at equator)
    lat_bucket = round(latitude, 3)
    lon_bucket = round(longitude, 3)
    cache_key = f"nearby_stops:{lat_bucket}:{lon_bucket}:{radius_meters}:{limit}"

    # Try cache first
    try:
        cached_data = await cache.get_json(cache_key)
        if cached_data:
            return [TransitStop(**s) for s in cached_data]

        stale_data = await cache.get_stale_json(cache_key)
        if stale_data:
            return [TransitStop(**s) for s in stale_data]
    except Exception as cache_error:
        import logging

        logging.getLogger(__name__).warning(
            f"Nearby stops cache read failed: {cache_error}"
        )

    # Cache miss - query database
    gtfs_schedule = GTFSScheduleService(db)
    radius_km = radius_meters / 1000.0
    stops = await gtfs_schedule.get_nearby_stops(latitude, longitude, radius_km, limit)

    # Convert to response models (exclude zone and wheelchair for nearby)
    results = [
        gtfs_stop_to_transit_stop(
            _StopLikeAdapter(
                stop_id=stop.stop_id,
                stop_name=stop.stop_name,
                stop_lat=stop.stop_lat,
                stop_lon=stop.stop_lon,
            ),
            include_zone=False,
            include_wheelchair=False,
        )
        for stop in stops
    ]

    # Cache the result (stops rarely change)
    try:
        settings = get_settings()
        serialized = [r.model_dump() for r in results]
        await cache.set_json(
            cache_key,
            serialized,
            ttl_seconds=settings.gtfs_stop_cache_ttl_seconds,
            stale_ttl_seconds=settings.gtfs_stop_cache_ttl_seconds * 2,
        )
    except Exception as cache_error:
        import logging

        logging.getLogger(__name__).warning(
            f"Nearby stops cache write failed: {cache_error}"
        )

    return results


@router.get(
    "/stops/{stop_id}",
    response_model=TransitStop,
    summary="Get stop details",
    description="Get detailed information about a specific stop.",
)
@limiter.limit(RATE_LIMIT_SEARCH.value)
async def get_stop(
    request: Request,
    stop_id: str,
    response: Response,
    transit_service: TransitDataService = Depends(get_transit_data_service),
) -> TransitStop:
    """Get details for a specific stop."""
    stop_info = await transit_service.get_stop_info(stop_id)

    if not stop_info:
        raise stop_not_found(stop_id)

    # Set cache headers
    set_transit_cache_header(response)

    return gtfs_stop_to_transit_stop(stop_info)


@router.get(
    "/stops/{stop_id}/stats",
    response_model=StationStats,
    summary="Get station statistics",
    description="Get cancellation and delay statistics for a specific station.",
)
@limiter.limit(RATE_LIMIT_SEARCH.value)
async def get_station_stats(
    request: Request,
    stop_id: str,
    response: Response,
    time_range: Annotated[
        TimeRangePreset,
        Query(description="Time range preset (live, 1h, 6h, 24h, 7d, 30d)."),
    ] = "24h",
    include_network_averages: Annotated[
        bool,
        Query(
            description="Whether to include network-wide average rates (expensive for long time ranges)."
        ),
    ] = True,
    stats_service: StationStatsService = Depends(get_station_stats_service),
    cache: CacheService = Depends(get_cache_service),
) -> StationStats:
    """Get station statistics including cancellation and delay rates."""
    # Handle live mode - use snapshot cache as primary source
    if time_range == "live":
        stats = await _get_station_stats_from_live_snapshot(
            stop_id,
            cache,
            include_network_averages=include_network_averages,
        )
        if stats:
            set_stats_cache_header(response)
            return stats
        # Fall through to database query with "1h" as fallback
        time_range = "1h"

    stats = await stats_service.get_station_stats(
        stop_id,
        time_range,
        include_network_averages=include_network_averages,
    )

    if not stats:
        raise station_not_found(stop_id)

    # Set cache headers - shorter TTL for stats (5 minutes)
    set_stats_cache_header(response)

    return stats


@router.get(
    "/stops/{stop_id}/trends",
    response_model=StationTrends,
    summary="Get station trends",
    description="Get historical trend data for a specific station.",
)
@limiter.limit(RATE_LIMIT_EXPENSIVE.value)
async def get_station_trends(
    request: Request,
    stop_id: str,
    response: Response,
    time_range: Annotated[
        TimeRangePreset,
        Query(description="Time range preset (1h, 6h, 24h, 7d, 30d)."),
    ] = "24h",
    granularity: Annotated[
        TrendGranularity,
        Query(description="Data granularity (hourly or daily)."),
    ] = "hourly",
    stats_service: StationStatsService = Depends(get_station_stats_service),
) -> StationTrends:
    """Get historical trend data for a station."""
    trends = await stats_service.get_station_trends(stop_id, time_range, granularity)

    if not trends:
        raise station_not_found(stop_id)

    # Set cache headers - shorter TTL for trends (5 minutes)
    set_stats_cache_header(response)

    return trends
