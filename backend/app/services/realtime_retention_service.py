"""
Validated retention for historical realtime station statistics.

This service keeps hourly realtime rows until the matching daily rollup has been
validated. Monthly summaries are intentionally left as a future extension point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, and_, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.persistence.models import RealtimeStationStats, RealtimeStationStatsDaily

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RollupMetrics:
    trip_count: int
    delayed_count: int
    cancelled_count: int
    on_time_count: int
    total_delay_seconds: int


@dataclass(frozen=True, slots=True)
class RollupValidationResult:
    target_date: date
    has_daily_summary: bool
    hourly_station_count: int
    daily_station_count: int
    coverage_matches: bool
    metrics_match: bool
    can_delete: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RetentionRunResult:
    retention_enabled: bool
    cutoff_date: date | None
    eligible_dates: tuple[date, ...]
    validated_dates: tuple[date, ...]
    deleted_dates: tuple[date, ...]
    skipped_dates: tuple[date, ...]
    deleted_rows: int


class RealtimeRetentionService:
    """Validate daily rollups before purging historical hourly realtime rows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        retention_days: int | None = None,
        retention_enabled: bool | None = None,
        source_bucket_width_minutes: int = 60,
    ) -> None:
        settings = get_settings()

        hourly_retention_days = getattr(
            settings,
            "gtfs_rt_hourly_retention_days",
            settings.gtfs_rt_stats_retention_days,
        )

        self._session = session
        self._retention_days = int(
            retention_days if retention_days is not None else hourly_retention_days
        )
        self._retention_enabled = (
            settings.gtfs_rt_retention_enabled
            if retention_enabled is None
            else retention_enabled
        )
        self._source_bucket_width_minutes = source_bucket_width_minutes

    def _retention_cutoff_date(self, as_of: datetime | None = None) -> date:
        current = as_of or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        else:
            current = current.astimezone(timezone.utc)
        return current.date() - timedelta(days=self._retention_days)

    async def _eligible_dates_before(self, cutoff_date: date) -> list[date]:
        stmt = (
            select(cast(RealtimeStationStats.bucket_start, Date))
            .distinct()
            .where(cast(RealtimeStationStats.bucket_start, Date) < cutoff_date)
            .where(
                RealtimeStationStats.bucket_width_minutes
                == self._source_bucket_width_minutes
            )
            .order_by(cast(RealtimeStationStats.bucket_start, Date))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _load_hourly_rollup_for_date(
        self, target_date: date
    ) -> dict[str, RollupMetrics]:
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        stmt = (
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
            )
            .where(
                and_(
                    RealtimeStationStats.bucket_start >= day_start,
                    RealtimeStationStats.bucket_start < day_end,
                    RealtimeStationStats.bucket_width_minutes
                    == self._source_bucket_width_minutes,
                )
            )
            .group_by(RealtimeStationStats.stop_id)
        )

        result = await self._session.execute(stmt)
        rollup: dict[str, RollupMetrics] = {}
        for row in result.all():
            rollup[row.stop_id] = RollupMetrics(
                trip_count=int(row.trip_count or 0),
                delayed_count=int(row.delayed_count or 0),
                cancelled_count=int(row.cancelled_count or 0),
                on_time_count=int(row.on_time_count or 0),
                total_delay_seconds=int(row.total_delay_seconds or 0),
            )
        return rollup

    async def _load_daily_rollup_for_date(
        self, target_date: date
    ) -> dict[str, RollupMetrics]:
        stmt = select(
            RealtimeStationStatsDaily.stop_id,
            RealtimeStationStatsDaily.trip_count,
            RealtimeStationStatsDaily.delayed_count,
            RealtimeStationStatsDaily.cancelled_count,
            RealtimeStationStatsDaily.on_time_count,
            RealtimeStationStatsDaily.total_delay_seconds,
        ).where(RealtimeStationStatsDaily.date == target_date)

        result = await self._session.execute(stmt)
        rollup: dict[str, RollupMetrics] = {}
        for row in result.all():
            rollup[row.stop_id] = RollupMetrics(
                trip_count=int(row.trip_count or 0),
                delayed_count=int(row.delayed_count or 0),
                cancelled_count=int(row.cancelled_count or 0),
                on_time_count=int(row.on_time_count or 0),
                total_delay_seconds=int(row.total_delay_seconds or 0),
            )
        return rollup

    async def _delete_hourly_rows_for_date(self, target_date: date) -> int:
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        stmt = delete(RealtimeStationStats).where(
            and_(
                RealtimeStationStats.bucket_start >= day_start,
                RealtimeStationStats.bucket_start < day_end,
                RealtimeStationStats.bucket_width_minutes
                == self._source_bucket_width_minutes,
            )
        )

        result = await self._session.execute(stmt)
        deleted = getattr(result, "rowcount", 0) or 0
        return int(deleted)

    def _build_validation_result(
        self,
        *,
        target_date: date,
        hourly_rollup: dict[str, RollupMetrics],
        daily_rollup: dict[str, RollupMetrics],
    ) -> RollupValidationResult:
        has_daily_summary = bool(daily_rollup)
        hourly_station_count = len(hourly_rollup)
        daily_station_count = len(daily_rollup)
        coverage_matches = hourly_rollup.keys() == daily_rollup.keys()

        metrics_match = False
        reason: str | None = None

        if not hourly_rollup:
            reason = "no_hourly_data"
        elif not has_daily_summary:
            reason = "missing_daily_summary"
        elif not coverage_matches:
            reason = "station_coverage_mismatch"
        else:
            metrics_match = hourly_rollup == daily_rollup
            if not metrics_match:
                for stop_id, hourly_metrics in hourly_rollup.items():
                    if daily_rollup.get(stop_id) != hourly_metrics:
                        reason = f"metric_mismatch:{stop_id}"
                        break

        can_delete = bool(
            hourly_rollup and has_daily_summary and coverage_matches and metrics_match
        )

        return RollupValidationResult(
            target_date=target_date,
            has_daily_summary=has_daily_summary,
            hourly_station_count=hourly_station_count,
            daily_station_count=daily_station_count,
            coverage_matches=coverage_matches,
            metrics_match=metrics_match,
            can_delete=can_delete,
            reason=reason,
        )

    async def validate_daily_rollup(self, target_date: date) -> RollupValidationResult:
        """Validate that hourly totals match the daily summary for one date."""

        hourly_rollup = await self._load_hourly_rollup_for_date(target_date)
        daily_rollup = await self._load_daily_rollup_for_date(target_date)
        return self._build_validation_result(
            target_date=target_date,
            hourly_rollup=hourly_rollup,
            daily_rollup=daily_rollup,
        )

    async def purge_expired_hourly_stats(
        self,
        *,
        as_of: datetime | None = None,
    ) -> RetentionRunResult:
        """Delete hourly rows only after their daily summaries validate."""

        if not self._retention_enabled:
            return RetentionRunResult(
                retention_enabled=False,
                cutoff_date=None,
                eligible_dates=(),
                validated_dates=(),
                deleted_dates=(),
                skipped_dates=(),
                deleted_rows=0,
            )

        cutoff_date = self._retention_cutoff_date(as_of)
        eligible_dates = tuple(await self._eligible_dates_before(cutoff_date))

        validated_dates: list[date] = []
        deleted_dates: list[date] = []
        skipped_dates: list[date] = []
        deleted_rows = 0

        for target_date in eligible_dates:
            validation = await self.validate_daily_rollup(target_date)
            if not validation.can_delete:
                skipped_dates.append(target_date)
                logger.info(
                    "Skipped realtime retention for %s: %s",
                    target_date,
                    validation.reason or "validation_failed",
                )
                continue

            rows_deleted = await self._delete_hourly_rows_for_date(target_date)
            validated_dates.append(target_date)
            deleted_dates.append(target_date)
            deleted_rows += rows_deleted
            logger.info(
                "Deleted %d hourly realtime rows for %s after validation",
                rows_deleted,
                target_date,
            )

        if deleted_rows > 0:
            await self._session.commit()

        return RetentionRunResult(
            retention_enabled=True,
            cutoff_date=cutoff_date,
            eligible_dates=eligible_dates,
            validated_dates=tuple(validated_dates),
            deleted_dates=tuple(deleted_dates),
            skipped_dates=tuple(skipped_dates),
            deleted_rows=deleted_rows,
        )

    def _monthly_rollup_extension_point(self, target_date: date) -> None:
        """Placeholder for future monthly summary retention validation."""
        _ = target_date
        return None
