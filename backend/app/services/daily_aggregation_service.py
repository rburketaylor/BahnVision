"""
Daily aggregation service for heatmap performance optimization.

Aggregates hourly realtime_station_stats into daily summaries to improve
query performance for large time range heatmap requests (7d, 30d).
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    RealtimeStationStats,
    RealtimeStationStatsDaily,
)

# GTFS route_type mapping to our transport types (from heatmap_service.py)
GTFS_ROUTE_TYPES: dict[int, str] = {
    0: "TRAM",
    1: "UBAHN",
    2: "BAHN",
    3: "BUS",
    4: "SCHIFF",
    5: "TRAM",
    6: "TRAM",
    7: "TRAM",
    11: "TRAM",
    12: "BAHN",
    100: "BAHN",
    109: "SBAHN",
    400: "UBAHN",
    700: "BUS",
    900: "TRAM",
    1000: "SCHIFF",
}

logger = logging.getLogger(__name__)

# Threshold for using daily summaries (days)
_DAILY_SUMMARY_THRESHOLD_DAYS = 3

# Number of hourly buckets expected in a full daily summary
_EXPECTED_HOURLY_BUCKETS = 24


class DailyAggregationService:
    """Service for aggregating hourly station stats into daily summaries."""

    def __init__(
        self,
        session: AsyncSession,
        gtfs_route_types: dict[int, str] | None = None,
    ) -> None:
        """Initialize the daily aggregation service.

        Args:
            session: Database async session
            gtfs_route_types: Optional mapping of GTFS route_type to transport type names
        """
        self._session = session
        self._gtfs_route_types = gtfs_route_types or GTFS_ROUTE_TYPES

    async def aggregate_day(self, target_date: date) -> int:
        """Aggregate hourly stats for a single day.

        Queries all hourly buckets for the target date, aggregates them per station,
        and stores the results in realtime_station_stats_daily.

        Args:
            target_date: The date to aggregate (UTC calendar day)

        Returns:
            Number of stations aggregated
        """
        started = time.monotonic()

        # Define the time range for the target date (UTC)
        day_start = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc
        )
        day_end = day_start + timedelta(days=1)

        logger.info("Starting daily aggregation for %s", target_date)

        # Query hourly stats for this date
        hourly_stmt = (
            select(
                RealtimeStationStats.stop_id,
                func.coalesce(func.sum(RealtimeStationStats.trip_count), 0).label(
                    "trip_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.delayed_count), 0).label(
                    "delayed_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.cancelled_count), 0).label(
                    "cancelled_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.on_time_count), 0).label(
                    "on_time_count"
                ),
                func.coalesce(
                    func.sum(RealtimeStationStats.total_delay_seconds), 0
                ).label("total_delay_seconds"),
                func.count(RealtimeStationStats.id).label("observation_count"),
            )
            .where(
                and_(
                    RealtimeStationStats.bucket_start >= day_start,
                    RealtimeStationStats.bucket_start < day_end,
                    RealtimeStationStats.bucket_width_minutes == 60,
                )
            )
            .group_by(RealtimeStationStats.stop_id)
        )

        result = await self._session.execute(hourly_stmt)
        hourly_rows = result.all()

        if not hourly_rows:
            logger.info("No hourly data found for %s", target_date)
            return 0

        # Fetch per-route-type breakdowns for all stations in one query
        station_ids = [row.stop_id for row in hourly_rows]

        breakdown_stmt = (
            select(
                RealtimeStationStats.stop_id,
                RealtimeStationStats.route_type,
                func.coalesce(func.sum(RealtimeStationStats.trip_count), 0).label(
                    "trip_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.cancelled_count), 0).label(
                    "cancelled_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.delayed_count), 0).label(
                    "delayed_count"
                ),
                func.coalesce(func.sum(RealtimeStationStats.on_time_count), 0).label(
                    "on_time_count"
                ),
            )
            .where(
                and_(
                    RealtimeStationStats.bucket_start >= day_start,
                    RealtimeStationStats.bucket_start < day_end,
                    RealtimeStationStats.bucket_width_minutes == 60,
                    RealtimeStationStats.stop_id.in_(station_ids),
                )
            )
            .group_by(RealtimeStationStats.stop_id, RealtimeStationStats.route_type)
        )

        breakdown_result = await self._session.execute(breakdown_stmt)
        breakdown_rows = breakdown_result.all()

        # Build breakdown by station and transport type
        breakdown_by_station: dict[str, dict[str, dict[str, int]]] = {}
        for breakdown_row in breakdown_rows:
            stop_id = breakdown_row.stop_id
            route_type = breakdown_row.route_type

            if route_type is None:
                # Skip NULL route_type (already included in totals)
                continue

            transport_type = self._gtfs_route_types.get(route_type, "BUS")

            if stop_id not in breakdown_by_station:
                breakdown_by_station[stop_id] = {}

            breakdown_by_station[stop_id][transport_type] = {
                "trips": int(breakdown_row.trip_count),
                "cancelled": int(breakdown_row.cancelled_count),
                "delayed": int(breakdown_row.delayed_count),
                "on_time": int(breakdown_row.on_time_count),
            }

        # Delete existing daily summaries for this date
        delete_stmt = delete(RealtimeStationStatsDaily).where(
            RealtimeStationStatsDaily.date == target_date
        )
        await self._session.execute(delete_stmt)

        # Insert new daily summaries
        stations_created = 0
        for hourly_row in hourly_rows:
            daily_summary = RealtimeStationStatsDaily(
                stop_id=hourly_row.stop_id,
                date=target_date,
                trip_count=int(hourly_row.trip_count),
                delayed_count=int(hourly_row.delayed_count),
                cancelled_count=int(hourly_row.cancelled_count),
                on_time_count=int(hourly_row.on_time_count),
                total_delay_seconds=int(hourly_row.total_delay_seconds),
                observation_count=int(hourly_row.observation_count),
                by_route_type=breakdown_by_station.get(hourly_row.stop_id, {}),
            )
            self._session.add(daily_summary)
            stations_created += 1

        await self._session.commit()

        elapsed_ms = (time.monotonic() - started) * 1000
        logger.info(
            "Aggregated %d stations for %s in %dms",
            stations_created,
            target_date,
            int(elapsed_ms),
        )

        return stations_created

    async def aggregate_date_range(
        self, start_date: date, end_date: date
    ) -> dict[str, int]:
        """Aggregate a range of dates.

        Args:
            start_date: Inclusive start date
            end_date: Exclusive end date

        Returns:
            Dict with date strings as keys and station counts as values
        """
        results: dict[str, int] = {}
        current = start_date

        while current < end_date:
            try:
                count = await self.aggregate_day(current)
                results[str(current)] = count
            except Exception as e:
                logger.error("Failed to aggregate %s: %s", current, e)
                results[str(current)] = -1
            current += timedelta(days=1)

        return results

    async def backfill_days(self, days_back: int = 30) -> dict[str, int]:
        """Backfill historical daily aggregations.

        Args:
            days_back: Number of days to backfill from yesterday

        Returns:
            Dict with date strings as keys and station count or error code as values
        """
        today = date.today()
        # Start from days_back days ago, go through yesterday
        start_date = today - timedelta(days=days_back)
        end_date = today  # Don't aggregate today (still accumulating)

        logger.info("Starting backfill from %s to %s", start_date, end_date)

        return await self.aggregate_date_range(start_date, end_date)

    async def is_day_aggregated(self, target_date: date) -> bool:
        """Check if a daily summary exists for the given date.

        Args:
            target_date: Date to check

        Returns:
            True if daily summary exists with data
        """
        stmt = select(func.count()).where(RealtimeStationStatsDaily.date == target_date)
        result = await self._session.execute(stmt)
        count = result.scalar()

        return (count or 0) > 0

    async def get_aggregation_coverage(self, days_back: int = 30) -> dict[str, bool]:
        """Check which days have daily summaries.

        Args:
            days_back: Number of past days to check

        Returns:
            Dict mapping date strings to aggregation status
        """
        today = date.today()
        coverage: dict[str, bool] = {}

        for i in range(days_back):
            check_date = today - timedelta(days=i)
            is_aggregated = await self.is_day_aggregated(check_date)
            coverage[str(check_date)] = is_aggregated

        return coverage


def should_use_daily_summary(from_time: datetime, to_time: datetime) -> bool:
    """Determine if daily summaries should be used for the given time range.

    Args:
        from_time: Start of time range
        to_time: End of time range

    Returns:
        True if the range spans >= threshold days
    """
    delta = to_time - from_time
    return delta.days >= _DAILY_SUMMARY_THRESHOLD_DAYS
