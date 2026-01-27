"""
Tests for the StationStatsService.

Tests the station statistics service async methods for fetching
station-level metrics and trends from the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

from app.models.station_stats import (
    StationStats,
    StationTrends,
)
from app.services.station_stats_service import StationStatsService


class FakeResult:
    """Fake SQLAlchemy result for testing."""

    def __init__(self, rows: list[object]):
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows

    def one_or_none(self) -> object | None:
        return self._rows[0] if self._rows else None


class FakeAsyncSession:
    """Fake async database session for testing."""

    def __init__(
        self,
        rows: list[object] | None = None,
        raise_on_execute: Exception | None = None,
    ):
        self._rows = rows or []
        self._raise_on_execute = raise_on_execute
        self._call_count = 0

    async def execute(self, stmt) -> FakeResult:
        if self._raise_on_execute:
            raise self._raise_on_execute
        self._call_count += 1
        return FakeResult(self._rows)


@dataclass
class FakeStopInfo:
    """Fake stop info for testing."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    location_type: int = 0
    parent_station: Optional[str] = None


class FakeGTFSScheduleService:
    """Fake GTFS schedule service for testing."""

    def __init__(self, stop_info: FakeStopInfo | None = None):
        self._stop_info = stop_info

    async def get_stop_by_id(self, stop_id: str) -> FakeStopInfo | None:
        if self._stop_info and self._stop_info.stop_id == stop_id:
            return self._stop_info
        return None


@dataclass
class FakeStatsRow:
    """Fake database row for station stats."""

    route_type: int
    total_departures: int
    cancelled_count: int
    delayed_count: int


@dataclass
class FakeTrendRow:
    """Fake database row for trend data."""

    bucket: datetime
    total_departures: int
    cancelled_count: int
    delayed_count: int


@dataclass
class FakeNetworkRow:
    """Fake database row for network averages."""

    total: int
    cancelled: int
    delayed: int


@pytest.fixture
def sample_stop() -> FakeStopInfo:
    """Sample stop for testing."""
    return FakeStopInfo(
        stop_id="de:09162:6",
        stop_name="Marienplatz",
        stop_lat=48.13743,
        stop_lon=11.57549,
    )


@pytest.fixture
def sample_stats_rows() -> list[FakeStatsRow]:
    """Sample stats rows with data."""
    return [
        FakeStatsRow(
            route_type=1, total_departures=100, cancelled_count=5, delayed_count=10
        ),
        FakeStatsRow(
            route_type=2, total_departures=50, cancelled_count=2, delayed_count=8
        ),
    ]


@pytest.fixture
def sample_trend_rows() -> list[FakeTrendRow]:
    """Sample trend rows with hourly data."""
    now = datetime.now(timezone.utc)
    return [
        FakeTrendRow(
            bucket=now - timedelta(hours=2),
            total_departures=40,
            cancelled_count=2,
            delayed_count=5,
        ),
        FakeTrendRow(
            bucket=now - timedelta(hours=1),
            total_departures=60,
            cancelled_count=3,
            delayed_count=8,
        ),
    ]


class TestStationStatsService:
    """Tests for StationStatsService."""

    @pytest.mark.asyncio
    async def test_get_station_stats_returns_none_for_unknown_station(self):
        """Test get_station_stats returns None for unknown station."""
        session = FakeAsyncSession()
        gtfs_schedule = FakeGTFSScheduleService(stop_info=None)
        service = StationStatsService(session, gtfs_schedule)

        result = await service.get_station_stats("unknown:station")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_station_stats_returns_empty_when_no_data(self, sample_stop):
        """Test get_station_stats returns empty stats when no DB data."""
        session = FakeAsyncSession(rows=[])
        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session, gtfs_schedule)

        result = await service.get_station_stats(sample_stop.stop_id)

        assert result is not None
        assert isinstance(result, StationStats)
        assert result.station_id == sample_stop.stop_id
        assert result.station_name == sample_stop.stop_name
        assert result.total_departures == 0
        assert result.cancelled_count == 0
        assert result.cancellation_rate == 0.0
        assert result.delayed_count == 0
        assert result.delay_rate == 0.0
        assert result.by_transport == []

    @pytest.mark.asyncio
    async def test_get_station_stats_aggregates_transport_data(
        self, sample_stop, sample_stats_rows
    ):
        """Test get_station_stats aggregates data by transport type."""
        # First query returns stats rows, second query returns network averages
        session = MagicMock()
        stats_result = MagicMock()
        stats_result.all.return_value = sample_stats_rows
        network_result = MagicMock()
        network_result.one_or_none.return_value = FakeNetworkRow(
            total=1000, cancelled=30, delayed=100
        )

        async def execute_side_effect(stmt):
            if session.execute.call_count == 1:
                return stats_result
            return network_result

        session.execute = MagicMock(side_effect=execute_side_effect)
        session.execute = execute_side_effect  # Make it async

        # Use a simpler approach - mock properly
        session_mock = MagicMock()
        session_mock.execute = MagicMock()

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        # Mock execute to return AsyncMock

        call_count = 0

        async def async_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stats_result
            return network_result

        session_mock.execute = async_execute

        result = await service.get_station_stats(sample_stop.stop_id)

        assert result is not None
        assert result.total_departures == 150  # 100 + 50
        assert result.cancelled_count == 7  # 5 + 2
        assert result.delayed_count == 18  # 10 + 8
        assert len(result.by_transport) == 2

    @pytest.mark.asyncio
    async def test_get_station_stats_calculates_rates(self, sample_stop):
        """Test get_station_stats calculates cancellation and delay rates."""
        stats_rows = [
            FakeStatsRow(
                route_type=1, total_departures=100, cancelled_count=10, delayed_count=20
            )
        ]

        session_mock = MagicMock()
        stats_result = MagicMock()
        stats_result.all.return_value = stats_rows
        network_result = MagicMock()
        network_result.one_or_none.return_value = FakeNetworkRow(
            total=1000, cancelled=50, delayed=100
        )

        call_count = 0

        async def async_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return stats_result
            return network_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        result = await service.get_station_stats(sample_stop.stop_id)

        assert result is not None
        assert result.cancellation_rate == 0.1  # 10/100
        assert result.delay_rate == 0.2  # 20/100
        assert result.network_avg_cancellation_rate == 0.05  # 50/1000
        assert result.network_avg_delay_rate == 0.1  # 100/1000

    @pytest.mark.asyncio
    async def test_get_station_trends_returns_none_for_unknown_station(self):
        """Test get_station_trends returns None for unknown station."""
        session = FakeAsyncSession()
        gtfs_schedule = FakeGTFSScheduleService(stop_info=None)
        service = StationStatsService(session, gtfs_schedule)

        result = await service.get_station_trends("unknown:station")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_station_trends_returns_empty_when_no_data(self, sample_stop):
        """Test get_station_trends returns empty trends when no DB data."""
        session = FakeAsyncSession(rows=[])
        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session, gtfs_schedule)

        result = await service.get_station_trends(sample_stop.stop_id)

        assert result is not None
        assert isinstance(result, StationTrends)
        assert result.station_id == sample_stop.stop_id
        assert result.station_name == sample_stop.stop_name
        assert result.data_points == []
        assert result.avg_cancellation_rate == 0
        assert result.avg_delay_rate == 0

    @pytest.mark.asyncio
    async def test_get_station_trends_with_hourly_granularity(
        self, sample_stop, sample_trend_rows
    ):
        """Test get_station_trends returns hourly trend data."""
        session_mock = MagicMock()
        trend_result = MagicMock()
        trend_result.all.return_value = sample_trend_rows

        async def async_execute(stmt):
            return trend_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        result = await service.get_station_trends(
            sample_stop.stop_id, granularity="hourly"
        )

        assert result is not None
        assert result.granularity == "hourly"
        assert len(result.data_points) == 2
        assert result.data_points[0].total_departures == 40
        assert result.data_points[1].total_departures == 60

    @pytest.mark.asyncio
    async def test_get_station_trends_with_daily_granularity(self, sample_stop):
        """Test get_station_trends accepts daily granularity."""
        now = datetime.now(timezone.utc)
        trend_rows = [
            FakeTrendRow(
                bucket=now - timedelta(days=1),
                total_departures=500,
                cancelled_count=25,
                delayed_count=50,
            )
        ]

        session_mock = MagicMock()
        trend_result = MagicMock()
        trend_result.all.return_value = trend_rows

        async def async_execute(stmt):
            return trend_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        result = await service.get_station_trends(
            sample_stop.stop_id, granularity="daily"
        )

        assert result is not None
        assert result.granularity == "daily"
        assert len(result.data_points) == 1

    @pytest.mark.asyncio
    async def test_get_station_trends_calculates_averages(
        self, sample_stop, sample_trend_rows
    ):
        """Test get_station_trends calculates average rates correctly."""
        session_mock = MagicMock()
        trend_result = MagicMock()
        trend_result.all.return_value = sample_trend_rows

        async def async_execute(stmt):
            return trend_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        result = await service.get_station_trends(sample_stop.stop_id)

        assert result is not None
        # Point 1: 2/40 = 0.05, Point 2: 3/60 = 0.05 -> avg = 0.05
        assert result.avg_cancellation_rate == 0.05
        # Peak is max(0.05, 0.05) = 0.05
        assert result.peak_cancellation_rate == 0.05

    @pytest.mark.asyncio
    async def test_get_network_averages_returns_zeros_when_no_data(self, sample_stop):
        """Test _get_network_averages returns zeros when no data."""
        session_mock = MagicMock()
        network_result = MagicMock()
        network_result.one_or_none.return_value = None

        async def async_execute(stmt):
            return network_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        from_time = datetime.now(timezone.utc) - timedelta(hours=24)
        to_time = datetime.now(timezone.utc)

        result = await service._get_network_averages(
            time_range="24h",
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=60,
        )

        assert result["cancellation_rate"] == 0.0
        assert result["delay_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_network_averages_calculates_rates(self, sample_stop):
        """Test _get_network_averages calculates rates correctly."""
        session_mock = MagicMock()
        network_result = MagicMock()
        network_result.one_or_none.return_value = FakeNetworkRow(
            total=1000, cancelled=100, delayed=200
        )

        async def async_execute(stmt):
            return network_result

        session_mock.execute = async_execute

        gtfs_schedule = FakeGTFSScheduleService(stop_info=sample_stop)
        service = StationStatsService(session_mock, gtfs_schedule)

        from_time = datetime.now(timezone.utc) - timedelta(hours=24)
        to_time = datetime.now(timezone.utc)

        result = await service._get_network_averages(
            time_range="24h",
            from_time=from_time,
            to_time=to_time,
            bucket_width_minutes=60,
        )

        assert result["cancellation_rate"] == 0.1  # 100/1000
        assert result["delay_rate"] == 0.2  # 200/1000
