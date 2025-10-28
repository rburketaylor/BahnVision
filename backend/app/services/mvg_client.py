from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mvg import MvgApi, MvgApiError, TransportType


class StationNotFoundError(Exception):
    """Raised when an MVG station cannot be resolved."""


class MVGServiceError(Exception):
    """Generic wrapper for MVG service failures."""


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


class MVGClient:
    """Thin wrapper around the mvg package with asyncio-friendly helpers."""

    async def get_station(self, query: str) -> Station:
        """Resolve a station by query (name or global id)."""
        try:
            raw_station = await asyncio.to_thread(MvgApi.station, query)
        except MvgApiError as exc:
            raise MVGServiceError("Failed to reach MVG station endpoint.") from exc

        if not raw_station:
            raise StationNotFoundError(f"Station not found for query '{query}'.")

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
        try:
            raw_departures = await asyncio.to_thread(
                self._fetch_departures,
                station.id,
                limit,
                offset,
                list(transport_types) if transport_types else None,
            )
        except MvgApiError as exc:
            raise MVGServiceError("Failed to retrieve departures from MVG.") from exc

        departures = [self._map_departure(item) for item in raw_departures]
        return station, departures

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Search MVG for stations matching the query string."""
        try:
            raw_stations = await asyncio.to_thread(MvgApi.stations, query)
        except MvgApiError as exc:
            raise MVGServiceError("Failed to search MVG stations.") from exc

        if not raw_stations:
            return []

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
    def _to_datetime(timestamp: int | float | None) -> datetime | None:
        if timestamp is None:
            return None
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)


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
