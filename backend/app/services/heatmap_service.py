"""
Heatmap service for cancellation data aggregation.

Aggregates departure cancellation data across stations for heatmap visualization.
Uses real GTFS-RT data from the realtime_station_stats table.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select, Numeric
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapOverviewResponse,  # NEW
    HeatmapPointLight,  # NEW
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
_SLOW_HEATMAP_DB_QUERY_LOG_MS = 1000

# Time range preset mappings (in hours)
TIME_RANGE_HOURS: dict[str, int] = {
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

# Spatial stratification for heatmap coverage
# Grid cell size in degrees (~0.1° ≈ 10km at Germany's latitude)
GRID_CELL_SIZE = 0.1

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


def resolve_max_points(zoom_level: int, max_points: int | None) -> int:
    """Resolve the effective max_points for a request.

    We intentionally bucket zoom levels into a small set of densities so caching
    and warmup can cover most requests with a small number of keys.
    """
    if max_points is None:
        if zoom_level < 10:
            effective = 500
        elif zoom_level < 12:
            effective = 1000
        else:
            effective = 2000
    else:
        effective = max_points

    return min(int(effective), MAX_DATA_POINTS)


def calculate_heatmap_summary(
    data_points: list[HeatmapDataPoint],
) -> HeatmapSummary:
    """Calculate summary statistics from data points."""
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
        min(total_cancellations / total_departures, 1.0) if total_departures > 0 else 0
    )
    overall_delay_rate = (
        min(total_delays / total_departures, 1.0) if total_departures > 0 else 0
    )

    affected_stations = [dp for dp in data_points if dp.total_departures >= 50]
    most_affected_station = None
    if affected_stations:
        most_affected = max(
            affected_stations,
            key=lambda x: x.delay_rate + x.cancellation_rate,
        )
        most_affected_station = most_affected.station_name

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
        if line_stat["total"] >= 100:
            combined_rate = (line_stat["cancelled"] + line_stat["delayed"]) / line_stat[
                "total"
            ]
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

        max_points_effective = resolve_max_points(zoom_level, max_points)

        route_type_filter = self._resolve_route_type_filter(transport_types)

        # Get real aggregation data from database (joins with gtfs_stops internally)
        data_points = await self._aggregate_station_data_from_db(
            route_type_filter,
            from_time,
            to_time,
            bucket_width_minutes=bucket_width_minutes,
            max_points=max_points_effective,
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

        # Defensive: sort + cap again (DB already limits, but keep semantics stable)
        data_points.sort(
            key=lambda x: (x.delay_rate + x.cancellation_rate) * x.total_departures,
            reverse=True,
        )
        data_points = data_points[:max_points_effective]
        logger.info(
            f"Returning {len(data_points)} data points after filtering and limiting"
        )

        summary = await self._calculate_network_summary_from_db(
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=bucket_width_minutes,
            route_type_filter=route_type_filter,
            most_affected_station=_pick_most_affected_station(data_points),
        )

        return HeatmapResponse(
            time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
            data_points=data_points,
            summary=summary,
        )

    async def get_heatmap_overview(
        self,
        time_range: TimeRangePreset | None = None,
        transport_modes: str | None = None,
        bucket_width_minutes: int = DEFAULT_BUCKET_WIDTH_MINUTES,
    ) -> HeatmapOverviewResponse:
        """Generate lightweight heatmap overview showing ALL impacted stations.

        Unlike get_cancellation_heatmap(), this method:
        - Returns ALL stations with non-zero impact (no max_points limit)
        - Uses minimal fields (id, lat, lon, intensity, name)
        - Skips the by_transport breakdown (fetched on-demand via /stats endpoint)

        Args:
            time_range: Time range preset (live, 1h, 6h, 24h, 7d, 30d)
            transport_modes: Comma-separated transport types to include
            bucket_width_minutes: Time bucket width for aggregation

        Returns:
            HeatmapOverviewResponse with lightweight points for all impacted stations
        """
        from_time, to_time = parse_time_range(time_range)
        transport_types = parse_transport_modes(transport_modes)
        route_type_filter = self._resolve_route_type_filter(transport_types)

        logger.info(
            "Generating heatmap overview for time range %s to %s, transport modes: %s",
            from_time.isoformat(),
            to_time.isoformat(),
            transport_modes or "all",
        )

        points = await self._get_all_impacted_stations_light(
            route_type_filter=route_type_filter,
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=bucket_width_minutes,
        )

        summary = await self._calculate_network_summary_from_db(
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=bucket_width_minutes,
            route_type_filter=route_type_filter,
            most_affected_station=_pick_most_affected_station_light(points),
        )

        return HeatmapOverviewResponse(
            time_range=TimeRange.model_validate({"from": from_time, "to": to_time}),
            points=points,
            summary=summary,
            total_impacted_stations=len(points),
        )

    async def _aggregate_station_data_from_db(
        self,
        route_type_filter: list[int] | None,
        from_time: datetime,
        to_time: datetime,
        *,
        bucket_width_minutes: int,
        max_points: int,
    ) -> list[HeatmapDataPoint]:
        """Query real cancellation data with spatially stratified sampling.

        Uses a two-tiered selection strategy:
        1. Tier 1 (Coverage): One primary representative per grid cell (most impacted)
        2. Tier 2 (Density): Remaining slots filled by highest-impact stations globally

        This ensures consistent network coverage even during stable operations.

        Args:
            transport_types: Filter to specific transport types
            from_time: Start of time range
            to_time: End of time range
            max_points: Maximum number of stations to return

        Returns:
            List of HeatmapDataPoint with real statistics, or empty list when no data exists
        """
        if not self._session:
            logger.error("No database session available for heatmap data aggregation")
            raise RuntimeError(
                "Heatmap aggregation requires an active database session"
            )

        try:
            from app.models.gtfs import GTFSStop

            total_departures_expr = func.coalesce(
                func.sum(RealtimeStationStats.trip_count), 0
            )
            cancelled_count_expr = func.coalesce(
                func.sum(RealtimeStationStats.cancelled_count), 0
            )
            delayed_count_expr = func.coalesce(
                func.sum(RealtimeStationStats.delayed_count), 0
            )
            impact_score_expr = func.least(
                cancelled_count_expr, total_departures_expr
            ) + func.least(delayed_count_expr, total_departures_expr)

            # Virtual grid cell coordinates for spatial stratification
            grid_x_expr = func.floor(GTFSStop.stop_lon / GRID_CELL_SIZE).label("grid_x")
            grid_y_expr = func.floor(GTFSStop.stop_lat / GRID_CELL_SIZE).label("grid_y")

            # CTE: Base aggregation with grid coordinates
            # This creates a materialized result set with all stations and their metrics

            base_aggregation = (
                select(
                    RealtimeStationStats.stop_id,
                    GTFSStop.stop_name,
                    GTFSStop.stop_lat,
                    GTFSStop.stop_lon,
                    grid_x_expr,
                    grid_y_expr,
                    total_departures_expr.label("total_departures"),
                    cancelled_count_expr.label("cancelled_count"),
                    delayed_count_expr.label("delayed_count"),
                    impact_score_expr.label("impact_score"),
                )
                .join(
                    GTFSStop,
                    RealtimeStationStats.stop_id == GTFSStop.stop_id,
                )
                .where(RealtimeStationStats.bucket_start >= from_time)
                .where(RealtimeStationStats.bucket_start < to_time)
                .where(
                    RealtimeStationStats.bucket_width_minutes == bucket_width_minutes
                )
                .where(GTFSStop.stop_lat.isnot(None))
                .where(GTFSStop.stop_lon.isnot(None))
            )

            if route_type_filter:
                base_aggregation = base_aggregation.where(
                    RealtimeStationStats.route_type.in_(route_type_filter)
                )

            base_aggregation = base_aggregation.group_by(
                RealtimeStationStats.stop_id,
                GTFSStop.stop_name,
                GTFSStop.stop_lat,
                GTFSStop.stop_lon,
                grid_x_expr,
                grid_y_expr,
            ).having(total_departures_expr >= 1)

            # Wrap as CTE
            base_cte = base_aggregation.cte("station_metrics")

            # Tier 1: Primary representative for each grid cell (most impacted)
            # Use PostgreSQL's DISTINCT ON to get one row per (grid_x, grid_y) ordered by impact
            tier1_stmt = (
                select(
                    base_cte.c.stop_id,
                    base_cte.c.stop_name,
                    base_cte.c.stop_lat,
                    base_cte.c.stop_lon,
                    base_cte.c.total_departures,
                    base_cte.c.cancelled_count,
                    base_cte.c.delayed_count,
                    base_cte.c.impact_score,
                )
                .select_from(base_cte)
                .distinct(base_cte.c.grid_x, base_cte.c.grid_y)
                .order_by(
                    base_cte.c.grid_x,
                    base_cte.c.grid_y,
                    base_cte.c.impact_score.desc(),
                    base_cte.c.total_departures.desc(),
                )
            )

            # Tier 2: Top N globally (we'll take max_points total, so tier 2 fills remaining slots)
            tier2_stmt = (
                select(
                    base_cte.c.stop_id,
                    base_cte.c.stop_name,
                    base_cte.c.stop_lat,
                    base_cte.c.stop_lon,
                    base_cte.c.total_departures,
                    base_cte.c.cancelled_count,
                    base_cte.c.delayed_count,
                    base_cte.c.impact_score,
                )
                .select_from(base_cte)
                .order_by(
                    base_cte.c.impact_score.desc(), base_cte.c.total_departures.desc()
                )
                .limit(max_points)
            )

            # Combine Tier 1 and Tier 2 using UNION, then limit to max_points
            # UNION automatically deduplicates, so stations in both appear only once
            stations_stmt = (
                tier1_stmt.union(tier2_stmt)
                .order_by(
                    func.literal_column("impact_score").desc(),
                    func.literal_column("total_departures").desc(),
                )
                .limit(max_points)
            )

            stations_started = time.monotonic()
            stations_result = await self._session.execute(stations_stmt)
            stations_ms = (time.monotonic() - stations_started) * 1000
            station_rows = stations_result.all()
            if not station_rows:
                return []
            if stations_ms >= _SLOW_HEATMAP_DB_QUERY_LOG_MS:
                logger.info(
                    "Slow heatmap stations query (%dms): rows=%d max_points=%d",
                    int(stations_ms),
                    len(station_rows),
                    max_points,
                )

            station_ids = [row.stop_id for row in station_rows]

            # Second: fetch per-route_type breakdown only for the selected stations.
            breakdown_stmt = (
                select(
                    RealtimeStationStats.stop_id,
                    RealtimeStationStats.route_type,
                    func.coalesce(func.sum(RealtimeStationStats.trip_count), 0).label(
                        "total_departures"
                    ),
                    func.coalesce(
                        func.sum(RealtimeStationStats.cancelled_count), 0
                    ).label("cancelled_count"),
                    func.coalesce(
                        func.sum(RealtimeStationStats.delayed_count), 0
                    ).label("delayed_count"),
                )
                .where(RealtimeStationStats.bucket_start >= from_time)
                .where(RealtimeStationStats.bucket_start < to_time)
                .where(
                    RealtimeStationStats.bucket_width_minutes == bucket_width_minutes
                )
                .where(RealtimeStationStats.stop_id.in_(station_ids))
            )

            if route_type_filter:
                breakdown_stmt = breakdown_stmt.where(
                    RealtimeStationStats.route_type.in_(route_type_filter)
                )

            breakdown_stmt = breakdown_stmt.group_by(
                RealtimeStationStats.stop_id,
                RealtimeStationStats.route_type,
            )

            breakdown_started = time.monotonic()
            breakdown_result = await self._session.execute(breakdown_stmt)
            breakdown_ms = (time.monotonic() - breakdown_started) * 1000
            breakdown_rows = breakdown_result.all()
            if breakdown_ms >= _SLOW_HEATMAP_DB_QUERY_LOG_MS:
                logger.info(
                    "Slow heatmap breakdown query (%dms): stations=%d",
                    int(breakdown_ms),
                    len(station_ids),
                )

            breakdown_by_station: dict[str, dict[str, TransportStats]] = {}
            for row in breakdown_rows:
                stop_id = row.stop_id
                route_type = row.route_type
                if route_type is None:
                    continue

                transport_type = GTFS_ROUTE_TYPES.get(route_type, "BUS")
                per_station = breakdown_by_station.setdefault(stop_id, {})
                existing = per_station.get(transport_type)
                if existing is None:
                    per_station[transport_type] = TransportStats(
                        total=int(row.total_departures or 0),
                        cancelled=int(row.cancelled_count or 0),
                        delayed=int(row.delayed_count or 0),
                    )
                else:
                    per_station[transport_type] = TransportStats(
                        total=existing.total + int(row.total_departures or 0),
                        cancelled=existing.cancelled + int(row.cancelled_count or 0),
                        delayed=existing.delayed + int(row.delayed_count or 0),
                    )

            # Convert to HeatmapDataPoint
            data_points = []
            for row in station_rows:
                stop_id = row.stop_id
                total = int(row.total_departures or 0)
                cancelled = int(row.cancelled_count or 0)
                delayed = int(row.delayed_count or 0)

                # Station-level rates for popup display.
                cancellation_rate = min(cancelled / total, 1.0) if total > 0 else 0.0
                delay_rate = min(delayed / total, 1.0) if total > 0 else 0.0

                data_points.append(
                    HeatmapDataPoint(
                        station_id=stop_id,
                        station_name=(row.stop_name or stop_id),
                        latitude=float(row.stop_lat),
                        longitude=float(row.stop_lon),
                        total_departures=total,
                        cancelled_count=cancelled,
                        cancellation_rate=cancellation_rate,
                        delayed_count=delayed,
                        delay_rate=delay_rate,
                        by_transport=breakdown_by_station.get(stop_id, {}),
                    )
                )

            logger.info(
                "Retrieved %d stations with real aggregation data (limited to %d)",
                len(data_points),
                max_points,
            )
            return data_points

        except Exception as exc:
            logger.error("Failed to query aggregation data: %s", exc)
            raise

    async def _get_all_impacted_stations_light(
        self,
        route_type_filter: list[int] | None,
        from_time: datetime,
        to_time: datetime,
        *,
        bucket_width_minutes: int,
    ) -> list[HeatmapPointLight]:
        """Query ALL impacted stations with minimal fields.

        Returns only stations where:
        - cancelled_count > 0 OR delayed_count > 0
        - Has valid coordinates

        No limit on number of stations returned.
        """
        if not self._session:
            raise RuntimeError("Heatmap overview requires an active database session")

        from app.models.gtfs import GTFSStop
        from app.models.heatmap import HeatmapPointLight

        total_departures_expr = func.coalesce(
            func.sum(RealtimeStationStats.trip_count), 0
        )
        cancelled_count_expr = func.coalesce(
            func.sum(RealtimeStationStats.cancelled_count), 0
        )
        delayed_count_expr = func.coalesce(
            func.sum(RealtimeStationStats.delayed_count), 0
        )

        # Intensity = (cancelled + delayed) / total, saturated at 25%
        # This gives a 0-1 value for heatmap weight
        intensity_expr = func.least(
            (cancelled_count_expr + delayed_count_expr)
            / func.nullif(total_departures_expr, 0)
            * 4.0,
            1.0,
        ).label("intensity")

        stmt = (
            select(
                RealtimeStationStats.stop_id,
                GTFSStop.stop_name,
                func.round(GTFSStop.stop_lat.cast(Numeric), 4).label("lat"),
                func.round(GTFSStop.stop_lon.cast(Numeric), 4).label("lon"),
                intensity_expr,
                cancelled_count_expr.label("cancelled"),
                delayed_count_expr.label("delayed"),
            )
            .join(GTFSStop, RealtimeStationStats.stop_id == GTFSStop.stop_id)
            .where(RealtimeStationStats.bucket_start >= from_time)
            .where(RealtimeStationStats.bucket_start < to_time)
            .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
            .where(GTFSStop.stop_lat.isnot(None))
            .where(GTFSStop.stop_lon.isnot(None))
        )

        if route_type_filter:
            stmt = stmt.where(RealtimeStationStats.route_type.in_(route_type_filter))

        stmt = stmt.group_by(
            RealtimeStationStats.stop_id,
            GTFSStop.stop_name,
            GTFSStop.stop_lat,
            GTFSStop.stop_lon,
        ).having(
            # Only include stations with at least 1 cancellation OR delay
            (cancelled_count_expr > 0) | (delayed_count_expr > 0)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        points = [
            HeatmapPointLight(
                id=row.stop_id,
                n=row.stop_name or row.stop_id,
                lat=float(row.lat),
                lon=float(row.lon),
                i=float(row.intensity) if row.intensity else 0.0,
            )
            for row in rows
        ]

        logger.info("Retrieved %d impacted stations for heatmap overview", len(points))
        return points

    def _resolve_route_type_filter(
        self, transport_types: list[str] | None
    ) -> list[int] | None:
        if not transport_types:
            return None

        route_types_to_include: list[int] = []
        for transport_type in transport_types:
            route_types_to_include.extend(
                TRANSPORT_TO_ROUTE_TYPES.get(transport_type, [])
            )

        return route_types_to_include or None

    async def _calculate_network_summary_from_db(
        self,
        *,
        from_time: datetime,
        to_time: datetime,
        bucket_width_minutes: int,
        route_type_filter: list[int] | None,
        most_affected_station: str | None,
    ) -> HeatmapSummary:
        if not self._session:
            raise RuntimeError(
                "Network summary calculation requires an active database session"
            )

        total_departures_expr = func.coalesce(
            func.sum(RealtimeStationStats.trip_count), 0
        )
        total_cancellations_expr = func.coalesce(
            func.sum(RealtimeStationStats.cancelled_count), 0
        )
        total_delays_expr = func.coalesce(
            func.sum(RealtimeStationStats.delayed_count), 0
        )
        stations_expr = func.count(func.distinct(RealtimeStationStats.stop_id))

        stmt = (
            select(
                stations_expr.label("total_stations"),
                total_departures_expr.label("total_departures"),
                total_cancellations_expr.label("total_cancellations"),
                total_delays_expr.label("total_delays"),
            )
            .where(RealtimeStationStats.bucket_start >= from_time)
            .where(RealtimeStationStats.bucket_start < to_time)
            .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
        )
        if route_type_filter:
            stmt = stmt.where(RealtimeStationStats.route_type.in_(route_type_filter))

        result = await self._session.execute(stmt)
        rows = result.all()
        row = rows[0] if rows else None
        if not row:
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

        total_stations = int(row.total_stations or 0)
        total_departures = int(row.total_departures or 0)
        total_cancellations = int(row.total_cancellations or 0)
        total_delays = int(row.total_delays or 0)
        overall_cancellation_rate = (
            min(total_cancellations / total_departures, 1.0)
            if total_departures > 0
            else 0.0
        )
        overall_delay_rate = (
            min(total_delays / total_departures, 1.0) if total_departures > 0 else 0.0
        )

        most_affected_line = await self._get_most_affected_line_from_db(
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=bucket_width_minutes,
            route_type_filter=route_type_filter,
        )

        return HeatmapSummary(
            total_stations=total_stations,
            total_departures=total_departures,
            total_cancellations=total_cancellations,
            overall_cancellation_rate=overall_cancellation_rate,
            total_delays=total_delays,
            overall_delay_rate=overall_delay_rate,
            most_affected_station=most_affected_station,
            most_affected_line=most_affected_line,
        )

    async def _get_most_affected_line_from_db(
        self,
        *,
        from_time: datetime,
        to_time: datetime,
        bucket_width_minutes: int,
        route_type_filter: list[int] | None,
    ) -> str | None:
        if not self._session:
            raise RuntimeError(
                "Most affected line calculation requires an active database session"
            )

        stmt = (
            select(
                RealtimeStationStats.route_type.label("route_type"),
                func.coalesce(func.sum(RealtimeStationStats.trip_count), 0).label(
                    "total_departures"
                ),
                func.coalesce(func.sum(RealtimeStationStats.cancelled_count), 0).label(
                    "cancelled_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.delayed_count), 0).label(
                    "delayed_count"
                ),
            )
            .where(RealtimeStationStats.bucket_start >= from_time)
            .where(RealtimeStationStats.bucket_start < to_time)
            .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
            .group_by(RealtimeStationStats.route_type)
        )
        if route_type_filter:
            stmt = stmt.where(RealtimeStationStats.route_type.in_(route_type_filter))

        result = await self._session.execute(stmt)
        rows = result.all()

        line_stats: dict[str, dict[str, int]] = {}
        for row in rows:
            route_type = row.route_type
            if route_type is None:
                continue
            transport_type = GTFS_ROUTE_TYPES.get(route_type, "BUS")
            entry = line_stats.setdefault(
                transport_type, {"total": 0, "cancelled": 0, "delayed": 0}
            )
            entry["total"] += int(row.total_departures or 0)
            entry["cancelled"] += int(row.cancelled_count or 0)
            entry["delayed"] += int(row.delayed_count or 0)

        most_affected_line = None
        highest_line_rate = 0.0
        for line, line_stat in line_stats.items():
            total = line_stat["total"]
            if total < 100:
                continue
            combined_rate = (line_stat["cancelled"] + line_stat["delayed"]) / total
            if combined_rate > highest_line_rate:
                highest_line_rate = combined_rate
                most_affected_line = TRANSPORT_TYPE_NAMES.get(line, line)

        return most_affected_line

    def _calculate_summary(
        self,
        data_points: list[HeatmapDataPoint],
    ) -> HeatmapSummary:
        """Calculate summary statistics from data points."""
        return calculate_heatmap_summary(data_points)


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


def _pick_most_affected_station(data_points: list[HeatmapDataPoint]) -> str | None:
    affected_stations = [dp for dp in data_points if dp.total_departures >= 50]
    if not affected_stations:
        return None
    most_affected = max(
        affected_stations,
        key=lambda x: x.delay_rate + x.cancellation_rate,
    )
    return most_affected.station_name


def _pick_most_affected_station_light(points: list[HeatmapPointLight]) -> str | None:
    """Pick the most affected station from lightweight points."""
    if not points:
        return None
    most_affected = max(points, key=lambda p: p.i)
    return most_affected.n
