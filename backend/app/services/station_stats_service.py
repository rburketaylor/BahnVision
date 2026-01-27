"""
Station statistics service for station-specific aggregation.

Provides station-level cancellation/delay statistics and trend data
by querying the realtime_station_stats table.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache import CacheService

from app.models.heatmap import HeatmapOverviewResponse, TimeRangePreset
from app.models.station_stats import (
    StationStats,
    StationTrends,
    TransportBreakdown,
    TrendDataPoint,
    TrendGranularity,
)
from app.persistence.models import RealtimeStationStats
from app.persistence.models import RealtimeStationStatsDaily
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

    async def _get_station_name(self, stop_id: str) -> str | None:
        """Get station name with caching.

        Station names are static and can be cached for long durations.
        """
        cache_key = f"station_name:{stop_id}"

        if self._cache:
            try:
                name = await self._cache.get(cache_key)
                if name:
                    return name
            except Exception as e:
                logger.warning(f"Station name cache read failed: {e}")

        stop_info = await self._gtfs_schedule.get_stop_by_id(stop_id)
        if not stop_info:
            return None

        name = str(stop_info.stop_name or stop_id)

        if self._cache:
            try:
                await self._cache.set(cache_key, name, ttl_seconds=86400)  # 24 hours
            except Exception as e:
                logger.warning(f"Station name cache write failed: {e}")

        return name

    async def get_station_stats(
        self,
        stop_id: str,
        time_range: TimeRangePreset = "24h",
        bucket_width_minutes: int = 60,
        *,
        include_network_averages: bool = True,
    ) -> StationStats | None:
        """Get current statistics for a station with caching.

        Args:
            stop_id: GTFS stop_id to query
            time_range: Time range preset
            bucket_width_minutes: Time bucket width for aggregation

        Returns:
            StationStats with current metrics, or None if station not found
        """
        cache_key = (
            f"station_stats:{stop_id}:{time_range}:{bucket_width_minutes}:"
            f"{1 if include_network_averages else 0}"
        )

        # Try cache first
        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return StationStats(**cached)
            except Exception as e:
                logger.warning(f"Station stats cache read failed: {e}")

        from_time, to_time = parse_time_range(time_range)

        # Get station name (cached)
        station_name = await self._get_station_name(stop_id)
        if not station_name:
            return None

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
            .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
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

            network_avg: dict[str, float] = {}
            if include_network_averages:
                # Get network averages for comparison
                network_avg = await self._get_network_averages(
                    time_range=time_range,
                    from_time=from_time,
                    to_time=to_time,
                    bucket_width_minutes=bucket_width_minutes,
                )

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
                network_avg_cancellation_rate=(
                    network_avg.get("cancellation_rate")
                    if include_network_averages
                    else None
                ),
                network_avg_delay_rate=(
                    network_avg.get("delay_rate") if include_network_averages else None
                ),
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
        bucket_width_minutes: int = 60,
    ) -> StationTrends | None:
        """Get historical trend data for a station with caching.

        Args:
            stop_id: GTFS stop_id to query
            time_range: Time range preset
            granularity: Data granularity (hourly or daily)
            bucket_width_minutes: Time bucket width for aggregation

        Returns:
            StationTrends with time series data, or None if station not found
        """
        cache_key = f"station_trends:{stop_id}:{time_range}:{granularity}:{bucket_width_minutes}"

        # Try cache first
        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return StationTrends(**cached)
            except Exception as e:
                logger.warning(f"Station trends cache read failed: {e}")

        from_time, to_time = parse_time_range(time_range)

        # Get station name (cached)
        station_name = await self._get_station_name(stop_id)
        if not station_name:
            return None

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
            .where(RealtimeStationStats.bucket_width_minutes == bucket_width_minutes)
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
        time_range: TimeRangePreset,
        from_time: datetime,
        to_time: datetime,
        bucket_width_minutes: int,
    ) -> dict[str, float]:
        """Get network-wide average cancellation and delay rates with caching.

        Args:
            time_range: Time range preset (used for fast path via heatmap overview cache)
            from_time: Start of time range
            to_time: End of time range
            bucket_width_minutes: Bucket width to match aggregation

        Returns:
            Dict with 'cancellation_rate' and 'delay_rate' keys
        """
        # Use hour-bucketed cache key for network averages
        from_bucket = from_time.strftime("%Y%m%d%H")
        to_bucket = to_time.strftime("%Y%m%d%H")
        cache_key = f"network_averages:{bucket_width_minutes}:{from_bucket}:{to_bucket}"

        if self._cache:
            try:
                cached = await self._cache.get_json(cache_key)
                if cached:
                    return cached
            except Exception as e:
                logger.warning(f"Network averages cache read failed: {e}")

        # Fast path: reuse cached heatmap overview summary if available.
        # The heatmap landing page always hits /api/v1/heatmap/overview first, so this avoids
        # a full-table SUM over realtime_station_stats on the first station click.
        if self._cache:
            overview_cache_key = (
                f"heatmap:overview:{time_range or 'default'}:all:{bucket_width_minutes}"
            )
            try:
                overview_cached = await self._cache.get_json(overview_cache_key)
                if not overview_cached:
                    overview_cached = await self._cache.get_stale_json(
                        overview_cache_key
                    )
                if overview_cached:
                    overview = HeatmapOverviewResponse.model_validate(overview_cached)
                    res = {
                        "cancellation_rate": float(
                            overview.summary.overall_cancellation_rate
                        ),
                        "delay_rate": float(overview.summary.overall_delay_rate),
                    }
                    try:
                        await self._cache.set_json(cache_key, res, ttl_seconds=600)
                    except Exception as e:
                        logger.warning(f"Network averages cache write failed: {e}")
                    return res
            except Exception as e:
                logger.warning(
                    "Heatmap overview cache read failed for network averages: %s",
                    e,
                )

        async def _sum_hourly(start: datetime, end: datetime) -> tuple[int, int, int]:
            stmt = select(
                func.sum(RealtimeStationStats.trip_count).label("total"),
                func.sum(RealtimeStationStats.cancelled_count).label("cancelled"),
                func.sum(RealtimeStationStats.delayed_count).label("delayed"),
            ).where(
                RealtimeStationStats.bucket_start >= start,
                RealtimeStationStats.bucket_start < end,
                RealtimeStationStats.bucket_width_minutes == bucket_width_minutes,
            )
            result = await self._session.execute(stmt)
            row = result.one_or_none()
            if not row or not row.total:
                return 0, 0, 0
            return int(row.total or 0), int(row.cancelled or 0), int(row.delayed or 0)

        async def _sum_daily(start_date: date, end_date: date) -> tuple[int, int, int]:
            stmt = select(
                func.sum(RealtimeStationStatsDaily.trip_count).label("total"),
                func.sum(RealtimeStationStatsDaily.cancelled_count).label("cancelled"),
                func.sum(RealtimeStationStatsDaily.delayed_count).label("delayed"),
            ).where(
                RealtimeStationStatsDaily.date >= start_date,
                RealtimeStationStatsDaily.date < end_date,
            )
            result = await self._session.execute(stmt)
            row = result.one_or_none()
            if not row or not row.total:
                return 0, 0, 0
            return int(row.total or 0), int(row.cancelled or 0), int(row.delayed or 0)

        total = cancelled = delayed = 0

        # For longer ranges, prefer daily summaries for the full-day middle segment.
        # This avoids scanning tens of millions of hourly rows for 7d/30d requests.
        if (
            bucket_width_minutes == 60
            and (to_time - from_time).total_seconds() >= 48 * 3600
        ):
            from_midnight_next = datetime.combine(
                from_time.date() + timedelta(days=1), time(0, 0), tzinfo=timezone.utc
            )
            to_midnight = datetime.combine(
                to_time.date(), time(0, 0), tzinfo=timezone.utc
            )

            # Head: from_time -> next midnight (partial first day)
            head_end = min(from_midnight_next, to_time)
            head_total, head_cancelled, head_delayed = await _sum_hourly(
                from_time, head_end
            )
            total += head_total
            cancelled += head_cancelled
            delayed += head_delayed

            # Middle: full days between head_end and to_midnight (exclusive of the last partial day)
            middle_start_date = head_end.date()
            middle_end_date = to_midnight.date()
            if middle_start_date < middle_end_date:
                # Only use daily summaries if we actually have at least one row in the range;
                # otherwise fall back to hourly for correctness in fresh installs.
                probe_stmt = (
                    select(RealtimeStationStatsDaily.id)
                    .where(
                        RealtimeStationStatsDaily.date >= middle_start_date,
                        RealtimeStationStatsDaily.date < middle_end_date,
                    )
                    .limit(1)
                )
                probe = await self._session.execute(probe_stmt)
                if probe.scalar_one_or_none() is not None:
                    mid_total, mid_cancelled, mid_delayed = await _sum_daily(
                        middle_start_date, middle_end_date
                    )
                    total += mid_total
                    cancelled += mid_cancelled
                    delayed += mid_delayed
                else:
                    mid_start_dt = datetime.combine(
                        middle_start_date, time(0, 0), tzinfo=timezone.utc
                    )
                    mid_end_dt = datetime.combine(
                        middle_end_date, time(0, 0), tzinfo=timezone.utc
                    )
                    mid_total, mid_cancelled, mid_delayed = await _sum_hourly(
                        mid_start_dt, mid_end_dt
                    )
                    total += mid_total
                    cancelled += mid_cancelled
                    delayed += mid_delayed

            # Tail: last midnight -> to_time (partial last day)
            if to_midnight < to_time:
                tail_total, tail_cancelled, tail_delayed = await _sum_hourly(
                    to_midnight, to_time
                )
                total += tail_total
                cancelled += tail_cancelled
                delayed += tail_delayed
        else:
            total, cancelled, delayed = await _sum_hourly(from_time, to_time)

        if total <= 0:
            res = {"cancellation_rate": 0.0, "delay_rate": 0.0}
        else:
            res = {
                "cancellation_rate": min((cancelled or 0) / total, 1.0),
                "delay_rate": min((delayed or 0) / total, 1.0),
            }

        # Cache for 10 minutes (network averages change slowly)
        if self._cache:
            try:
                await self._cache.set_json(cache_key, res, ttl_seconds=600)
            except Exception as e:
                logger.warning(f"Network averages cache write failed: {e}")

        return res
