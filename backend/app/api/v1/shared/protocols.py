"""Cache refresh protocol implementations for MVG endpoints.

This module provides concrete implementations of CacheRefreshProtocol for each
MVG endpoint type, demonstrating how to use the shared caching patterns.
"""

import logging
from typing import Any

from app.api.v1.shared.cache_protocols import CacheRefreshProtocol, MvgCacheProtocol
from app.api.v1.shared.station_search_index import CachedStationSearchIndex
from app.core.config import Settings, get_settings
from app.persistence.repositories import StationPayload, StationRepository
from app.models.mvg import (
    DeparturesResponse,
    RouteResponse,
    Station,
    StationListResponse,
    StationSearchResponse,
)
from app.services.cache import CacheService
from app.services.mvg_client import (
    MVGClient,
    Station as StationDTO,
    TransportType,
)
from app.services.mvg_client import StationNotFoundError as MVGStationNotFoundError

logger = logging.getLogger(__name__)


class StationCatalog:
    """Helper that loads station metadata from cache, persistence, or MVG."""

    CACHE_KEY = "mvg:stations:all"

    def __init__(
        self,
        client: MVGClient,
        cache: CacheService,
        repository: StationRepository | None,
        *,
        settings: Settings | None = None,
    ):
        self.client = client
        self.cache = cache
        self.repository = repository
        self.settings = settings or get_settings()

    async def get_stations(self) -> list[Station]:
        """Return the most recent station catalog available to the service."""
        for loader in (
            self._load_from_station_list_cache,
            self._load_from_repository,
            self._fetch_from_mvg,
        ):
            stations = await loader()
            if stations:
                return stations
        return []

    async def _load_from_station_list_cache(self) -> list[Station]:
        payload = await self.cache.get_json(self.CACHE_KEY)
        if not payload:
            return []
        try:
            response = StationListResponse.model_validate(payload)
        except Exception as exc:
            logger.warning("Failed to parse cached station list: %s", exc)
            return []
        return [
            Station(
                id=station.id,
                name=station.name,
                place=station.place,
                latitude=station.latitude,
                longitude=station.longitude,
            )
            for station in response.stations
        ]

    async def _load_from_repository(self) -> list[Station]:
        if self.repository is None:
            return []
        try:
            records = await self.repository.get_all_stations()
        except Exception as exc:
            logger.warning("Failed to read stations from repository: %s", exc)
            return []
        return [
            Station(
                id=record.station_id,
                name=record.name,
                place=record.place,
                latitude=record.latitude,
                longitude=record.longitude,
            )
            for record in records
        ]

    async def _fetch_from_mvg(self) -> list[Station]:
        station_dtos = await self.client.get_all_stations()
        stations = [self._normalize_station(dto) for dto in station_dtos]
        if stations:
            await self._persist_stations(stations)
            await self._cache_station_list(stations)
        return stations

    async def _persist_stations(self, stations: list[Station]) -> None:
        if self.repository is None:
            return
        payloads = [
            StationPayload(
                station_id=station.id,
                name=station.name,
                place=station.place,
                latitude=station.latitude,
                longitude=station.longitude,
                transport_modes=[],
            )
            for station in stations
        ]
        try:
            await self.repository.upsert_stations(payloads)
        except Exception as exc:
            logger.warning("Failed to persist station catalog: %s", exc)

    async def _cache_station_list(self, stations: list[Station]) -> None:
        """Persist the station catalog into Valkey for future reads."""
        try:
            response = StationListResponse(stations=stations)
            await self.cache.set_json(
                self.CACHE_KEY,
                response.model_dump(mode="json"),
                ttl_seconds=self.settings.mvg_station_list_cache_ttl_seconds,
                stale_ttl_seconds=self.settings.mvg_station_list_cache_stale_ttl_seconds,
            )
        except Exception as exc:
            logger.warning("Failed to cache station list: %s", exc)

    def _normalize_station(self, station: Station | StationDTO) -> Station:
        """Ensure station entries use the API's Pydantic schema."""
        if isinstance(station, Station):
            return station
        return Station(
            id=station.id,
            name=station.name,
            place=station.place,
            latitude=station.latitude,
            longitude=station.longitude,
        )


class DeparturesRefreshProtocol(CacheRefreshProtocol[DeparturesResponse]):
    """Cache refresh protocol for departures endpoint."""

    def __init__(
        self,
        client: MVGClient,
        filter_transport_types: list[TransportType] | None = None,
    ):
        """
        Initialize protocol with optional transport type filtering.

        Args:
            client: MVG client instance
            filter_transport_types: Optional list of transport types to filter via MVG API.
                                    If None, all transport types are returned.
        """
        self.client = client
        # Defensive deduplication in case call sites pass duplicates
        if filter_transport_types:
            seen = set()
            deduplicated = []
            for transport_type in filter_transport_types:
                if transport_type not in seen:
                    deduplicated.append(transport_type)
                    seen.add(transport_type)
            self.filter_transport_types = deduplicated
        else:
            self.filter_transport_types = filter_transport_types

    def cache_name(self) -> str:
        return "mvg_departures"

    def get_model_class(self) -> type[DeparturesResponse]:
        return DeparturesResponse

    async def fetch_data(self, **kwargs: Any) -> DeparturesResponse:
        """
        Fetch departures data with optional transport type filtering.

        This method uses different strategies based on whether transport type filters
        are specified:
        - No filters: Single call to get all transport types for efficiency
        - With filters: Pass filters upstream to MVG API for server-side filtering
        """
        station = kwargs["station"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]

        if self.filter_transport_types:
            # Pass filters upstream to MVG API for server-side filtering
            station_details, departures_list = await self.client.get_departures(
                station_query=station,
                limit=limit,
                offset=offset,
                transport_types=self.filter_transport_types,
            )
        else:
            # No filters: fetch all transport types in a single call for efficiency
            station_details, departures_list = await self.client.get_departures(
                station_query=station,
                limit=limit,
                offset=offset,
                transport_types=None,
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


class StationSearchRefreshProtocol(MvgCacheProtocol[StationSearchResponse]):
    """Optimized cache refresh protocol for station search endpoint using O(1) search index."""

    def __init__(
        self,
        client: MVGClient,
        cache: CacheService,
        station_repository: StationRepository | None,
    ):
        """
        Initialize protocol with search index support.

        Args:
            client: MVG client instance
            cache: Cache service for persistent search index
            station_repository: Repository that holds persisted stations
        """
        self.client = client
        self.search_index = CachedStationSearchIndex(cache)
        self.catalog = StationCatalog(client, cache, station_repository)

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
        all_stations = await self.catalog.get_stations()

        if not all_stations:
            raise MVGStationNotFoundError(f"No stations found for query '{query}'.")

        # Get or build the high-performance search index
        index = await self.search_index.get_index(all_stations)

        # Perform O(1) lookup instead of O(n) linear scan
        stations = await index.search(query, limit)

        if not stations:
            raise MVGStationNotFoundError(f"No stations found for query '{query}'.")

        return StationSearchResponse.from_dtos(query, stations)


class StationListRefreshProtocol(MvgCacheProtocol[StationListResponse]):
    """Simplified cache refresh protocol for station list endpoint."""

    def __init__(
        self,
        client: MVGClient,
        cache: CacheService,
        station_repository: StationRepository | None,
    ):
        self.client = client
        self.catalog = StationCatalog(client, cache, station_repository)

    def cache_name(self) -> str:
        return "mvg_station_list"

    def get_model_class(self) -> type[StationListResponse]:
        return StationListResponse

    def get_ttl_setting_name(self) -> str:
        return "mvg_station_list_cache_ttl_seconds"

    def get_stale_ttl_setting_name(self) -> str:
        return "mvg_station_list_cache_stale_ttl_seconds"

    async def fetch_data(self, **kwargs: Any) -> StationListResponse:
        stations = await self.catalog.get_stations()
        return StationListResponse(stations=stations if stations else [])


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
