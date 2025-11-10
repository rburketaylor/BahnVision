"""Cache refresh protocol implementations for MVG endpoints.

This module provides concrete implementations of CacheRefreshProtocol for each
MVG endpoint type, demonstrating how to use the shared caching patterns.
"""

from datetime import datetime
from typing import Any

from app.api.v1.shared.caching import CacheRefreshProtocol, MvgCacheProtocol
from app.api.v1.shared.station_search_index import CachedStationSearchIndex
from app.core.config import Settings
from app.models.mvg import DeparturesResponse, RouteResponse, Station, StationListResponse, StationSearchResponse
from app.services.cache import CacheService
from app.services.mvg_client import (
    MVGClient,
    TransportType,
)
from app.services.mvg_client import (
    StationNotFoundError as MVGStationNotFoundError,
)


class DeparturesRefreshProtocol(CacheRefreshProtocol[DeparturesResponse]):
    """Cache refresh protocol for departures endpoint."""

    def __init__(self, client: MVGClient, filter_transport_types: list[TransportType] | None = None):
        """
        Initialize protocol with optional transport type filtering.

        Args:
            client: MVG client instance
            filter_transport_types: Optional list of transport types to filter client-side.
                                    If None, all transport types are returned.
        """
        self.client = client
        self.filter_transport_types = filter_transport_types

    def cache_name(self) -> str:
        return "mvg_departures"

    def get_model_class(self) -> type[DeparturesResponse]:
        return DeparturesResponse

    async def fetch_data(self, **kwargs: Any) -> DeparturesResponse:
        """
        Fetch departures data with optional client-side filtering.

        This method always makes a single call to MVG API to get all transport types,
        then applies filtering client-side if specific transport types were requested.
        """
        station = kwargs["station"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]

        # Always fetch all transport types in a single call for efficiency
        station_details, departures_list = await self.client.get_departures(
            station_query=station,
            limit=limit,
            offset=offset,
            transport_types=None,  # Get all types in one call
        )

        # Apply client-side filtering if specific transport types were requested
        if self.filter_transport_types:
            filter_set = set(self.filter_transport_types)
            departures_list = [
                departure for departure in departures_list
                if departure.transport_type in filter_set
            ]

        return DeparturesResponse.from_dtos(station_details, departures_list)

    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: DeparturesResponse,
        settings: Settings,
    ) -> None:
        await cache.set_json(  # type: ignore
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=settings.mvg_departures_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_departures_cache_stale_ttl_seconds,
        )


class StationSearchRefreshProtocol(MvgCacheProtocol[StationSearchResponse]):
    """Optimized cache refresh protocol for station search endpoint using O(1) search index."""

    def __init__(self, client: MVGClient, cache: CacheService):
        """
        Initialize protocol with search index support.

        Args:
            client: MVG client instance
            cache: Cache service for persistent search index
        """
        self.client = client
        self.search_index = CachedStationSearchIndex(cache)

    def cache_name(self) -> str:
        return "mvg_station_search"

    def get_model_class(self) -> type[StationSearchResponse]:
        return StationSearchResponse

    def get_ttl_setting_name(self) -> str:
        return "mvg_station_search_cache_ttl_seconds"

    def get_stale_ttl_setting_name(self) -> str:
        return "mvg_station_search_cache_stale_ttl_seconds"

    async def fetch_data(self, **kwargs: Any) -> StationSearchResponse:
        """
        Fetch station search results using optimized search index.

        This method builds and uses a high-performance search index that provides
        O(1) or O(log n) lookups instead of O(n) linear scans.
        """
        query = kwargs["query"]
        limit = kwargs["limit"]

        # Get all stations (cached call) - this is much faster with the search index
        all_stations = await self.client.get_all_stations()

        # Get or build the high-performance search index
        index = await self.search_index.get_index(all_stations)

        # Perform O(1) lookup instead of O(n) linear scan
        stations = await index.search(query, limit)

        if not stations:
            raise MVGStationNotFoundError(f"No stations found for query '{query}'.")

        return StationSearchResponse.from_dtos(query, stations)


class StationListRefreshProtocol(MvgCacheProtocol[StationListResponse]):
    """Simplified cache refresh protocol for station list endpoint."""

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_station_list"

    def get_model_class(self) -> type[StationListResponse]:
        return StationListResponse

    def get_ttl_setting_name(self) -> str:
        return "mvg_station_list_cache_ttl_seconds"

    def get_stale_ttl_setting_name(self) -> str:
        return "mvg_station_list_cache_stale_ttl_seconds"

    async def fetch_data(self, **kwargs: Any) -> StationListResponse:
        stations = await self.client.get_all_stations()
        return StationListResponse.from_dtos(stations if stations else [])


class RouteRefreshProtocol(CacheRefreshProtocol[RouteResponse]):
    """Cache refresh protocol for route endpoint."""

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_route"

    def get_model_class(self) -> type[RouteResponse]:
        return RouteResponse

    async def fetch_data(self, **kwargs: Any) -> RouteResponse:
        origin = kwargs["origin"]
        destination = kwargs["destination"]
        departure_time = kwargs.get("departure_time")
        arrival_time = kwargs.get("arrival_time")
        transport_types = kwargs.get("transport_types", [])

        origin_dto, destination_dto, plans = await self.client.plan_route(
            origin_query=origin,
            destination_query=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            transport_types=transport_types or None,
        )
        return RouteResponse.from_dtos(origin_dto, destination_dto, plans)

    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: RouteResponse,
        settings: Settings,
    ) -> None:
        await cache.set_json(  # type: ignore
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=settings.mvg_route_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_route_cache_stale_ttl_seconds,
        )