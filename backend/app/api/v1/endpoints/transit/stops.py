"""
Stops endpoints for Transit API.

Provides stop search and information using GTFS data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.shared.rate_limit import limiter
from app.core.config import get_settings
from app.core.database import get_session
from app.models.transit import (
    TransitStop,
    TransitStopSearchResponse,
)
from app.services.cache import CacheService, get_cache_service
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.gtfs_realtime import GtfsRealtimeService
from app.services.transit_data import TransitDataService

router = APIRouter()

# Cache names for metrics
_CACHE_STOP_SEARCH = "transit_stop_search"


async def get_transit_data_service(
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_session),
) -> TransitDataService:
    """Create TransitDataService with dependencies."""
    gtfs_schedule = GTFSScheduleService(db)
    gtfs_realtime = GtfsRealtimeService(cache)
    return TransitDataService(cache, gtfs_schedule, gtfs_realtime, db)


@router.get(
    "/stops/search",
    response_model=TransitStopSearchResponse,
    summary="Search for stops by name",
    description="Find transit stops matching a search query.",
)
@limiter.limit("60/minute")
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
    results = [
        TransitStop(
            id=stop.stop_id,
            name=stop.stop_name,
            latitude=stop.stop_lat,
            longitude=stop.stop_lon,
            zone_id=stop.zone_id,
            wheelchair_boarding=stop.wheelchair_boarding,
        )
        for stop in stop_infos
    ]

    # Set cache headers
    settings = get_settings()
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.gtfs_stop_cache_ttl_seconds}"
    )

    return TransitStopSearchResponse(
        query=query,
        results=results,
    )


@router.get(
    "/stops/{stop_id}",
    response_model=TransitStop,
    summary="Get stop details",
    description="Get detailed information about a specific stop.",
)
@limiter.limit("60/minute")
async def get_stop(
    request: Request,
    stop_id: str,
    response: Response,
    transit_service: TransitDataService = Depends(get_transit_data_service),
) -> TransitStop:
    """Get details for a specific stop."""
    stop_info = await transit_service.get_stop_info(stop_id)

    if not stop_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop '{stop_id}' not found",
        )

    # Set cache headers
    settings = get_settings()
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.gtfs_stop_cache_ttl_seconds}"
    )

    return TransitStop(
        id=stop_info.stop_id,
        name=stop_info.stop_name,
        latitude=stop_info.stop_lat,
        longitude=stop_info.stop_lon,
        zone_id=stop_info.zone_id,
        wheelchair_boarding=stop_info.wheelchair_boarding,
    )


@router.get(
    "/stops/nearby",
    response_model=list[TransitStop],
    summary="Find stops near a location",
    description="Find transit stops within a radius of a given location.",
)
@limiter.limit("30/minute")
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
    settings = get_settings()
    gtfs_schedule = GTFSScheduleService(db)

    radius_km = radius_meters / 1000.0

    stops = await gtfs_schedule.get_nearby_stops(latitude, longitude, radius_km, limit)

    # Convert to response models
    results = [
        TransitStop(
            id=str(stop.stop_id),
            name=str(stop.stop_name),
            latitude=float(stop.stop_lat) if stop.stop_lat else 0.0,
            longitude=float(stop.stop_lon) if stop.stop_lon else 0.0,
            zone_id=None,
            wheelchair_boarding=0,
        )
        for stop in stops
    ]

    # Set cache headers
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.gtfs_stop_cache_ttl_seconds}"
    )

    return results
