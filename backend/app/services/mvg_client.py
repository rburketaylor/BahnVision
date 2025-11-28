from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from mvg import MvgApi, MvgApiError, TransportType

from app.core.metrics import observe_mvg_request, record_mvg_transport_request
from app.services.mvg_dto import Departure, RouteLeg, RoutePlan, RouteStop, Station
from app.services.mvg_errors import (
    MVGServiceError,
    RouteNotFoundError,
    StationNotFoundError,
)
from app.services.mvg_mapping import (
    extract_routes,
    map_departure,
    map_route_plan,
    map_station,
)

logger = logging.getLogger(__name__)

# Re-export DTOs and exceptions for backward compatibility
__all__ = [
    "MVGClient",
    "get_client",
    # DTOs
    "Station",
    "Departure",
    "RoutePlan",
    "RouteLeg",
    "RouteStop",
    # Exceptions
    "MVGServiceError",
    "StationNotFoundError",
    "RouteNotFoundError",
    # External
    "MvgApiError",
    "TransportType",
]

# Re-export MvgApiError for convenience - already imported above


class MVGClient:
    """Async wrapper for MVG API with caching support."""

    def __init__(self, cache_service: Any | None = None):
        """
        Initialize MVG client with optional cache service for station search optimization.

        Args:
            cache_service: Optional CacheService for efficient station searches
        """
        self._cache_service = cache_service
        self._search_index: Any | None = None

    def _get_search_index(self):
        """Get cached search index if cache service is available."""
        if self._cache_service and self._search_index is None:
            # Import here to avoid circular import
            from app.api.v1.shared.station_search_index import CachedStationSearchIndex

            self._search_index = CachedStationSearchIndex(self._cache_service)
        return self._search_index

    async def get_station(self, query: str) -> Station:
        """Resolve a station by query (name or global id)."""
        start = time.perf_counter()
        try:
            raw_station = await asyncio.to_thread(MvgApi.station, query)
        except MvgApiError as exc:
            observe_mvg_request("station_lookup", "error", time.perf_counter() - start)
            raise MVGServiceError("Failed to reach MVG station endpoint.") from exc

        if not raw_station:
            observe_mvg_request(
                "station_lookup", "not_found", time.perf_counter() - start
            )
            raise StationNotFoundError(f"Station not found for query '{query}'.")

        observe_mvg_request("station_lookup", "success", time.perf_counter() - start)
        return map_station(raw_station)

    async def get_departures(
        self,
        station_query: str,
        limit: int = 10,
        offset: int = 0,
        transport_types: Iterable[TransportType] | None = None,
    ) -> tuple[Station, list[Departure]]:
        """Fetch departures for a station specified via query string."""
        station = await self.get_station(station_query)

        if not transport_types:
            raw_departures = await asyncio.to_thread(
                self._fetch_departures,
                station.id,
                limit,
                offset,
                None,
            )
            departures = [map_departure(item) for item in raw_departures]
            return station, departures

        transport_types_list = list(transport_types)
        tasks = [
            asyncio.to_thread(self._fetch_departures, station.id, limit, offset, [tt])
            for tt in transport_types_list
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        departures = []
        for i, result in enumerate(results):
            transport_type = (
                transport_types_list[i] if i < len(transport_types_list) else "unknown"
            )
            transport_type_name = getattr(transport_type, "name", str(transport_type))

            if isinstance(result, Exception):
                # Record failure metric
                if isinstance(result, MvgApiError):
                    error_msg = str(result).lower()
                    if any(
                        indicator in error_msg
                        for indicator in ["400", "bad request", "client error"]
                    ):
                        record_mvg_transport_request(
                            "departures", transport_type_name, "bad_request"
                        )
                        reason = "bad request"
                    elif any(
                        indicator in error_msg for indicator in ["timeout", "timed out"]
                    ):
                        record_mvg_transport_request(
                            "departures", transport_type_name, "timeout"
                        )
                        reason = "timeout"
                    else:
                        record_mvg_transport_request(
                            "departures", transport_type_name, "error"
                        )
                        reason = "MVG API error"
                else:
                    record_mvg_transport_request(
                        "departures", transport_type_name, "error"
                    )
                    reason = "unexpected error"

                logger.warning(
                    "Error fetching departures for station %s, transport type %s: %s - %s",
                    station_query,
                    transport_type_name,
                    reason,
                    str(result),
                )
                # Fail-fast: raise error immediately for any transport type failure
                raise MVGServiceError(
                    f"Failed to fetch departures for transport type {transport_type_name}: {reason}"
                ) from result
            elif isinstance(result, list):
                # Record success metric
                record_mvg_transport_request(
                    "departures", transport_type_name, "success"
                )
                departures.extend([map_departure(item) for item in result])
            else:
                # This shouldn't happen, but handle it gracefully
                record_mvg_transport_request("departures", transport_type_name, "error")
                logger.warning(
                    "Unexpected result type for station %s, transport type %s: %s",
                    station_query,
                    transport_type_name,
                    type(result).__name__,
                )
                raise MVGServiceError(
                    f"Unexpected result type for transport type {transport_type_name}"
                )

        departures.sort(key=lambda d: (d.planned_time is None, d.planned_time))
        return station, departures[:limit]

    async def get_all_stations(self) -> list[Station]:
        """Fetch all MVG stations (cached)."""
        start = time.perf_counter()
        try:
            raw_stations = await asyncio.to_thread(MvgApi.stations)
        except MvgApiError as exc:
            observe_mvg_request("station_list", "error", time.perf_counter() - start)
            raise MVGServiceError("Failed to fetch MVG station list.") from exc

        if not raw_stations:
            observe_mvg_request(
                "station_list", "not_found", time.perf_counter() - start
            )
            return []

        observe_mvg_request("station_list", "success", time.perf_counter() - start)
        return [map_station(item) for item in raw_stations]

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search MVG for stations matching the query string using optimized search index."""
        if limit <= 0:
            return []

        # Try to use optimized search index if cache service is available
        search_index = self._get_search_index()
        if search_index:
            try:
                # Get all stations once and build/use search index
                stations = await self.get_all_stations()
                index = await search_index.get_index(stations)
                return await index.search(query, limit)
            except Exception as e:
                logger.warning(
                    f"Failed to use optimized station search index, falling back to linear search: {e}"
                )

        # Fallback to the original linear approach (but still cached via get_all_stations)
        stations = await self.get_all_stations()
        query_lower = query.lower()
        matches: list[Station] = []
        for station in stations:
            if (
                query_lower in station.name.lower()
                or query_lower in station.place.lower()
            ):
                matches.append(station)
                if len(matches) >= limit:
                    break
        return matches

    async def plan_route(
        self,
        origin_query: str,
        destination_query: str,
        departure_time: datetime | None = None,
        arrival_time: datetime | None = None,
        transport_types: Iterable[TransportType] | None = None,
    ) -> tuple[Station, Station, list[RoutePlan]]:
        """Plan a journey between two stations."""
        origin = await self.get_station(origin_query)
        destination = await self.get_station(destination_query)

        start = time.perf_counter()
        try:
            raw_routes = await asyncio.to_thread(
                self._fetch_routes,
                origin.id,
                destination.id,
                departure_time,
                arrival_time,
                list(transport_types) if transport_types else None,
            )
        except MvgApiError as exc:
            observe_mvg_request("route_lookup", "error", time.perf_counter() - start)
            raise MVGServiceError(
                "Failed to retrieve route information from MVG."
            ) from exc

        duration = time.perf_counter() - start
        routes_payload = extract_routes(raw_routes)
        if not routes_payload:
            observe_mvg_request("route_lookup", "not_found", duration)
            raise RouteNotFoundError(
                f"No MVG routes available between '{origin.name}' and '{destination.name}'."
            )

        observe_mvg_request("route_lookup", "success", duration)
        plans = [map_route_plan(item) for item in routes_payload]
        return origin, destination, plans

    @staticmethod
    def _fetch_departures(
        station_id: str,
        limit: int,
        offset: int,
        transport_types: list[TransportType] | None,
    ) -> list[dict[str, Any]]:
        client = MvgApi(station_id)
        try:
            return client.departures(
                limit=limit, offset=offset, transport_types=transport_types
            )
        except MvgApiError as exc:
            error_msg = str(exc).lower()

            # Check for HTTP 400 errors more robustly
            is_400_error = any(
                indicator in error_msg
                for indicator in ["400", "bad request", "client error"]
            )

            if is_400_error:
                logger.debug("Bad API call for departures: %s", exc)
                return []
            raise

    @staticmethod
    def _fetch_routes(
        origin_id: str,
        destination_id: str,
        departure_time: datetime | None,
        arrival_time: datetime | None,
        transport_types: list[TransportType] | None,
    ) -> dict[str, Any]:
        client = MvgApi(origin_id)
        kwargs: dict[str, Any] = {"destination": destination_id}
        if departure_time is not None:
            kwargs["departure"] = departure_time
        if arrival_time is not None:
            kwargs["arrival"] = arrival_time
        if transport_types:
            kwargs["transport_types"] = transport_types
        return client.route(**kwargs)


def get_client() -> MVGClient:
    """Instantiate a fresh MVG client per request.

    This function is included for backward compatibility with existing import patterns.
    The correct location for this function is app.api.v1.endpoints.mvg.shared.utils.

    Returns:
        A new MVGClient instance
    """
    return MVGClient()
