"""
Heatmap service for cancellation data aggregation.

Aggregates departure cancellation data across stations for heatmap visualization.
Uses real GTFS-RT data from the station_aggregations table when available,
falling back to simulated data when historical data is not yet collected.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapResponse,
    HeatmapSummary,
    TimeRange,
    TimeRangePreset,
    TransportStats,
)
from app.persistence.models import RealtimeStationStats
from app.services.cache import CacheService
from app.services.gtfs_schedule import GTFSScheduleService

if TYPE_CHECKING:
    pass

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

# Data density control
MIN_CANCELLATION_RATE = 0.01  # 1% minimum
MIN_DEPARTURES = 10  # Minimum departures to be significant

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

# GTFS route_type mapping to our transport types
GTFS_ROUTE_TYPES: dict[int, str] = {
    0: "TRAM",  # Tram, Streetcar, Light rail
    1: "UBAHN",  # Subway, Metro
    2: "BAHN",  # Rail
    3: "BUS",  # Bus
    4: "SCHIFF",  # Ferry
    5: "TRAM",  # Cable tram
    6: "TRAM",  # Aerial lift, gondola
    7: "TRAM",  # Funicular
    11: "TRAM",  # Trolleybus
    12: "BAHN",  # Monorail
    100: "BAHN",  # Railway Service
    109: "SBAHN",  # Suburban Railway
    400: "UBAHN",  # Urban Railway Service
    700: "BUS",  # Bus Service
    900: "TRAM",  # Tram Service
    1000: "SCHIFF",  # Water Transport Service
}

# Reverse mapping for filtering
TRANSPORT_TO_ROUTE_TYPES: dict[str, list[int]] = {
    "TRAM": [0, 5, 6, 7, 11, 900],
    "UBAHN": [1, 400],
    "BAHN": [2, 12, 100],
    "BUS": [3, 700],
    "SCHIFF": [4, 1000],
    "SBAHN": [109],
}


@dataclass
class StopInfo:
    """Simple stop info for heatmap generation."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


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


def parse_transport_modes(transport_modes: str | None) -> list[str] | None:
    """Parse comma-separated transport modes string into list of transport type names.

    Args:
        transport_modes: Comma-separated string of transport types

    Returns:
        List of transport type names or None for all types
    """
    if not transport_modes:
        return None

    modes: list[str] = []
    for mode_str in transport_modes.split(","):
        mode_str = mode_str.strip().upper()
        # Handle common aliases
        if mode_str == "S-BAHN":
            mode_str = "SBAHN"
        elif mode_str == "U-BAHN":
            mode_str = "UBAHN"
        if mode_str in TRANSPORT_TYPE_NAMES:
            modes.append(mode_str)
        else:
            logger.warning("Unknown transport mode: %s", mode_str)

    return modes if modes else None


class HeatmapService:
    """Service for aggregating cancellation data for heatmap visualization.

    Queries pre-computed station aggregations from the database when available.
    Falls back to simulated data when historical data collection is still building up.
    """

    def __init__(
        self,
        gtfs_schedule: GTFSScheduleService,
        cache: CacheService,
        session: AsyncSession | None = None,
    ) -> None:
        """Initialize heatmap service.

        Args:
            gtfs_schedule: GTFS schedule service for fetching stop data
            cache: Cache service for data storage and retrieval
            session: Optional database session for aggregation queries
        """
        self._gtfs_schedule = gtfs_schedule
        self._cache = cache
        self._session = session

    async def get_cancellation_heatmap(
        self,
        time_range: TimeRangePreset | None = None,
        transport_modes: str | None = None,
        bucket_width_minutes: int = DEFAULT_BUCKET_WIDTH_MINUTES,
        zoom_level: int = 10,
        max_points: int | None = None,
    ) -> HeatmapResponse:
        """Generate cancellation heatmap data.

        Args:
            time_range: Time range preset (1h, 6h, 24h, 7d, 30d)
            transport_modes: Comma-separated transport types to include
            bucket_width_minutes: Time bucket width for aggregation
            zoom_level: Map zoom level for density control
            max_points: Maximum number of data points to return

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

        # Get all stops from GTFS data
        try:
            gtfs_stops = await self._gtfs_schedule.get_all_stops(limit=5000)
            stops = [
                StopInfo(
                    stop_id=stop.stop_id,
                    stop_name=stop.stop_name,
                    stop_lat=float(stop.stop_lat) if stop.stop_lat else 0.0,
                    stop_lon=float(stop.stop_lon) if stop.stop_lon else 0.0,
                )
                for stop in gtfs_stops
                if stop.stop_lat and stop.stop_lon
            ]
        except Exception as exc:
            logger.error("Failed to fetch stop list: %s", exc)
            stops = []

        if not stops:
            return HeatmapResponse(
                time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
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

        # Set max points based on zoom level if not provided
        if max_points is None:
            if zoom_level < 10:
                max_points = 100
            elif zoom_level < 12:
                max_points = 500
            else:
                max_points = min(2000, MAX_DATA_POINTS)
        else:
            max_points = min(max_points, MAX_DATA_POINTS)

        # Try to get real aggregation data from database
        data_points = await self._aggregate_station_data_from_db(
            stops, transport_types, from_time, to_time
        )

        # If no data from DB, fall back to simulated data
        if not data_points:
            logger.info("No historical data available, using simulated data")
            data_points = self._aggregate_station_data_simulated(stops, transport_types)

        # Filter to stations with significant data (delays or cancellations)
        data_points = [
            dp
            for dp in data_points
            if dp.total_departures >= MIN_DEPARTURES
            and (
                dp.delay_rate >= 0.05
                or dp.cancellation_rate >= MIN_CANCELLATION_RATE
                or dp.total_departures >= 100
            )
        ]

        # Sort by impact (combined delay + cancellation rate, weighted by departures)
        data_points.sort(
            key=lambda x: (x.delay_rate + x.cancellation_rate) * x.total_departures,
            reverse=True,
        )
        data_points = data_points[:max_points]

        # Calculate summary
        summary = self._calculate_summary(data_points)

        return HeatmapResponse(
            time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
            data_points=data_points,
            summary=summary,
        )

    async def _aggregate_station_data_from_db(
        self,
        stops: list[StopInfo],
        transport_types: list[str] | None,
        from_time: datetime,
        to_time: datetime,
    ) -> list[HeatmapDataPoint]:
        """Query real cancellation data from station_aggregations table.

        Args:
            stops: List of stops with coordinates
            transport_types: Filter to specific transport types
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of HeatmapDataPoint with real statistics, or empty list if no data
        """
        if not self._session:
            return []

        # Build route_type filter if transport_types specified
        route_type_filter = None
        if transport_types:
            route_types_to_include = []
            for tt in transport_types:
                route_types_to_include.extend(TRANSPORT_TO_ROUTE_TYPES.get(tt, []))
            if route_types_to_include:
                route_type_filter = route_types_to_include

        try:
            # Query aggregated data for the time range from realtime_station_stats
            stmt = (
                select(
                    RealtimeStationStats.stop_id,
                    func.sum(RealtimeStationStats.trip_count).label("total_departures"),
                    func.sum(RealtimeStationStats.cancelled_count).label(
                        "cancelled_count"
                    ),
                    func.sum(RealtimeStationStats.delayed_count).label("delayed_count"),
                    RealtimeStationStats.route_type,
                )
                .where(RealtimeStationStats.bucket_start >= from_time)
                .where(RealtimeStationStats.bucket_start < to_time)
            )

            if route_type_filter:
                stmt = stmt.where(
                    RealtimeStationStats.route_type.in_(route_type_filter)
                )

            stmt = stmt.group_by(
                RealtimeStationStats.stop_id, RealtimeStationStats.route_type
            )

            result = await self._session.execute(stmt)
            rows = result.all()

            if not rows:
                return []

            # Build a map of stop_id -> stop info for lookup
            stop_map = {stop.stop_id: stop for stop in stops}

            # Aggregate by stop (combining route_types)
            stop_stats: dict[str, dict] = {}
            for row in rows:
                stop_id = row.stop_id
                if stop_id not in stop_map:
                    continue

                if stop_id not in stop_stats:
                    stop_info = stop_map[stop_id]
                    stop_stats[stop_id] = {
                        "stop_info": stop_info,
                        "total_departures": 0,
                        "cancelled_count": 0,
                        "delayed_count": 0,
                        "by_transport": {},
                    }

                stop_stats[stop_id]["total_departures"] += row.total_departures or 0
                stop_stats[stop_id]["cancelled_count"] += row.cancelled_count or 0
                stop_stats[stop_id]["delayed_count"] += row.delayed_count or 0

                # Track by transport type
                if row.route_type is not None:
                    transport_type = GTFS_ROUTE_TYPES.get(row.route_type, "BUS")
                    if transport_type not in stop_stats[stop_id]["by_transport"]:
                        stop_stats[stop_id]["by_transport"][transport_type] = {
                            "total": 0,
                            "cancelled": 0,
                            "delayed": 0,
                        }
                    stop_stats[stop_id]["by_transport"][transport_type]["total"] += (
                        row.total_departures or 0
                    )
                    stop_stats[stop_id]["by_transport"][transport_type][
                        "cancelled"
                    ] += row.cancelled_count or 0
                    stop_stats[stop_id]["by_transport"][transport_type]["delayed"] += (
                        row.delayed_count or 0
                    )

            # Convert to HeatmapDataPoint
            data_points = []
            for stop_id, stats in stop_stats.items():
                stop_info = stats["stop_info"]
                total = stats["total_departures"]
                cancelled = stats["cancelled_count"]
                delayed = stats["delayed_count"]
                cancellation_rate = cancelled / total if total > 0 else 0
                delay_rate = delayed / total if total > 0 else 0

                by_transport = {
                    tt: TransportStats(
                        total=ts["total"],
                        cancelled=ts["cancelled"],
                        delayed=ts["delayed"],
                    )
                    for tt, ts in stats["by_transport"].items()
                }

                data_points.append(
                    HeatmapDataPoint(
                        station_id=stop_id,
                        station_name=stop_info.stop_name,
                        latitude=stop_info.stop_lat,
                        longitude=stop_info.stop_lon,
                        total_departures=total,
                        cancelled_count=cancelled,
                        cancellation_rate=cancellation_rate,
                        delayed_count=delayed,
                        delay_rate=delay_rate,
                        by_transport=by_transport,
                    )
                )

            logger.info(
                "Retrieved %d stations with real aggregation data", len(data_points)
            )
            return data_points

        except Exception as exc:
            logger.warning("Failed to query aggregation data, falling back: %s", exc)
            return []

    def _aggregate_station_data_simulated(
        self,
        stops: list[StopInfo],
        transport_types: list[str] | None,
    ) -> list[HeatmapDataPoint]:
        """Generate simulated cancellation data for each station.

        Used as fallback when historical data is not yet available.

        Args:
            stops: List of stops to generate data for
            transport_types: Filter to specific transport types

        Returns:
            List of HeatmapDataPoint with simulated statistics
        """
        data_points: list[HeatmapDataPoint] = []

        # Default transport types if not specified
        all_transport_types = ["UBAHN", "SBAHN", "TRAM", "BUS", "BAHN"]
        active_types = transport_types or all_transport_types

        # Generate realistic-looking data based on station characteristics
        for stop in stops:
            # Use stop ID hash for reproducible "random" data
            # Using SHA256 instead of MD5 for security compliance
            stop_hash = int(hashlib.sha256(stop.stop_id.encode()).hexdigest()[:8], 16)

            # Generate realistic departure counts based on station importance
            # Central stations have more departures
            is_major_station = any(
                name in stop.stop_name.lower()
                for name in [
                    "hauptbahnhof",
                    "hbf",
                    "marienplatz",
                    "sendlinger",
                    "stachus",
                    "odeonsplatz",
                    "münchner freiheit",
                    "ostbahnhof",
                    "pasing",
                    "giesing",
                    "moosach",
                    "zentrum",
                    "bahnhof",
                ]
            )

            base_departures = 500 if is_major_station else 100
            total_departures = base_departures + (stop_hash % 200)

            # Calculate cancellation rate (typically 1-5%, higher for some stations)
            base_cancellation_rate = 0.02 + (stop_hash % 100) / 3000
            if stop_hash % 20 == 0:  # Some stations have higher issues
                base_cancellation_rate += 0.03

            cancelled_count = int(total_departures * min(base_cancellation_rate, 0.15))

            # Generate delay rate (typically 5-15%, higher than cancellations)
            base_delay_rate = 0.08 + (stop_hash % 100) / 2000
            if stop_hash % 15 == 0:  # Some stations have more delays
                base_delay_rate += 0.05

            delayed_count = int(total_departures * min(base_delay_rate, 0.25))

            # Generate transport breakdown
            by_transport: dict[str, TransportStats] = {}

            remaining_departures = total_departures
            remaining_cancellations = cancelled_count
            remaining_delays = delayed_count

            for i, tt in enumerate(active_types):
                if i == len(active_types) - 1:
                    # Last transport type gets remaining
                    tt_departures = remaining_departures
                    tt_cancellations = remaining_cancellations
                    tt_delays = remaining_delays
                else:
                    # Distribute based on hash
                    ratio = ((stop_hash >> (i * 4)) % 10 + 1) / 10
                    tt_departures = int(remaining_departures * ratio * 0.3)
                    tt_cancellations = int(remaining_cancellations * ratio * 0.3)
                    tt_delays = int(remaining_delays * ratio * 0.3)

                    remaining_departures -= tt_departures
                    remaining_cancellations -= tt_cancellations
                    remaining_delays -= tt_delays

                if tt_departures > 0:
                    by_transport[tt] = TransportStats(
                        total=tt_departures,
                        cancelled=max(0, tt_cancellations),
                        delayed=max(0, tt_delays),
                    )

            cancellation_rate = (
                cancelled_count / total_departures if total_departures > 0 else 0
            )
            delay_rate = delayed_count / total_departures if total_departures > 0 else 0

            data_points.append(
                HeatmapDataPoint(
                    station_id=stop.stop_id,
                    station_name=stop.stop_name,
                    latitude=stop.stop_lat,
                    longitude=stop.stop_lon,
                    total_departures=total_departures,
                    cancelled_count=cancelled_count,
                    cancellation_rate=cancellation_rate,
                    delayed_count=delayed_count,
                    delay_rate=delay_rate,
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
                total_delays=0,
                overall_delay_rate=0.0,
                most_affected_station=None,
                most_affected_line=None,
            )

        total_departures = sum(dp.total_departures for dp in data_points)
        total_cancellations = sum(dp.cancelled_count for dp in data_points)
        total_delays = sum(dp.delayed_count for dp in data_points)
        overall_cancellation_rate = (
            total_cancellations / total_departures if total_departures > 0 else 0
        )
        overall_delay_rate = (
            total_delays / total_departures if total_departures > 0 else 0
        )

        # Find most affected station (by combined delay+cancellation rate)
        affected_stations = [dp for dp in data_points if dp.total_departures >= 50]
        most_affected_station = None
        if affected_stations:
            most_affected = max(
                affected_stations,
                key=lambda x: x.delay_rate + x.cancellation_rate,
            )
            most_affected_station = most_affected.station_name

        # Find most affected line (aggregate by transport type)
        line_stats: dict[str, dict[str, int]] = {}
        for dp in data_points:
            for transport, stats in dp.by_transport.items():
                if transport not in line_stats:
                    line_stats[transport] = {"total": 0, "cancelled": 0, "delayed": 0}
                line_stats[transport]["total"] += stats.total
                line_stats[transport]["cancelled"] += stats.cancelled
                line_stats[transport]["delayed"] += stats.delayed

        most_affected_line = None
        highest_line_rate = 0.0
        for line, line_stat in line_stats.items():
            if line_stat["total"] >= 100:  # Minimum threshold
                combined_rate = (
                    line_stat["cancelled"] + line_stat["delayed"]
                ) / line_stat["total"]
                if combined_rate > highest_line_rate:
                    highest_line_rate = combined_rate
                    most_affected_line = TRANSPORT_TYPE_NAMES.get(line, line)

        return HeatmapSummary(
            total_stations=len(data_points),
            total_departures=total_departures,
            total_cancellations=total_cancellations,
            overall_cancellation_rate=overall_cancellation_rate,
            total_delays=total_delays,
            overall_delay_rate=overall_delay_rate,
            most_affected_station=most_affected_station,
            most_affected_line=most_affected_line,
        )


def get_heatmap_service(
    gtfs_schedule: GTFSScheduleService,
    cache: CacheService,
    session: AsyncSession | None = None,
) -> HeatmapService:
    """Factory function for HeatmapService.

    Args:
        gtfs_schedule: GTFS schedule service
        cache: Cache service
        session: Optional database session for aggregation queries

    Returns:
        Configured HeatmapService instance
    """
    return HeatmapService(gtfs_schedule, cache, session)
