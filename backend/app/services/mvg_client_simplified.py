from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mvg import MvgApi, MvgApiError, TransportType

from app.core.metrics import observe_mvg_request


class StationNotFoundError(Exception):
    """Raised when an MVG station cannot be resolved."""


class MVGServiceError(Exception):
    """Generic wrapper for MVG service failures."""


class RouteNotFoundError(Exception):
    """Raised when MVG cannot provide a route between two stations."""


@dataclass(frozen=True)
class Station:
    """Resolved station details."""

    id: str
    name: str
    place: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Departure:
    """Processed departure information."""

    planned_time: datetime | None
    realtime_time: datetime | None
    delay_minutes: int
    platform: str | None
    realtime: bool
    line: str
    destination: str
    transport_type: str
    icon: str | None
    cancelled: bool
    messages: list[str]


@dataclass(frozen=True)
class RouteStop:
    """Stop details for a leg within a planned route."""

    id: str | None
    name: str | None
    place: str | None
    latitude: float | None
    longitude: float | None
    planned_time: datetime | None
    realtime_time: datetime | None
    platform: str | None
    transport_type: str | None
    line: str | None
    destination: str | None
    delay_minutes: int | None
    messages: list[str]


@dataclass(frozen=True)
class RouteLeg:
    """Single segment of a route between two stops."""

    origin: RouteStop | None
    destination: RouteStop | None
    transport_type: str | None
    line: str | None
    direction: str | None
    duration_minutes: int | None
    distance_meters: int | None
    intermediate_stops: list[RouteStop]


@dataclass(frozen=True)
class RoutePlan:
    """Complete itinerary returned by MVG."""

    duration_minutes: int | None
    transfers: int | None
    departure: RouteStop | None
    arrival: RouteStop | None
    legs: list[RouteLeg]


class DataMapper:
    """Simplified data extraction and transformation utility."""

    @staticmethod
    def safe_get(data: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
        """Safely get a value from dictionary with fallback keys."""
        if not data:
            return default
        for key in keys:
            if key in data:
                return data[key]
        return default

    @staticmethod
    def safe_get_nested(data: dict[str, Any], *paths: list[str]) -> Any:
        """Get value from nested paths like ['station', 'id'] or 'name'."""
        if not data:
            return None

        for path in paths:
            if isinstance(path, str):
                # Direct key access
                if path in data:
                    return data[path]
            elif isinstance(path, list):
                # Nested access
                current = data
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    return current
        return None

    @staticmethod
    def convert_type(value: Any, target_type: type) -> Any:
        """Universal type converter with error handling."""
        if value is None:
            return None

        try:
            if target_type == int:
                return int(float(value))  # Handle "15.0" strings
            elif target_type == float:
                return float(value)
            elif target_type == datetime:
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
            elif target_type == str:
                return str(value) if value is not None else None
            return target_type(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def extract_minutes(value: Any) -> int | None:
        """Extract minutes from various formats."""
        if value is None:
            return None
        if isinstance(value, dict):
            for key in ("minutes", "duration", "total", "value"):
                result = DataMapper.convert_type(value.get(key), int)
                if result is not None:
                    return result
            return None
        return DataMapper.convert_type(value, int)


class MVGClient:
    """Simplified wrapper around the mvg package with cleaner data mapping."""

    async def get_station(self, query: str) -> Station:
        """Resolve a station by query (name or global id)."""
        start = time.perf_counter()
        try:
            raw_station = await asyncio.to_thread(MvgApi.station, query)
        except MvgApiError as exc:
            observe_mvg_request("station_lookup", "error", time.perf_counter() - start)
            raise MVGServiceError("Failed to reach MVG station endpoint.") from exc

        if not raw_station:
            observe_mvg_request("station_lookup", "not_found", time.perf_counter() - start)
            raise StationNotFoundError(f"Station not found for query '{query}'.")

        observe_mvg_request("station_lookup", "success", time.perf_counter() - start)
        return self._map_station(raw_station)

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
            departures = [self._map_departure(item) for item in raw_departures]
            return station, departures

        transport_types_list = list(transport_types)
        tasks = [
            asyncio.to_thread(self._fetch_departures, station.id, limit, offset, [tt])
            for tt in transport_types_list
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        departures = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                departures.extend([self._map_departure(item) for item in result])
            else:
                transport_type = transport_types_list[i] if i < len(transport_types_list) else "unknown"
                print(f"Error fetching departures for transport type {transport_type}: {result}")

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
            observe_mvg_request("station_list", "not_found", time.perf_counter() - start)
            return []

        observe_mvg_request("station_list", "success", time.perf_counter() - start)
        return [self._map_station(item) for item in raw_stations]

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search MVG for stations matching the query string."""
        if limit <= 0:
            return []

        stations = await self.get_all_stations()
        query_lower = query.lower()
        matches: list[Station] = []
        for station in stations:
            if query_lower in station.name.lower() or query_lower in station.place.lower():
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
            raise MVGServiceError("Failed to retrieve route information from MVG.") from exc

        duration = time.perf_counter() - start
        routes_payload = self._extract_routes(raw_routes)
        if not routes_payload:
            observe_mvg_request("route_lookup", "not_found", duration)
            raise RouteNotFoundError(
                f"No MVG routes available between '{origin.name}' and '{destination.name}'."
            )

        observe_mvg_request("route_lookup", "success", duration)
        plans = [self._map_route_plan(item) for item in routes_payload]
        return origin, destination, plans

    @staticmethod
    def _map_station(data: dict[str, Any]) -> Station:
        """Map raw station data to Station model."""
        return Station(
            id=data["id"],
            name=data["name"],
            place=data["place"],
            latitude=data["latitude"],
            longitude=data["longitude"],
        )

    @staticmethod
    def _map_departure(data: dict[str, Any]) -> Departure:
        """Map raw departure data to Departure model."""
        return Departure(
            planned_time=DataMapper.convert_type(data.get("planned"), datetime),
            realtime_time=DataMapper.convert_type(data.get("time"), datetime),
            delay_minutes=DataMapper.convert_type(data.get("delay"), int) or 0,
            platform=DataMapper.convert_type(data.get("platform"), str),
            realtime=bool(data.get("realtime")),
            line=data.get("line", ""),
            destination=data.get("destination", ""),
            transport_type=data.get("type", ""),
            icon=data.get("icon"),
            cancelled=bool(data.get("cancelled")),
            messages=[str(message) for message in data.get("messages", [])],
        )

    @staticmethod
    def _map_route_plan(data: dict[str, Any]) -> RoutePlan:
        """Map raw route plan data to RoutePlan model."""
        return RoutePlan(
            duration_minutes=DataMapper.extract_minutes(data.get("duration")),
            transfers=DataMapper.convert_type(
                DataMapper.safe_get(data, "transfers", "changes"), int
            ),
            departure=MVGClient._map_route_stop(data.get("departure")),
            arrival=MVGClient._map_route_stop(data.get("arrival")),
            legs=MVGClient._map_route_legs(data),
        )

    @staticmethod
    def _map_route_legs(data: dict[str, Any]) -> list[RouteLeg]:
        """Map route legs from raw data."""
        legs_payload = DataMapper.safe_get(data, "legs", "connections") or []
        return [
            leg for leg in (MVGClient._map_route_leg(item) for item in legs_payload if isinstance(item, dict))
            if leg is not None
        ]

    @staticmethod
    def _map_route_leg(data: dict[str, Any]) -> RouteLeg | None:
        """Map raw route leg data to RouteLeg model."""
        origin = MVGClient._map_route_stop(
            DataMapper.safe_get(data, "departure", "origin")
        )
        destination = MVGClient._map_route_stop(
            DataMapper.safe_get(data, "arrival", "destination")
        )

        # Extract transport type with nested fallback
        transport_type = DataMapper.safe_get_nested(
            data, ["transportType"], ["product"], ["line", "transportType"]
        )

        # Extract line information
        line_name = (
            DataMapper.safe_get(data.get("line") or {}, "name", "label", "symbol")
            or data.get("line")
        )

        direction = DataMapper.safe_get(data, "destination", "direction") or (data.get("line") or {}).get("destination")

        duration = DataMapper.extract_minutes(data.get("duration"))
        distance = DataMapper.convert_type(
            DataMapper.safe_get(data, "distance", "distanceInMeters")
            or (data.get("distance") or {}).get("meters") if isinstance(data.get("distance"), dict) else None,
            int
        )

        intermediate_stops = MVGClient._map_intermediate_stops(data)

        # Return None if leg has no meaningful content
        if origin is None and destination is None and not intermediate_stops:
            return None

        return RouteLeg(
            origin=origin,
            destination=destination,
            transport_type=transport_type,
            line=line_name,
            direction=direction,
            duration_minutes=duration,
            distance_meters=distance,
            intermediate_stops=intermediate_stops,
        )

    @staticmethod
    def _map_route_stop(data: dict[str, Any] | None) -> RouteStop | None:
        """Map raw route stop data to RouteStop model."""
        if not data:
            return None

        # Extract station info with nested fallbacks
        station_id = (
            DataMapper.safe_get_nested(data, ["station", "id"], ["stop", "id"], ["station", "globalId"])
            or DataMapper.safe_get(data, "stationId", "stopId")
        )

        name = (
            DataMapper.safe_get_nested(data, ["station", "name"], ["stop", "name"])
            or DataMapper.safe_get(data, "name", "stationName")
        )

        place = (
            DataMapper.safe_get_nested(data, ["station", "place"], ["stop", "place"], ["station", "municipality"])
            or data.get("place")
        )

        latitude = DataMapper.convert_type(
            DataMapper.safe_get_nested(data, ["station", "latitude"], ["stop", "latitude"], ["station", "lat"])
            or data.get("latitude"),
            float
        )

        longitude = DataMapper.convert_type(
            DataMapper.safe_get_nested(data, ["station", "longitude"], ["stop", "longitude"], ["station", "lon"])
            or data.get("longitude"),
            float
        )

        # Extract time information
        planned_time = DataMapper.convert_type(
            DataMapper.safe_get(data, "planned", "plannedTime", "scheduledTime", "scheduledDepartureTime", "scheduledArrivalTime"),
            datetime
        )

        realtime_time = DataMapper.convert_type(
            DataMapper.safe_get(data, "time", "realtime", "departureTime", "arrivalTime"),
            datetime
        )

        # Extract transport information
        transport_type = DataMapper.safe_get_nested(
            data, ["transportType"], ["product"], ["line", "transportType"]
        )

        line_name = (
            DataMapper.safe_get(data.get("line") or {}, "name", "label", "symbol")
            or data.get("line")
        )

        destination = DataMapper.safe_get(data, "destination", "direction") or (data.get("line") or {}).get("destination")

        return RouteStop(
            id=DataMapper.convert_type(station_id, str),
            name=name,
            place=place,
            latitude=latitude,
            longitude=longitude,
            planned_time=planned_time,
            realtime_time=realtime_time,
            platform=DataMapper.convert_type(data.get("platform"), str),
            transport_type=transport_type,
            line=line_name,
            destination=destination,
            delay_minutes=DataMapper.convert_type(
                DataMapper.safe_get(data, "delay", "delayInMinutes"), int
            ),
            messages=[str(message) for message in data.get("messages", [])],
        )

    @staticmethod
    def _map_intermediate_stops(data: dict[str, Any]) -> list[RouteStop]:
        """Map intermediate stops from route leg data."""
        intermediate_raw = DataMapper.safe_get(data, "intermediateStops", "stops") or []
        return [
            stop for stop in (
                MVGClient._map_route_stop(item) for item in intermediate_raw if isinstance(item, dict)
            )
            if stop is not None
        ]

    @staticmethod
    def _fetch_departures(
        station_id: str,
        limit: int,
        offset: int,
        transport_types: list[TransportType] | None,
    ) -> list[dict[str, Any]]:
        client = MvgApi(station_id)
        try:
            return client.departures(limit=limit, offset=offset, transport_types=transport_types)
        except MvgApiError as exc:
            error_msg = str(exc).lower()

            # Check for HTTP 400 errors more robustly
            is_400_error = any(indicator in error_msg for indicator in ["400", "bad request", "client error"])

            if is_400_error:
                print(f"Error fetching departures: Bad API call: {exc}")
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

    @staticmethod
    def _extract_routes(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
        """Extract routes from various possible payload structures."""
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("routes", "connections", "legs", "journeys"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []


def get_client() -> MVGClient:
    """Instantiate a fresh MVG client per request.

    This function is included for backward compatibility with existing import patterns.
    The correct location for this function is app.api.v1.endpoints.mvg.shared.utils.

    Returns:
        A new MVGClient instance
    """
    return MVGClient()


def parse_transport_types(raw_values: Iterable[str]) -> list[TransportType]:
    """Simplified transport type parsing with clean lookup logic."""
    # Build simple lookup map
    transport_map = {}
    for transport_type in TransportType:
        # Add enum name variations
        name_lower = transport_type.name.lower()
        transport_map[name_lower] = transport_type

        # Add display value variations
        if transport_type.value:
            display = transport_type.value[0].lower()
            transport_map[display] = transport_type
            transport_map[display.replace("-", "").replace(" ", "")] = transport_type

    result = []
    for raw in raw_values:
        key = raw.strip().lower()
        if not key:
            continue

        # Try direct lookup
        transport_type = transport_map.get(key)

        # Try normalized version if direct lookup fails
        if not transport_type:
            clean_key = key.replace("-", "").replace(" ", "")
            transport_type = transport_map.get(clean_key)

        if not transport_type:
            raise ValueError(f"Unsupported transport type '{raw}'.")

        result.append(transport_type)

    return result