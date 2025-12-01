"""
Stations endpoints for MVG API.

Provides station search and listing with caching and stale fallback.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from app.api.v1.endpoints.mvg.shared.cache_keys import station_search_cache_key
from app.api.v1.endpoints.mvg.shared.utils import get_client
from app.api.v1.shared.cache_manager import CacheManager
from app.api.v1.shared.mvg_protocols import (
    StationListRefreshProtocol,
    StationSearchRefreshProtocol,
)
from app.core.config import get_settings
from app.models.mvg import Station, StationSearchResponse
from app.persistence.dependencies import get_station_repository
from app.persistence.repositories import StationRepository
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import MVGClient

router = APIRouter()

# Cache names for metrics
_CACHE_STATION_SEARCH = "mvg_station_search"
_CACHE_STATION_LIST = "mvg_station_list"


@router.get(
    "/stations/search",
    response_model=StationSearchResponse,
    summary="Find stations matching a search query",
)
async def search_stations(
    query: Annotated[
        str,
        Query(
            min_length=1,
            description="Free-form search text for MVG stations (name or address).",
        ),
    ],
    response: Response,
    background_tasks: BackgroundTasks,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of stations to return (default: 40).",
        ),
    ] = 40,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
    station_repository: StationRepository = Depends(get_station_repository),
) -> StationSearchResponse:
    """Search MVG for station suggestions."""
    settings = get_settings()
    cache_key = station_search_cache_key(query, limit)

    # Use the shared cache manager with optimized search index
    cache_manager = CacheManager(
        protocol=StationSearchRefreshProtocol(client, cache, station_repository),
        cache=cache,
        cache_name=_CACHE_STATION_SEARCH,
    )

    return await cache_manager.get_cached_data(
        cache_key=cache_key,
        response=response,
        background_tasks=background_tasks,
        settings=settings,
        query=query,
        limit=limit,
    )


@router.get(
    "/stations/list",
    response_model=list[Station],
    summary="Get all MVG stations (cached)",
)
async def list_stations(
    response: Response,
    background_tasks: BackgroundTasks,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
    station_repository: StationRepository = Depends(get_station_repository),
) -> list[Station]:
    """Get the complete list of MVG stations."""
    settings = get_settings()
    cache_key = "mvg:stations:all"

    # Use the shared cache manager for simplified caching logic
    cache_manager = CacheManager(
        protocol=StationListRefreshProtocol(client, cache, station_repository),
        cache=cache,
        cache_name=_CACHE_STATION_LIST,
    )

    return await cache_manager.get_cached_data(
        cache_key=cache_key,
        response=response,
        background_tasks=background_tasks,
        settings=settings,
    )
