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
            le=20,
            description="Maximum number of stations to return (default: 8).",
        ),
    ] = 8,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> StationSearchResponse:
    """Search MVG for station suggestions."""
    settings = get_settings()
    cache_key = station_search_cache_key(query, limit)

    # Use the shared cache manager for simplified caching logic
    cache_manager = CacheManager(
        protocol=StationSearchRefreshProtocol(client),
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
) -> list[Station]:
    """Get the complete list of MVG stations."""
    settings = get_settings()
    cache_key = "mvg:stations:all"

    # Use the shared cache manager for simplified caching logic
    cache_manager = CacheManager(
        protocol=StationListRefreshProtocol(client),
        cache=cache,
        cache_name=_CACHE_STATION_LIST,
    )

    return await cache_manager.get_cached_data(
        cache_key=cache_key,
        response=response,
        background_tasks=background_tasks,
        settings=settings,
    )