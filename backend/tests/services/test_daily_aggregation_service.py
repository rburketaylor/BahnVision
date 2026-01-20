"""
Tests for the daily aggregation service.

Tests the service that aggregates hourly station stats into daily summaries
for improved query performance on large time ranges.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from app.persistence.models import RealtimeStationStatsDaily
from app.services.daily_aggregation_service import (
    DailyAggregationService,
    should_use_daily_summary,
)


@dataclass
class FakeRow:
    """Fake SQLAlchemy row for testing."""

    stop_id: str
    trip_count: int
    delayed_count: int
    cancelled_count: int
    on_time_count: int
    total_delay_seconds: int | None = None
    observation_count: int | None = None
    route_type: int | None = None


class FakeResult:
    """Fake SQLAlchemy result for testing."""

    def __init__(
        self, rows: list[FakeRow] | None = None, scalar_value: int | None = None
    ):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def all(self) -> list[FakeRow]:
        return self._rows

    def scalar(self) -> int | None:
        if self._scalar_value is not None:
            return self._scalar_value
        return len(self._rows) if self._rows else 0


class FakeAsyncSession:
    """Fake async database session for testing."""

    def __init__(
        self,
        hourly_rows: list[FakeRow] | None = None,
        breakdown_rows: list[FakeRow] | None = None,
        existing_daily_count: int = 0,
        raise_on_execute: Exception | None = None,
    ):
        self._hourly_rows = hourly_rows or []
        self._breakdown_rows = breakdown_rows or []
        self._existing_daily_count = existing_daily_count
        self._raise_on_execute = raise_on_execute
        self.executed_statements: list[object] = []
        self.committed = False
        self._delete_count = 0
        self._inserted_objects: list[RealtimeStationStatsDaily] = []

    async def execute(self, stmt) -> FakeResult:
        self.executed_statements.append(stmt)

        # Track delete statements (daily_aggregation_service.py:183-186)
        stmt_str = str(stmt).lower()
        if "delete" in stmt_str and "realtime_station_stats_daily" in stmt_str:
            self._delete_count += 1

        if self._raise_on_execute:
            raise self._raise_on_execute

        # Return hourly aggregation results
        if "trip_count" in str(stmt) and "delayed_count" in str(stmt):
            if self._breakdown_rows and "route_type" in str(stmt):
                return FakeResult(self._breakdown_rows)
            return FakeResult(self._hourly_rows)

        # Return count for is_day_aggregated check
        if "count" in str(stmt).lower():
            return FakeResult(scalar_value=self._existing_daily_count)

        return FakeResult([])

    async def commit(self) -> None:
        self.committed = True

    def add(self, obj: RealtimeStationStatsDaily) -> None:
        self._inserted_objects.append(obj)


class TestShouldUseDailySummary:
    """Tests for should_use_daily_summary function."""

    def test_uses_hourly_for_small_ranges(self):
        """Test that small time ranges use hourly data."""
        # 1 hour
        assert not should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 15, 1, 0, tzinfo=timezone.utc),
        )

        # 24 hours
        assert not should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 16, 0, 0, tzinfo=timezone.utc),
        )

        # 2 days (48 hours)
        assert not should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 17, 0, 0, tzinfo=timezone.utc),
        )

    def test_uses_daily_for_large_ranges(self):
        """Test that large time ranges use daily summaries."""
        # 3 days exactly (threshold)
        assert should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 18, 0, 0, tzinfo=timezone.utc),
        )

        # 7 days
        assert should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 22, 0, 0, tzinfo=timezone.utc),
        )

        # 30 days
        assert should_use_daily_summary(
            datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 2, 14, 0, 0, tzinfo=timezone.utc),
        )


class TestDailyAggregationService:
    """Tests for DailyAggregationService."""

    @pytest.mark.asyncio
    async def test_aggregate_day_no_data(self):
        """Test aggregating a day with no hourly data."""
        session = FakeAsyncSession(hourly_rows=[], breakdown_rows=[])
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 0
        # When there's no data, aggregate_day returns early without commit
        # (see line 122-124 in daily_aggregation_service.py)

    @pytest.mark.asyncio
    async def test_aggregate_day_single_station(self):
        """Test aggregating a day with a single station."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,  # UBAHN
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 1
        assert session.committed
        assert len(session._inserted_objects) == 1

        daily = session._inserted_objects[0]
        assert daily.stop_id == "de:09162:6"
        assert daily.date == date(2025, 1, 15)
        assert daily.trip_count == 100
        assert daily.delayed_count == 10
        assert daily.cancelled_count == 5
        assert daily.on_time_count == 85
        assert daily.total_delay_seconds == 600
        assert daily.observation_count == 24
        assert "UBAHN" in daily.by_route_type
        assert daily.by_route_type["UBAHN"]["trips"] == 100
        assert daily.by_route_type["UBAHN"]["cancelled"] == 5

    @pytest.mark.asyncio
    async def test_aggregate_day_multiple_stations(self):
        """Test aggregating a day with multiple stations."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            ),
            FakeRow(
                stop_id="de:09162:1",
                trip_count=200,
                delayed_count=20,
                cancelled_count=10,
                on_time_count=170,
                total_delay_seconds=1200,
                observation_count=24,
            ),
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            ),
            FakeRow(
                stop_id="de:09162:1",
                route_type=109,
                trip_count=200,
                delayed_count=20,
                cancelled_count=10,
                on_time_count=170,
            ),
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 2
        assert len(session._inserted_objects) == 2
        assert session.committed

    @pytest.mark.asyncio
    async def test_aggregate_day_multiple_route_types(self):
        """Test aggregating per-route-type breakdowns correctly."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=300,
                delayed_count=30,
                cancelled_count=15,
                on_time_count=255,
                total_delay_seconds=1800,
                observation_count=24,
            )
        ]
        # Multiple route types for same station
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,  # UBAHN
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            ),
            FakeRow(
                stop_id="de:09162:6",
                route_type=109,  # SBAHN
                trip_count=200,
                delayed_count=20,
                cancelled_count=10,
                on_time_count=170,
            ),
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 1
        daily = session._inserted_objects[0]

        # Total counts should be summed
        assert daily.trip_count == 300
        assert daily.cancelled_count == 15

        # Breakdown should have both types
        assert "UBAHN" in daily.by_route_type
        assert "SBAHN" in daily.by_route_type
        assert daily.by_route_type["UBAHN"]["trips"] == 100
        assert daily.by_route_type["SBAHN"]["trips"] == 200

    @pytest.mark.asyncio
    async def test_aggregate_day_unknown_route_type_defaults_to_bus(self):
        """Test that unknown route types default to BUS."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        # Unknown route type (9999)
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=9999,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 1
        daily = session._inserted_objects[0]
        assert "BUS" in daily.by_route_type

    @pytest.mark.asyncio
    async def test_aggregate_day_skips_null_route_type(self):
        """Test that NULL route_type is skipped in breakdown."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        # NULL route_type should be skipped
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=None,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        count = await service.aggregate_day(date(2025, 1, 15))

        assert count == 1
        daily = session._inserted_objects[0]
        # Breakdown should be empty since only NULL route_type was provided
        assert daily.by_route_type == {}

    @pytest.mark.asyncio
    async def test_aggregate_day_deletes_existing(self):
        """Test that existing daily summaries are deleted before inserting."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        await service.aggregate_day(date(2025, 1, 15))

        # Should have executed a delete statement
        assert session._delete_count == 1

    @pytest.mark.asyncio
    async def test_is_day_aggregated_true(self):
        """Test is_day_aggregated returns True when data exists."""
        session = FakeAsyncSession(existing_daily_count=5)
        service = DailyAggregationService(session=session)

        result = await service.is_day_aggregated(date(2025, 1, 15))

        assert result is True

    @pytest.mark.asyncio
    async def test_is_day_aggregated_false(self):
        """Test is_day_aggregated returns False when no data exists."""
        session = FakeAsyncSession(existing_daily_count=0)
        service = DailyAggregationService(session=session)

        result = await service.is_day_aggregated(date(2025, 1, 15))

        assert result is False

    @pytest.mark.asyncio
    async def test_aggregate_date_range(self):
        """Test aggregating a range of dates."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        results = await service.aggregate_date_range(
            date(2025, 1, 15),
            date(2025, 1, 17),  # 2 days
        )

        assert len(results) == 2
        assert results["2025-01-15"] == 1
        assert results["2025-01-16"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_date_range_handles_errors(self):
        """Test that errors during aggregation are handled gracefully."""

        class RaiseOnceSession(FakeAsyncSession):
            """Session that raises on first execute call."""

            def __init__(self, *args, call_count=0, **kwargs):
                super().__init__(*args, **kwargs)
                self.call_count = call_count

            async def execute(self, stmt):
                self.call_count += 1
                if self.call_count == 1:
                    raise RuntimeError("Database error")
                return await super().execute(stmt)

        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = RaiseOnceSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        results = await service.aggregate_date_range(
            date(2025, 1, 15), date(2025, 1, 17)
        )

        # First day should fail with -1
        assert results["2025-01-15"] == -1
        # Second day should succeed
        assert results["2025-01-16"] == 1

    @pytest.mark.asyncio
    async def test_backfill_days(self):
        """Test backfilling historical data."""
        hourly_rows = [
            FakeRow(
                stop_id="de:09162:6",
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
                total_delay_seconds=600,
                observation_count=24,
            )
        ]
        breakdown_rows = [
            FakeRow(
                stop_id="de:09162:6",
                route_type=400,
                trip_count=100,
                delayed_count=10,
                cancelled_count=5,
                on_time_count=85,
            )
        ]

        session = FakeAsyncSession(
            hourly_rows=hourly_rows, breakdown_rows=breakdown_rows
        )
        service = DailyAggregationService(session=session)

        # Mock date.today() to return a fixed date
        import unittest.mock

        with unittest.mock.patch(
            "app.services.daily_aggregation_service.date"
        ) as mock_date:
            mock_date.today.return_value = date(2025, 1, 17)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            results = await service.backfill_days(days_back=5)

            # Should aggregate 5 days (from 2025-01-12 to 2025-01-16)
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_get_aggregation_coverage(self):
        """Test getting aggregation coverage for multiple days."""
        session = FakeAsyncSession(existing_daily_count=5)
        service = DailyAggregationService(session=session)

        coverage = await service.get_aggregation_coverage(days_back=3)

        assert len(coverage) == 3
        # All days should show as aggregated since we set existing_daily_count=5
        assert all(coverage.values())

    @pytest.mark.asyncio
    async def test_get_aggregation_coverage_empty(self):
        """Test aggregation coverage with no data."""
        session = FakeAsyncSession(existing_daily_count=0)
        service = DailyAggregationService(session=session)

        coverage = await service.get_aggregation_coverage(days_back=3)

        assert len(coverage) == 3
        # All days should show as not aggregated
        assert not any(coverage.values())
