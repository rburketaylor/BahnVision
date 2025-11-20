"""Pure mapping utilities for MVG payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.mvg_dto import Departure, RouteLeg, RoutePlan, RouteStop, Station


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
                if path in data:
                    return data[path]
            elif isinstance(path, list):
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
            if target_type is int:
                return int(float(value))
            if target_type is float:
                return float(value)
            if target_type is datetime:
                return datetime.fromtimestamp(int(value), tz=timezone.utc)
            if target_type is str:
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


def map_station(data: dict[str, Any]) -> Station:
    """Map raw station data to Station DTO."""
    return Station(
        id=data["id"],
        name=data["name"],
        place=data["place"],
        latitude=data["latitude"],
        longitude=data["longitude"],
    )


def map_departure(data: dict[str, Any]) -> Departure:
    """Map raw departure data to Departure DTO."""
    planned_time = DataMapper.convert_type(data.get("planned"), datetime)
    realtime_time = DataMapper.convert_type(data.get("time"), datetime)
    delay_minutes = DataMapper.convert_type(data.get("delay"), int) or 0

    cancelled = bool(data.get("cancelled"))

    if planned_time and realtime_time and not cancelled and delay_minutes <= 0:
        actual_delay = (realtime_time - planned_time).total_seconds() / 60
        if actual_delay <= 1:
            planned_time = None
    elif cancelled and planned_time:
        pass

    return Departure(
        planned_time=planned_time,
        realtime_time=realtime_time,
        delay_minutes=delay_minutes,
        platform=DataMapper.convert_type(data.get("platform"), str),
        realtime=bool(data.get("realtime")),
        line=data.get("line", ""),
        destination=data.get("destination", ""),
        transport_type=data.get("type", ""),
        icon=data.get("icon"),
        cancelled=bool(data.get("cancelled")),
        messages=[str(message) for message in data.get("messages", [])],
    )


def map_route_plan(data: dict[str, Any]) -> RoutePlan:
    """Map raw route plan data to RoutePlan DTO."""
    return RoutePlan(
        duration_minutes=DataMapper.extract_minutes(data.get("duration")),
        transfers=DataMapper.convert_type(
            DataMapper.safe_get(data, "transfers", "changes"), int
        ),
        departure=map_route_stop(data.get("departure")),
        arrival=map_route_stop(data.get("arrival")),
        legs=map_route_legs(data),
    )


def map_route_legs(data: dict[str, Any]) -> list[RouteLeg]:
    """Map route legs from raw data."""
    legs_payload = DataMapper.safe_get(data, "legs", "connections") or []
    return [
        leg
        for leg in (
            map_route_leg(item) for item in legs_payload if isinstance(item, dict)
        )
        if leg is not None
    ]


def map_route_leg(data: dict[str, Any]) -> RouteLeg | None:
    """Map raw route leg data to RouteLeg DTO."""
    origin = map_route_stop(DataMapper.safe_get(data, "departure", "origin"))
    destination = map_route_stop(DataMapper.safe_get(data, "arrival", "destination"))

    transport_type = DataMapper.safe_get_nested(
        data, ["transportType"], ["product"], ["line", "transportType"]
    )

    line_payload = data.get("line") or {}
    line_name = DataMapper.safe_get(
        line_payload, "name", "label", "symbol"
    ) or data.get("line")

    direction = DataMapper.safe_get(
        data, "destination", "direction"
    ) or line_payload.get("destination")

    duration = DataMapper.extract_minutes(data.get("duration"))
    distance_val = DataMapper.safe_get(data, "distance", "distanceInMeters")
    if isinstance(distance_val, dict):
        distance_val = distance_val.get("meters")

    distance = DataMapper.convert_type(distance_val, int)

    intermediate_stops = map_intermediate_stops(data)

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


def map_route_stop(data: dict[str, Any] | None) -> RouteStop | None:
    """Map raw route stop data to RouteStop DTO."""
    if not data:
        return None

    station_id = DataMapper.safe_get_nested(
        data, ["station", "id"], ["stop", "id"], ["station", "globalId"]
    ) or DataMapper.safe_get(data, "stationId", "stopId")

    name = DataMapper.safe_get_nested(
        data, ["station", "name"], ["stop", "name"]
    ) or DataMapper.safe_get(data, "name", "stationName")

    place = DataMapper.safe_get_nested(
        data, ["station", "place"], ["stop", "place"], ["station", "municipality"]
    ) or data.get("place")

    latitude = DataMapper.convert_type(
        DataMapper.safe_get_nested(
            data, ["station", "latitude"], ["stop", "latitude"], ["station", "lat"]
        )
        or data.get("latitude"),
        float,
    )

    longitude = DataMapper.convert_type(
        DataMapper.safe_get_nested(
            data, ["station", "longitude"], ["stop", "longitude"], ["station", "lon"]
        )
        or data.get("longitude"),
        float,
    )

    planned_time = DataMapper.convert_type(
        DataMapper.safe_get(
            data,
            "planned",
            "plannedTime",
            "scheduledTime",
            "scheduledDepartureTime",
            "scheduledArrivalTime",
        ),
        datetime,
    )

    realtime_time = DataMapper.convert_type(
        DataMapper.safe_get(data, "time", "realtime", "departureTime", "arrivalTime"),
        datetime,
    )

    transport_type = DataMapper.safe_get_nested(
        data, ["transportType"], ["product"], ["line", "transportType"]
    )

    line_payload = data.get("line") or {}
    line_name = DataMapper.safe_get(
        line_payload, "name", "label", "symbol"
    ) or data.get("line")

    destination = DataMapper.safe_get(
        data, "destination", "direction"
    ) or line_payload.get("destination")

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


def map_intermediate_stops(data: dict[str, Any]) -> list[RouteStop]:
    """Map intermediate stops from route leg data."""
    intermediate_raw = DataMapper.safe_get(data, "intermediateStops", "stops") or []
    return [
        stop
        for stop in (
            map_route_stop(item) for item in intermediate_raw if isinstance(item, dict)
        )
        if stop is not None
    ]


def extract_routes(payload: dict[str, Any] | list[Any] | None) -> list[dict[str, Any]]:
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


__all__ = [
    "DataMapper",
    "map_station",
    "map_departure",
    "map_route_plan",
    "map_route_legs",
    "map_route_leg",
    "map_route_stop",
    "map_intermediate_stops",
    "extract_routes",
]
