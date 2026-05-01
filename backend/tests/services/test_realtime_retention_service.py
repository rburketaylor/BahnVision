"""Tests for the realtime retention service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.realtime_retention_service import (
    RealtimeRetentionService,
    RetentionRunResult,
    RollupMetrics,
    RollupValidationResult,
)


@dataclass(frozen=True, slots=True)
class _RetentionScenario:
    eligible_dates: tuple[date, ...]
    hourly_rollups: dict[date, dict[str, RollupMetrics]]
    daily_rollups: dict[date, dict[str, RollupMetrics]]
    delete_rowcounts: dict[date, int]


class FakeRetentionService(RealtimeRetentionService):
    def __init__(
        self,
        scenario: _RetentionScenario,
        *,
        retention_days: int = 30,
        retention_enabled: bool = True,
    ) -> None:
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.in_transaction = AsyncMock(return_value=False)
        super().__init__(
            session=mock_session,  # type: ignore[arg-type]
            retention_days=retention_days,
            retention_enabled=retention_enabled,
        )
        self._scenario = scenario
        self.deleted_dates: list[date] = []

    async def _eligible_dates_before(self, cutoff_date: date) -> list[date]:
        return [d for d in self._scenario.eligible_dates if d < cutoff_date]

    async def _load_hourly_rollup_for_date(
        self, target_date: date
    ) -> dict[str, RollupMetrics]:
        return self._scenario.hourly_rollups.get(target_date, {})

    async def _load_daily_rollup_for_date(
        self, target_date: date
    ) -> dict[str, RollupMetrics]:
        return self._scenario.daily_rollups.get(target_date, {})

    async def _delete_hourly_rows_for_date(self, target_date: date) -> int:
        self.deleted_dates.append(target_date)
        return self._scenario.delete_rowcounts.get(target_date, 0)


def _metrics(
    *,
    trips: int,
    delayed: int,
    cancelled: int,
    on_time: int,
    delay_seconds: int,
) -> RollupMetrics:
    return RollupMetrics(
        trip_count=trips,
        delayed_count=delayed,
        cancelled_count=cancelled,
        on_time_count=on_time,
        total_delay_seconds=delay_seconds,
    )


class TestRealtimeRetentionService:
    @pytest.mark.asyncio
    async def test_validate_daily_rollup_refuses_date_with_no_daily_summary(self):
        scenario = _RetentionScenario(
            eligible_dates=(date(2025, 1, 15),),
            hourly_rollups={
                date(2025, 1, 15): {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            daily_rollups={},
            delete_rowcounts={},
        )
        service = FakeRetentionService(scenario)

        validation = await service.validate_daily_rollup(date(2025, 1, 15))

        assert validation == RollupValidationResult(
            target_date=date(2025, 1, 15),
            has_daily_summary=False,
            hourly_station_count=1,
            daily_station_count=0,
            coverage_matches=False,
            metrics_match=False,
            can_delete=False,
            reason="missing_daily_summary",
        )

    @pytest.mark.asyncio
    async def test_validate_daily_rollup_refuses_mismatched_totals(self):
        target_date = date(2025, 1, 15)
        scenario = _RetentionScenario(
            eligible_dates=(target_date,),
            hourly_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            daily_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=11,
                        cancelled=5,
                        on_time=84,
                        delay_seconds=600,
                    )
                }
            },
            delete_rowcounts={},
        )
        service = FakeRetentionService(scenario)

        validation = await service.validate_daily_rollup(target_date)

        assert validation.target_date == target_date
        assert validation.has_daily_summary is True
        assert validation.coverage_matches is True
        assert validation.metrics_match is False
        assert validation.can_delete is False
        assert validation.reason == "metric_mismatch:de:09162:6"

    @pytest.mark.asyncio
    async def test_purge_expired_hourly_stats_deletes_validated_old_date(self):
        target_date = date(2025, 1, 15)
        scenario = _RetentionScenario(
            eligible_dates=(target_date,),
            hourly_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    ),
                    "de:09162:1": _metrics(
                        trips=50,
                        delayed=5,
                        cancelled=1,
                        on_time=44,
                        delay_seconds=120,
                    ),
                }
            },
            daily_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    ),
                    "de:09162:1": _metrics(
                        trips=50,
                        delayed=5,
                        cancelled=1,
                        on_time=44,
                        delay_seconds=120,
                    ),
                }
            },
            delete_rowcounts={target_date: 48},
        )
        service = FakeRetentionService(scenario)

        result = await service.purge_expired_hourly_stats(
            as_of=datetime(2025, 2, 20, tzinfo=timezone.utc)
        )

        assert result == RetentionRunResult(
            retention_enabled=True,
            cutoff_date=date(2025, 1, 21),
            eligible_dates=(target_date,),
            validated_dates=(target_date,),
            deleted_dates=(target_date,),
            skipped_dates=(),
            deleted_rows=48,
        )
        assert service.deleted_dates == [target_date]
        service._session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_purge_expired_hourly_stats_skips_rows_newer_than_cutoff(self):
        target_date = date(2025, 2, 15)
        scenario = _RetentionScenario(
            eligible_dates=(target_date,),
            hourly_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            daily_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            delete_rowcounts={target_date: 24},
        )
        service = FakeRetentionService(scenario)

        result = await service.purge_expired_hourly_stats(
            as_of=datetime(2025, 3, 1, tzinfo=timezone.utc)
        )

        assert result.eligible_dates == ()
        assert result.deleted_rows == 0
        assert result.deleted_dates == ()
        assert service.deleted_dates == []
        service._session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_purge_expired_hourly_stats_is_noop_when_disabled(self):
        target_date = date(2025, 1, 15)
        scenario = _RetentionScenario(
            eligible_dates=(target_date,),
            hourly_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            daily_rollups={
                target_date: {
                    "de:09162:6": _metrics(
                        trips=100,
                        delayed=10,
                        cancelled=5,
                        on_time=85,
                        delay_seconds=600,
                    )
                }
            },
            delete_rowcounts={target_date: 24},
        )
        service = FakeRetentionService(scenario, retention_enabled=False)

        result = await service.purge_expired_hourly_stats(
            as_of=datetime(2025, 3, 1, tzinfo=timezone.utc)
        )

        assert result == RetentionRunResult(
            retention_enabled=False,
            cutoff_date=None,
            eligible_dates=(),
            validated_dates=(),
            deleted_dates=(),
            skipped_dates=(),
            deleted_rows=0,
        )
        assert service.deleted_dates == []
