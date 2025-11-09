"""Cache refresh protocol implementations for MVG endpoints.

This module provides concrete implementations of CacheRefreshProtocol for each
MVG endpoint type, demonstrating how to use the shared caching patterns.
"""

from datetime import datetime
from typing import Any

from app.api.v1.shared.caching import CacheRefreshProtocol
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

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_departures"

    def get_model_class(self) -> type[DeparturesResponse]:
        return DeparturesResponse

    async def fetch_data(self, **kwargs: Any) -> DeparturesResponse:
        station = kwargs["station"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]
        transport_types = kwargs.get("transport_types", [])

        station_details, departures_list = await self.client.get_departures(
            station_query=station,
            limit=limit,
            offset=offset,
            transport_types=transport_types or None,
        )
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


class StationSearchRefreshProtocol(CacheRefreshProtocol[StationSearchResponse]):
    """Cache refresh protocol for station search endpoint."""

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_station_search"

    def get_model_class(self) -> type[StationSearchResponse]:
        return StationSearchResponse

    async def fetch_data(self, **kwargs: Any) -> StationSearchResponse:
        query = kwargs["query"]
        limit = kwargs["limit"]

        # Get all stations for search (this would need to be optimized in practice)
        all_stations = await self.client.get_all_stations()

        query_lower = query.lower()
        stations: list[Station] = []
        for station in all_stations:
            if query_lower in station.name.lower() or query_lower in station.place.lower():
                stations.append(station)
                if len(stations) >= limit:
                    break

        if not stations:
            raise MVGStationNotFoundError(f"No stations found for query '{query}'.")

        return StationSearchResponse.from_dtos(query, stations)

    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: StationSearchResponse,
        settings: Settings,
    ) -> None:
        await cache.set_json(  # type: ignore
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=settings.mvg_station_search_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_station_search_cache_stale_ttl_seconds,
        )


class StationListRefreshProtocol(CacheRefreshProtocol[StationListResponse]):
    """Cache refresh protocol for station list endpoint."""

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_station_list"

    def get_model_class(self) -> type[StationListResponse]:
        return StationListResponse

    async def fetch_data(self, **kwargs: Any) -> StationListResponse:
        stations = await self.client.get_all_stations()
        return StationListResponse.from_dtos(stations if stations else [])

    async def store_data(
        self,
        cache: CacheService,
        cache_key: str,
        data: StationListResponse,
        settings: Settings,
    ) -> None:
        await cache.set_json(  # type: ignore
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=settings.mvg_station_list_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_station_list_cache_stale_ttl_seconds,
        )


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