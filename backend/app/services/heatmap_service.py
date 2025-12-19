"""
Heatmap service for cancellation data aggregation.

Aggregates departure cancellation data across stations for heatmap visualization.
Uses real GTFS-RT data from the realtime_station_stats table.
"""

from __future__ import annotations

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

        # Set max points based on zoom level if not provided
        if max_points is None:
            if zoom_level < 10:
                # At low zoom we still want enough points for stable clustering
                # and a representative national overview.
                max_points = 500
            elif zoom_level < 12:
                max_points = 1000
            else:
                max_points = min(2000, MAX_DATA_POINTS)
        else:
            max_points = min(max_points, MAX_DATA_POINTS)

        # Get real aggregation data from database (joins with gtfs_stops internally)
        data_points = await self._aggregate_station_data_from_db(
            transport_types, from_time, to_time
        )

        # Log when no real data is available
        if not data_points:
            logger.info("No historical data available for the requested time range")

        # Filter to stations with any data (at least 1 departure)
        original_count = len(data_points)
        data_points = [dp for dp in data_points if dp.total_departures >= 1]
        filtered_count = len(data_points)
        logger.debug(
            f"Filtered data points: {filtered_count}/{original_count} stations have departures"
        )

        # Sort by impact (combined delay + cancellation rate, weighted by departures)
        data_points.sort(
            key=lambda x: (x.delay_rate + x.cancellation_rate) * x.total_departures,
            reverse=True,
        )
        data_points = data_points[:max_points]
        logger.info(
            f"Returning {len(data_points)} data points after filtering and limiting"
        )

        # Calculate summary
        try:
            summary = self._calculate_summary(data_points)
        except Exception as e:
            logger.error(f"Failed to calculate summary: {str(e)}")
            # Provide a safe default summary
            summary = HeatmapSummary(
                total_stations=len(data_points),
                total_departures=sum(dp.total_departures for dp in data_points),
                total_cancellations=sum(dp.cancelled_count for dp in data_points),
                overall_cancellation_rate=0.0,
                total_delays=sum(dp.delayed_count for dp in data_points),
                overall_delay_rate=0.0,
                most_affected_station=None,
                most_affected_line=None,
            )

        return HeatmapResponse(
            time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
            data_points=data_points,
            summary=summary,
        )

    async def _aggregate_station_data_from_db(
        self,
        transport_types: list[str] | None,
        from_time: datetime,
        to_time: datetime,
    ) -> list[HeatmapDataPoint]:
        """Query real cancellation data by joining with GTFS stops.

        Args:
            transport_types: Filter to specific transport types
            from_time: Start of time range
            to_time: End of time range

        Returns:
            List of HeatmapDataPoint with real statistics, or empty list when no data exists
        """
        if not self._session:
            logger.error("No database session available for heatmap data aggregation")
            raise RuntimeError(
                "Heatmap aggregation requires an active database session"
            )

        # Build route_type filter if transport_types specified
        route_type_filter = None
        if transport_types:
            route_types_to_include = []
            for tt in transport_types:
                route_types_to_include.extend(TRANSPORT_TO_ROUTE_TYPES.get(tt, []))
            if route_types_to_include:
                route_type_filter = route_types_to_include

        try:
            from app.models.gtfs import GTFSStop

            # Query aggregated data with JOIN to gtfs_stops for coordinates/names
            stmt = (
                select(
                    RealtimeStationStats.stop_id,
                    GTFSStop.stop_name,
                    GTFSStop.stop_lat,
                    GTFSStop.stop_lon,
                    func.sum(RealtimeStationStats.trip_count).label("total_departures"),
                    func.sum(RealtimeStationStats.cancelled_count).label(
                        "cancelled_count"
                    ),
                    func.sum(RealtimeStationStats.delayed_count).label("delayed_count"),
                    RealtimeStationStats.route_type,
                )
                .join(
                    GTFSStop,
                    RealtimeStationStats.stop_id == GTFSStop.stop_id,
                )
                .where(RealtimeStationStats.bucket_start >= from_time)
                .where(RealtimeStationStats.bucket_start < to_time)
                .where(GTFSStop.stop_lat.isnot(None))
                .where(GTFSStop.stop_lon.isnot(None))
            )

            if route_type_filter:
                stmt = stmt.where(
                    RealtimeStationStats.route_type.in_(route_type_filter)
                )

            stmt = stmt.group_by(
                RealtimeStationStats.stop_id,
                GTFSStop.stop_name,
                GTFSStop.stop_lat,
                GTFSStop.stop_lon,
                RealtimeStationStats.route_type,
            )

            result = await self._session.execute(stmt)
            rows = result.all()

            if not rows:
                return []

            # Aggregate by stop (combining route_types)
            stop_stats: dict[str, dict] = {}
            for row in rows:
                stop_id = row.stop_id

                if stop_id not in stop_stats:
                    stop_stats[stop_id] = {
                        "stop_name": row.stop_name or stop_id,
                        "stop_lat": float(row.stop_lat),
                        "stop_lon": float(row.stop_lon),
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
                total = stats["total_departures"]
                cancelled = stats["cancelled_count"]
                delayed = stats["delayed_count"]
                # Clamp rates to [0, 1] to handle data quality issues
                # where delayed_count or cancelled_count may exceed trip_count
                cancellation_rate = min(cancelled / total, 1.0) if total > 0 else 0.0
                delay_rate = min(delayed / total, 1.0) if total > 0 else 0.0

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
                        station_name=stats["stop_name"],
                        latitude=stats["stop_lat"],
                        longitude=stats["stop_lon"],
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
            logger.error("Failed to query aggregation data: %s", exc)
            raise

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
            min(total_cancellations / total_departures, 1.0)
            if total_departures > 0
            else 0
        )
        overall_delay_rate = (
            min(total_delays / total_departures, 1.0) if total_departures > 0 else 0
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
