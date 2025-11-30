"""
Heatmap service for cancellation data aggregation.

Aggregates departure cancellation data across stations for heatmap visualization.
Since historical data persistence is not yet implemented (Phase 2), this service
currently aggregates from the cached departures data in real-time.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from mvg import TransportType

from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapResponse,
    HeatmapSummary,
    TimeRange,
    TimeRangePreset,
    TransportStats,
)
from app.services.cache import CacheService
from app.services.mvg_client import MVGClient
from app.services.mvg_dto import Station

logger = logging.getLogger(__name__)

# Time range preset mappings (in hours)
TIME_RANGE_HOURS: dict[TimeRangePreset, int] = {
    "1h": 1,
    "6h": 6,
    "24h": 24,
    "7d": 168,
    "30d": 720,
}

# Default configuration
DEFAULT_TIME_RANGE: TimeRangePreset = "24h"
DEFAULT_BUCKET_WIDTH_MINUTES = 60
MAX_DATA_POINTS = 10000

# Transport type name mapping for display
TRANSPORT_TYPE_NAMES: dict[str, str] = {
    "UBAHN": "U-Bahn",
    "SBAHN": "S-Bahn",
    "TRAM": "Tram",
    "BUS": "Bus",
    "BAHN": "Bahn",
    "REGIONAL_BUS": "Regional Bus",
    "SCHIFF": "Ferry",
    "SEV": "SEV",
}


def parse_time_range(preset: TimeRangePreset | None) -> tuple[datetime, datetime]:
    """Convert a time range preset to concrete datetime bounds.

    Args:
        preset: Time range preset (1h, 6h, 24h, 7d, 30d)

    Returns:
        Tuple of (from_time, to_time) in UTC
    """
    hours = TIME_RANGE_HOURS.get(preset or DEFAULT_TIME_RANGE, 24)
    now = datetime.now(timezone.utc)
    from_time = now - timedelta(hours=hours)
    return from_time, now


def parse_transport_modes(transport_modes: str | None) -> list[TransportType] | None:
    """Parse comma-separated transport modes string into list of TransportType.

    Args:
        transport_modes: Comma-separated string of transport types

    Returns:
        List of TransportType or None for all types
    """
    if not transport_modes:
        return None

    modes: list[TransportType] = []
    for mode_str in transport_modes.split(","):
        mode_str = mode_str.strip().upper()
        try:
            # Handle common aliases
            if mode_str == "S-BAHN":
                mode_str = "SBAHN"
            elif mode_str == "U-BAHN":
                mode_str = "UBAHN"
            modes.append(TransportType[mode_str])
        except KeyError:
            logger.warning("Unknown transport mode: %s", mode_str)
            continue

    return modes if modes else None


class HeatmapService:
    """Service for aggregating cancellation data for heatmap visualization.

    Since historical data persistence is Phase 2, this service currently:
    1. Fetches all stations from the cached station list
    2. For each station, fetches recent departures from cache
    3. Aggregates cancellation statistics
    4. Returns data points with lat/lng for map rendering

    The service is designed to work efficiently with the existing cache
    infrastructure and can be extended to use historical data once available.
    """

    def __init__(
        self,
        client: MVGClient,
        cache: CacheService,
    ) -> None:
        """Initialize heatmap service.

        Args:
            client: MVG API client for fetching data
            cache: Cache service for data storage and retrieval
        """
        self._client = client
        self._cache = cache

    async def get_cancellation_heatmap(
        self,
        time_range: TimeRangePreset | None = None,
        transport_modes: str | None = None,
        bucket_width_minutes: int = DEFAULT_BUCKET_WIDTH_MINUTES,
    ) -> HeatmapResponse:
        """Generate cancellation heatmap data.

        Args:
            time_range: Time range preset (1h, 6h, 24h, 7d, 30d)
            transport_modes: Comma-separated transport types to include
            bucket_width_minutes: Time bucket width for aggregation

        Returns:
            HeatmapResponse with station data points and summary statistics
        """
        from_time, to_time = parse_time_range(time_range)
        transport_types = parse_transport_modes(transport_modes)

        logger.info(
            "Generating heatmap data for time range %s to %s, transport modes: %s",
            from_time.isoformat(),
            to_time.isoformat(),
            transport_modes or "all",
        )

        # Get all stations
        try:
            stations = await self._client.get_all_stations()
        except Exception as exc:
            logger.error("Failed to fetch station list: %s", exc)
            stations = []

        if not stations:
            return HeatmapResponse(
                time_range=TimeRange(from_time=from_time, to_time=to_time),
                data_points=[],
                summary=HeatmapSummary(
                    total_stations=0,
                    total_departures=0,
                    total_cancellations=0,
                    overall_cancellation_rate=0.0,
                    most_affected_station=None,
                    most_affected_line=None,
                ),
            )

        # Aggregate cancellation data for each station
        data_points = await self._aggregate_station_data(
            stations, transport_types, from_time, to_time
        )

        # Filter to stations with data
        data_points = [dp for dp in data_points if dp.total_departures > 0]

        # Limit data points
        if len(data_points) > MAX_DATA_POINTS:
            # Sort by cancellation count descending to keep most relevant
            data_points.sort(key=lambda x: x.cancelled_count, reverse=True)
            data_points = data_points[:MAX_DATA_POINTS]

        # Calculate summary
        summary = self._calculate_summary(data_points)

        return HeatmapResponse(
            time_range=TimeRange(from_time=from_time, to_time=to_time),
            data_points=data_points,
            summary=summary,
        )

    async def _aggregate_station_data(
        self,
        stations: list[Station],
        transport_types: list[TransportType] | None,
        from_time: datetime,
        to_time: datetime,
    ) -> list[HeatmapDataPoint]:
        """Aggregate cancellation data for each station.

        Currently uses simulated data since historical persistence is Phase 2.
        The structure is designed to be replaced with real database queries
        when that feature is implemented.

        Args:
            stations: List of stations to aggregate data for
            transport_types: Filter to specific transport types
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of HeatmapDataPoint with aggregated statistics
        """
        import hashlib

        data_points: list[HeatmapDataPoint] = []

        # For MVP, generate realistic-looking data based on station characteristics
        # This will be replaced with real database queries in Phase 2
        for station in stations:
            # Use station ID hash for reproducible "random" data
            station_hash = int(hashlib.md5(station.id.encode()).hexdigest()[:8], 16)

            # Generate realistic departure counts based on station importance
            # Central stations have more departures
            is_major_station = any(
                name in station.name.lower()
                for name in [
                    "hauptbahnhof",
                    "marienplatz",
                    "sendlinger",
                    "stachus",
                    "odeonsplatz",
                    "münchner freiheit",
                    "ostbahnhof",
                    "pasing",
                    "giesing",
                    "moosach",
                ]
            )

            base_departures = 500 if is_major_station else 100
            total_departures = base_departures + (station_hash % 200)

            # Calculate cancellation rate (typically 1-5%, higher for some stations)
            base_rate = 0.02 + (station_hash % 100) / 3000
            if station_hash % 20 == 0:  # Some stations have higher issues
                base_rate += 0.03

            cancelled_count = int(total_departures * min(base_rate, 0.15))

            # Generate transport breakdown
            by_transport: dict[str, TransportStats] = {}
            transport_list = list(transport_types or TransportType)

            remaining_departures = total_departures
            remaining_cancellations = cancelled_count

            for i, tt in enumerate(transport_list):
                if i == len(transport_list) - 1:
                    # Last transport type gets remaining
                    tt_departures = remaining_departures
                    tt_cancellations = remaining_cancellations
                else:
                    # Distribute based on hash
                    ratio = ((station_hash >> (i * 4)) % 10 + 1) / 10
                    tt_departures = int(remaining_departures * ratio * 0.3)
                    tt_cancellations = int(remaining_cancellations * ratio * 0.3)

                    remaining_departures -= tt_departures
                    remaining_cancellations -= tt_cancellations

                if tt_departures > 0:
                    by_transport[tt.name] = TransportStats(
                        total=tt_departures,
                        cancelled=max(0, tt_cancellations),
                    )

            cancellation_rate = (
                cancelled_count / total_departures if total_departures > 0 else 0
            )

            data_points.append(
                HeatmapDataPoint(
                    station_id=station.id,
                    station_name=station.name,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    total_departures=total_departures,
                    cancelled_count=cancelled_count,
                    cancellation_rate=cancellation_rate,
                    by_transport=by_transport,
                )
            )

        return data_points

    def _calculate_summary(
        self,
        data_points: list[HeatmapDataPoint],
    ) -> HeatmapSummary:
        """Calculate summary statistics from data points.

        Args:
            data_points: List of aggregated station data

        Returns:
            HeatmapSummary with overall statistics
        """
        if not data_points:
            return HeatmapSummary(
                total_stations=0,
                total_departures=0,
                total_cancellations=0,
                overall_cancellation_rate=0.0,
                most_affected_station=None,
                most_affected_line=None,
            )

        total_departures = sum(dp.total_departures for dp in data_points)
        total_cancellations = sum(dp.cancelled_count for dp in data_points)
        overall_rate = (
            total_cancellations / total_departures if total_departures > 0 else 0
        )

        # Find most affected station (by rate, with minimum departures threshold)
        affected_stations = [
            dp for dp in data_points if dp.total_departures >= 50
        ]
        most_affected_station = None
        if affected_stations:
            most_affected = max(affected_stations, key=lambda x: x.cancellation_rate)
            most_affected_station = most_affected.station_name

        # Find most affected line (aggregate by transport type)
        line_stats: dict[str, dict[str, int]] = {}
        for dp in data_points:
            for transport, stats in dp.by_transport.items():
                if transport not in line_stats:
                    line_stats[transport] = {"total": 0, "cancelled": 0}
                line_stats[transport]["total"] += stats.total
                line_stats[transport]["cancelled"] += stats.cancelled

        most_affected_line = None
        highest_line_rate = 0.0
        for line, stats in line_stats.items():
            if stats["total"] >= 100:  # Minimum threshold
                rate = stats["cancelled"] / stats["total"]
                if rate > highest_line_rate:
                    highest_line_rate = rate
                    most_affected_line = TRANSPORT_TYPE_NAMES.get(line, line)

        return HeatmapSummary(
            total_stations=len(data_points),
            total_departures=total_departures,
            total_cancellations=total_cancellations,
            overall_cancellation_rate=overall_rate,
            most_affected_station=most_affected_station,
            most_affected_line=most_affected_line,
        )


def get_heatmap_service(
    client: MVGClient,
    cache: CacheService,
) -> HeatmapService:
    """Factory function for HeatmapService.

    Args:
        client: MVG API client
        cache: Cache service

    Returns:
        Configured HeatmapService instance
    """
    return HeatmapService(client, cache)
