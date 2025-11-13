"""
Stations endpoints for MVG API.

This module provides the /stations/search and /stations/list endpoints with
dramatically simplified code by leveraging shared caching patterns and utilities.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response

from app.api.v1.endpoints.mvg.shared.cache_keys import station_search_cache_key
from app.api.v1.endpoints.mvg.shared.utils import get_client
from app.api.v1.shared.caching import CacheManager
from app.api.v1.shared.protocols import (
    StationListRefreshProtocol,
    StationSearchRefreshProtocol,
)
from app.core.config import get_settings
from app.models.mvg import Station, StationSearchResponse
from app.persistence.dependencies import get_station_repository
from app.persistence.repositories import StationRepository
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import MVGClient
# from app.jobs.stations_sync import run_stations_sync, get_stations_sync_status

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


# @router.post(
#     "/stations/sync",
#     summary="Sync stations from MVG API to database",
# )
# async def sync_stations() -> dict[str, int]:
#     """Trigger a manual sync of all MVG stations to the local database."""
#     return await run_stations_sync()


# @router.get(
#     "/stations/sync/status",
#     summary="Get stations sync status",
# )
# async def get_sync_status() -> dict[str, any]:
#     """Get the current status of stations in the database."""
#     return await get_stations_sync_status()
