"""
Station statistics service for station-specific aggregation.

Provides station-level cancellation/delay statistics and trend data
by querying the realtime_station_stats table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache import CacheService

from app.models.heatmap import TimeRangePreset
from app.models.station_stats import (
    StationStats,
    StationTrends,
    TransportBreakdown,
    TrendDataPoint,
    TrendGranularity,
)
from app.persistence.models import RealtimeStationStats
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.heatmap_service import (
    GTFS_ROUTE_TYPES,
    TRANSPORT_TYPE_NAMES,
    parse_time_range,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class StationStatsService:
    """Service for station-specific statistics and trends.

    Aggregates data from the realtime_station_stats table for individual
    stations, providing cancellation rates, delay rates, and historical trends.
    """

    def __init__(
        self,
        session: AsyncSession,
        gtfs_schedule: GTFSScheduleService,
        cache: CacheService | None = None,
    ) -> None:
        """Initialize station stats service.

        Args:
            session: Database session for queries
            gtfs_schedule: GTFS schedule service for stop metadata
            cache: Optional cache service for caching results
        """
        self._session = session
        self._gtfs_schedule = gtfs_schedule
        self._cache = cache

    async def get_station_stats(
        self,
        stop_id: str,
        time_range: TimeRangePreset = "24h",
    ) -> StationStats | None:
        """Get current statistics for a station with caching.

        Args:
            stop_id: GTFS stop_id to query
            time_range: Time range preset

        Returns:
            StationStats with current metrics, or None if station not found
        """
        cache_key = f"station_stats:{stop_id}:{time_range}"

        # Try cache first
        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return StationStats(**cached)
            except Exception as e:
                logger.warning(f"Station stats cache read failed: {e}")

        from_time, to_time = parse_time_range(time_range)

        # Get station name from GTFS
        stop_info = await self._gtfs_schedule.get_stop_by_id(stop_id)
        if not stop_info:
            return None

        station_name = str(stop_info.stop_name or stop_id)

        # Query aggregated stats for this station
        stmt = (
            select(
                RealtimeStationStats.route_type,
                func.sum(RealtimeStationStats.trip_count).label("total_departures"),
                func.sum(RealtimeStationStats.cancelled_count).label("cancelled_count"),
                func.sum(RealtimeStationStats.delayed_count).label("delayed_count"),
            )
            .where(RealtimeStationStats.stop_id == stop_id)
            .where(RealtimeStationStats.bucket_start >= from_time)
            .where(RealtimeStationStats.bucket_start < to_time)
            .group_by(RealtimeStationStats.route_type)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        if not rows:
            # Return empty stats if no data
            stats = StationStats(
                station_id=stop_id,
                station_name=station_name,
                time_range=time_range,
                total_departures=0,
                cancelled_count=0,
                cancellation_rate=0.0,
                delayed_count=0,
                delay_rate=0.0,
                network_avg_cancellation_rate=None,
                network_avg_delay_rate=None,
                performance_score=None,
                by_transport=[],
                data_from=from_time,
                data_to=to_time,
            )
        else:
            # Aggregate totals and build transport breakdown
            total_departures = 0
            total_cancelled = 0
            total_delayed = 0
            by_transport: list[TransportBreakdown] = []

            for row in rows:
                deps = row.total_departures or 0
                cancelled = row.cancelled_count or 0
                delayed = row.delayed_count or 0

                total_departures += deps
                total_cancelled += cancelled
                total_delayed += delayed

                # Get transport type name
                transport_type = GTFS_ROUTE_TYPES.get(row.route_type, "BUS")
                display_name = TRANSPORT_TYPE_NAMES.get(transport_type, transport_type)

                by_transport.append(
                    TransportBreakdown(
                        transport_type=transport_type,
                        display_name=display_name,
                        total_departures=deps,
                        cancelled_count=cancelled,
                        cancellation_rate=min(cancelled / deps, 1.0) if deps > 0 else 0,
                        delayed_count=delayed,
                        delay_rate=min(delayed / deps, 1.0) if deps > 0 else 0,
                    )
                )

            # Sort transport breakdown by departures
            by_transport.sort(key=lambda x: x.total_departures, reverse=True)

            # Calculate overall rates
            overall_cancellation_rate = (
                min(total_cancelled / total_departures, 1.0)
                if total_departures > 0
                else 0
            )
            overall_delay_rate = (
                min(total_delayed / total_departures, 1.0)
                if total_departures > 0
                else 0
            )

            # Get network averages for comparison
            network_avg = await self._get_network_averages(from_time, to_time)

            # Calculate performance score (100 = perfect)
            # Score decreases with higher cancellation/delay rates
            # Weight: cancellations are more impactful than delays
            performance_score = max(
                0,
                100 - (overall_cancellation_rate * 400) - (overall_delay_rate * 100),
            )

            stats = StationStats(
                station_id=stop_id,
                station_name=station_name,
                time_range=time_range,
                total_departures=total_departures,
                cancelled_count=total_cancelled,
                cancellation_rate=overall_cancellation_rate,
                delayed_count=total_delayed,
                delay_rate=overall_delay_rate,
                network_avg_cancellation_rate=network_avg.get("cancellation_rate"),
                network_avg_delay_rate=network_avg.get("delay_rate"),
                performance_score=performance_score,
                by_transport=by_transport,
                data_from=from_time,
                data_to=to_time,
            )

        # Cache the result
        if self._cache and stats:
            try:
                await self._cache.set_json(
                    cache_key,
                    stats.model_dump(),
                    ttl_seconds=300,  # 5 minutes
                    stale_ttl_seconds=900,  # 15 minute stale fallback
                )
            except Exception as e:
                logger.warning(f"Station stats cache write failed: {e}")

        return stats

    async def get_station_trends(
        self,
        stop_id: str,
        time_range: TimeRangePreset = "24h",
        granularity: TrendGranularity = "hourly",
    ) -> StationTrends | None:
        """Get historical trend data for a station with caching.

        Args:
            stop_id: GTFS stop_id to query
            time_range: Time range preset
            granularity: Data granularity (hourly or daily)

        Returns:
            StationTrends with time series data, or None if station not found
        """
        cache_key = f"station_trends:{stop_id}:{time_range}:{granularity}"

        # Try cache first
        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return StationTrends(**cached)
            except Exception as e:
                logger.warning(f"Station trends cache read failed: {e}")

        from_time, to_time = parse_time_range(time_range)

        # Get station name from GTFS
        stop_info = await self._gtfs_schedule.get_stop_by_id(stop_id)
        if not stop_info:
            return None

        station_name = str(stop_info.stop_name or stop_id)

        # Determine bucket grouping based on granularity
        if granularity == "hourly":
            # Group by hour
            time_bucket = func.date_trunc("hour", RealtimeStationStats.bucket_start)
        else:
            # Group by day
            time_bucket = func.date_trunc("day", RealtimeStationStats.bucket_start)

        stmt = (
            select(
                time_bucket.label("bucket"),
                func.sum(RealtimeStationStats.trip_count).label("total_departures"),
                func.sum(RealtimeStationStats.cancelled_count).label("cancelled_count"),
                func.sum(RealtimeStationStats.delayed_count).label("delayed_count"),
            )
            .where(RealtimeStationStats.stop_id == stop_id)
            .where(RealtimeStationStats.bucket_start >= from_time)
            .where(RealtimeStationStats.bucket_start < to_time)
            .group_by(time_bucket)
            .order_by(time_bucket)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        data_points: list[TrendDataPoint] = []
        total_cancellation_rate = 0.0
        total_delay_rate = 0.0
        peak_cancellation_rate = 0.0
        peak_delay_rate = 0.0

        for row in rows:
            deps = row.total_departures or 0
            cancelled = row.cancelled_count or 0
            delayed = row.delayed_count or 0

            cancel_rate = min(cancelled / deps, 1.0) if deps > 0 else 0
            delay_rate = min(delayed / deps, 1.0) if deps > 0 else 0

            total_cancellation_rate += cancel_rate
            total_delay_rate += delay_rate
            peak_cancellation_rate = max(peak_cancellation_rate, cancel_rate)
            peak_delay_rate = max(peak_delay_rate, delay_rate)

            data_points.append(
                TrendDataPoint(
                    timestamp=row.bucket,
                    total_departures=deps,
                    cancelled_count=cancelled,
                    cancellation_rate=cancel_rate,
                    delayed_count=delayed,
                    delay_rate=delay_rate,
                )
            )

        # Calculate averages
        n_points = len(data_points)
        avg_cancellation_rate = (
            total_cancellation_rate / n_points if n_points > 0 else 0
        )
        avg_delay_rate = total_delay_rate / n_points if n_points > 0 else 0

        trends = StationTrends(
            station_id=stop_id,
            station_name=station_name,
            time_range=time_range,
            granularity=granularity,
            data_points=data_points,
            avg_cancellation_rate=avg_cancellation_rate,
            avg_delay_rate=avg_delay_rate,
            peak_cancellation_rate=peak_cancellation_rate,
            peak_delay_rate=peak_delay_rate,
            data_from=from_time,
            data_to=to_time,
        )

        # Cache the result
        if self._cache and trends:
            try:
                await self._cache.set_json(
                    cache_key,
                    trends.model_dump(),
                    ttl_seconds=300,
                    stale_ttl_seconds=900,
                )
            except Exception as e:
                logger.warning(f"Station trends cache write failed: {e}")

        return trends

    async def _get_network_averages(
        self,
        from_time: datetime,
        to_time: datetime,
    ) -> dict[str, float]:
        """Get network-wide average cancellation and delay rates with caching.

        Args:
            from_time: Start of time range
            to_time: End of time range

        Returns:
            Dict with 'cancellation_rate' and 'delay_rate' keys
        """
        # Use hour-bucketed cache key for network averages
        from_bucket = from_time.strftime("%Y%m%d%H")
        to_bucket = to_time.strftime("%Y%m%d%H")
        cache_key = f"network_averages:{from_bucket}:{to_bucket}"

        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return cached
            except Exception as e:
                logger.warning(f"Network averages cache read failed: {e}")

        stmt = select(
            func.sum(RealtimeStationStats.trip_count).label("total"),
            func.sum(RealtimeStationStats.cancelled_count).label("cancelled"),
            func.sum(RealtimeStationStats.delayed_count).label("delayed"),
        ).where(
            RealtimeStationStats.bucket_start >= from_time,
            RealtimeStationStats.bucket_start < to_time,
        )

        result = await self._session.execute(stmt)
        row = result.one_or_none()

        if not row or not row.total:
            res = {"cancellation_rate": 0.0, "delay_rate": 0.0}
        else:
            res = {
                "cancellation_rate": min((row.cancelled or 0) / row.total, 1.0),
                "delay_rate": min((row.delayed or 0) / row.total, 1.0),
            }

        # Cache for 10 minutes (network averages change slowly)
        if self._cache:
            try:
                await self._cache.set_json(cache_key, res, ttl_seconds=600)
            except Exception as e:
                logger.warning(f"Network averages cache write failed: {e}")

        return res
