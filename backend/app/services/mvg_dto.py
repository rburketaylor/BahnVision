"""Data transfer objects used by the MVG client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List


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
    messages: List[str]


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
    messages: List[str]


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
    intermediate_stops: List[RouteStop]


@dataclass(frozen=True)
class RoutePlan:
    """Complete itinerary returned by MVG."""

    duration_minutes: int | None
    transfers: int | None
    departure: RouteStop | None
    arrival: RouteStop | None
    legs: List[RouteLeg]


__all__ = [
    "Station",
    "Departure",
    "RouteStop",
    "RouteLeg",
    "RoutePlan",
]
