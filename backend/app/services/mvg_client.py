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


class MVGClient:
    """Thin wrapper around the mvg package with asyncio-friendly helpers."""

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
        return Station(
            id=raw_station["id"],
            name=raw_station["name"],
            place=raw_station["place"],
            latitude=raw_station["latitude"],
            longitude=raw_station["longitude"],
        )

    async def get_departures(
        self,
        station_query: str,
        limit: int = 10,
        offset: int = 0,
        transport_types: Iterable[TransportType] | None = None,
    ) -> tuple[Station, list[Departure]]:
        """Fetch departures for a station specified via query string."""
        station = await self.get_station(station_query)
        start = time.perf_counter()
        try:
            raw_departures = await asyncio.to_thread(
                self._fetch_departures,
                station.id,
                limit,
                offset,
                list(transport_types) if transport_types else None,
            )
        except MvgApiError as exc:
            observe_mvg_request("departures", "error", time.perf_counter() - start)
            raise MVGServiceError("Failed to retrieve departures from MVG.") from exc

        observe_mvg_request("departures", "success", time.perf_counter() - start)
        departures = [self._map_departure(item) for item in raw_departures]
        return station, departures

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search MVG for stations matching the query string."""
        start = time.perf_counter()
        try:
            raw_stations = await asyncio.to_thread(MvgApi.stations, query)
        except MvgApiError as exc:
            observe_mvg_request("station_search", "error", time.perf_counter() - start)
            raise MVGServiceError("Failed to search MVG stations.") from exc

        if not raw_stations:
            observe_mvg_request("station_search", "not_found", time.perf_counter() - start)
            return []

        observe_mvg_request("station_search", "success", time.perf_counter() - start)
        stations: list[Station] = []
        for item in raw_stations:
            stations.append(
                Station(
                    id=item["id"],
                    name=item["name"],
                    place=item["place"],
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                )
            )
            if 0 < limit <= len(stations):
                break
        return stations

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
    def _fetch_departures(
        station_id: str,
        limit: int,
        offset: int,
        transport_types: list[TransportType] | None,
    ) -> list[dict[str, Any]]:
        client = MvgApi(station_id)
        return client.departures(limit=limit, offset=offset, transport_types=transport_types)

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
    def _map_departure(data: dict[str, Any]) -> Departure:
        planned = MVGClient._to_datetime(data.get("planned"))
        realtime = MVGClient._to_datetime(data.get("time"))
        return Departure(
            planned_time=planned,
            realtime_time=realtime,
            delay_minutes=int(data.get("delay") or 0),
            platform=str(data["platform"]) if data.get("platform") is not None else None,
            realtime=bool(data.get("realtime")),
            line=data.get("line", ""),
            destination=data.get("destination", ""),
            transport_type=data.get("type", ""),
            icon=data.get("icon"),
            cancelled=bool(data.get("cancelled")),
            messages=[str(message) for message in data.get("messages", [])],
        )

    @staticmethod
    def _extract_routes(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
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

    @staticmethod
    def _map_route_plan(data: dict[str, Any]) -> RoutePlan:
        duration = MVGClient._to_minutes(data.get("duration"))
        transfers = MVGClient._to_int(data.get("transfers") or data.get("changes"))
        departure = MVGClient._map_route_stop(data.get("departure"))
        arrival = MVGClient._map_route_stop(data.get("arrival"))

        legs_payload = data.get("legs") or data.get("connections") or []
        legs = [
            leg
            for leg in (MVGClient._map_route_leg(item) for item in legs_payload if isinstance(item, dict))
            if leg is not None
        ]
        return RoutePlan(
            duration_minutes=duration,
            transfers=transfers,
            departure=departure,
            arrival=arrival,
            legs=legs,
        )

    @staticmethod
    def _map_route_leg(data: dict[str, Any]) -> RouteLeg | None:
        origin = MVGClient._map_route_stop(data.get("departure") or data.get("origin"))
        destination = MVGClient._map_route_stop(data.get("arrival") or data.get("destination"))
        transport_type = (
            data.get("transportType")
            or data.get("product")
            or ((data.get("line") or {}).get("transportType"))
        )
        line_info = data.get("line") or {}
        line_name = (
            line_info.get("name")
            or line_info.get("label")
            or line_info.get("symbol")
            or data.get("line")
        )
        direction = (
            data.get("destination")
            or line_info.get("destination")
            or data.get("direction")
        )
        duration = MVGClient._to_minutes(data.get("duration"))
        distance = MVGClient._to_int(
            data.get("distance")
            or data.get("distanceInMeters")
            or (data.get("distance") or {}).get("meters") if isinstance(data.get("distance"), dict) else None
        )
        intermediate_raw = data.get("intermediateStops") or data.get("stops") or []
        intermediate_stops = [
            stop
            for stop in (MVGClient._map_route_stop(item) for item in intermediate_raw if isinstance(item, dict))
            if stop is not None
        ]

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
        if not data:
            return None
        station_payload = data.get("station") or data.get("stop") or {}
        identifier = (
            station_payload.get("id")
            or station_payload.get("globalId")
            or data.get("stationId")
            or data.get("stopId")
        )
        name = station_payload.get("name") or data.get("name") or data.get("stationName")
        place = station_payload.get("place") or station_payload.get("municipality") or data.get("place")
        latitude = MVGClient._to_float(
            station_payload.get("latitude") or station_payload.get("lat") or data.get("latitude")
        )
        longitude = MVGClient._to_float(
            station_payload.get("longitude") or station_payload.get("lon") or data.get("longitude")
        )
        planned_time = MVGClient._to_datetime(
            data.get("planned")
            or data.get("plannedTime")
            or data.get("scheduledTime")
            or data.get("scheduledDepartureTime")
            or data.get("scheduledArrivalTime")
        )
        realtime_time = MVGClient._to_datetime(
            data.get("time")
            or data.get("realtime")
            or data.get("departureTime")
            or data.get("arrivalTime")
        )
        platform = str(data.get("platform")) if data.get("platform") is not None else None
        transport_type = (
            data.get("transportType")
            or data.get("product")
            or (data.get("line") or {}).get("transportType")
        )
        line_info = data.get("line") or {}
        line_name = (
            line_info.get("name")
            or line_info.get("label")
            or line_info.get("symbol")
            or data.get("line")
        )
        destination = (
            data.get("destination")
            or line_info.get("destination")
            or data.get("direction")
        )
        delay = data.get("delay") or data.get("delayInMinutes")
        messages = [str(message) for message in data.get("messages", [])]

        return RouteStop(
            id=str(identifier) if identifier is not None else None,
            name=name,
            place=place,
            latitude=latitude,
            longitude=longitude,
            planned_time=planned_time,
            realtime_time=realtime_time,
            platform=platform,
            transport_type=transport_type,
            line=line_name,
            destination=destination,
            delay_minutes=int(delay) if delay is not None else None,
            messages=messages,
        )

    @staticmethod
    def _to_datetime(timestamp: int | float | None) -> datetime | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)

    @staticmethod
    def _to_minutes(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, dict):
            for key in ("minutes", "duration", "total", "value"):
                candidate = value.get(key)
                if candidate is not None:
                    try:
                        return int(candidate)
                    except (TypeError, ValueError):
                        continue
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def parse_transport_types(raw_values: Iterable[str]) -> list[TransportType]:
    """Convert string inputs into MVG transport type enums."""
    normalized_map: dict[str, TransportType] = {}
    for item in TransportType:
        normalized_map[item.name.lower()] = item
        display = item.value[0].lower()
        normalized_map[display] = item
        normalized_map[display.replace("-", "").replace(" ", "")] = item

    transport_types: list[TransportType] = []
    for raw in raw_values:
        key = raw.strip().lower()
        if not key:
            continue
        candidates = (
            key,
            key.replace("-", ""),
            key.replace(" ", ""),
            key.replace(" ", "").replace("-", ""),
        )
        transport_type = None
        for candidate in candidates:
            transport_type = normalized_map.get(candidate)
            if transport_type:
                break
        if not transport_type:
            raise ValueError(f"Unsupported transport type '{raw}'.")
        transport_types.append(transport_type)
    return transport_types
