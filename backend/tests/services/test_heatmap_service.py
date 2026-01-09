"""
Tests for the heatmap service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pytest

from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapResponse,
    TransportStats,
)
from app.services.heatmap_service import (
    HeatmapService,
    parse_time_range,
    parse_transport_modes,
)


class FakeCache:
    """Fake cache for testing."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        pass


class FakeResult:
    """Fake SQLAlchemy result for testing."""

    def __init__(self, rows: list[object]):
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeAsyncSession:
    """Fake async database session for testing."""

    def __init__(
        self,
        rows: list[object] | None = None,
        row_sets: list[list[object]] | None = None,
        raise_on_execute: Exception | None = None,
    ):
        self._rows = rows or []
        self._row_sets = row_sets
        self._row_set_index = 0
        self._raise_on_execute = raise_on_execute
        self.executed_statements: list[object] = []

    async def execute(self, stmt) -> FakeResult:
        self.executed_statements.append(stmt)
        if self._raise_on_execute:
            raise self._raise_on_execute
        if self._row_sets is not None:
            if self._row_set_index >= len(self._row_sets):
                return FakeResult([])
            rows = self._row_sets[self._row_set_index]
            self._row_set_index += 1
            return FakeResult(rows)
        return FakeResult(self._rows)


@dataclass
class FakeGTFSStop:
    """Fake GTFS stop for testing."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    location_type: int = 0
    parent_station: Optional[str] = None


class FakeGTFSScheduleService:
    """Fake GTFS schedule service for testing."""

    def __init__(self, stops: list[FakeGTFSStop] | None = None):
        self.stops = stops or []
        self.fail_stops = False

    async def get_all_stops(self, limit: int = 10000) -> List[FakeGTFSStop]:
        if self.fail_stops:
            raise Exception("Stop list unavailable")
        return self.stops[:limit]


@pytest.fixture
def sample_stops() -> list[FakeGTFSStop]:
    """Sample stops for testing."""
    return [
        FakeGTFSStop(
            stop_id="de:09162:6",
            stop_name="Marienplatz",
            stop_lat=48.13743,
            stop_lon=11.57549,
        ),
        FakeGTFSStop(
            stop_id="de:09162:1",
            stop_name="Hauptbahnhof",
            stop_lat=48.140,
            stop_lon=11.558,
        ),
        FakeGTFSStop(
            stop_id="de:09162:10",
            stop_name="Sendlinger Tor",
            stop_lat=48.134,
            stop_lon=11.567,
        ),
    ]


@pytest.fixture
def fake_session_empty() -> FakeAsyncSession:
    """Fake session that returns no rows."""
    return FakeAsyncSession()


class TestParseTimeRange:
    """Tests for parse_time_range function."""

    def test_parse_time_range_1h(self):
        """Test 1 hour time range."""
        from_time, to_time = parse_time_range("1h")
        delta = to_time - from_time
        assert abs(delta.total_seconds() - 3600) < 1

    def test_parse_time_range_6h(self):
        """Test 6 hour time range."""
        from_time, to_time = parse_time_range("6h")
        delta = to_time - from_time
        assert abs(delta.total_seconds() - 6 * 3600) < 1

    def test_parse_time_range_24h(self):
        """Test 24 hour time range."""
        from_time, to_time = parse_time_range("24h")
        delta = to_time - from_time
        assert abs(delta.total_seconds() - 24 * 3600) < 1

    def test_parse_time_range_7d(self):
        """Test 7 day time range."""
        from_time, to_time = parse_time_range("7d")
        delta = to_time - from_time
        assert abs(delta.total_seconds() - 7 * 24 * 3600) < 1

    def test_parse_time_range_30d(self):
        """Test 30 day time range."""
        from_time, to_time = parse_time_range("30d")
        delta = to_time - from_time
        assert abs(delta.total_seconds() - 30 * 24 * 3600) < 1

    def test_parse_time_range_default(self):
        """Test default time range."""
        from_time, to_time = parse_time_range(None)
        delta = to_time - from_time
        # Default is 24h
        assert abs(delta.total_seconds() - 24 * 3600) < 1


class TestParseTransportModes:
    """Tests for parse_transport_modes function."""

    def test_parse_single_mode(self):
        """Test parsing a single transport mode."""
        modes = parse_transport_modes("UBAHN")
        assert modes is not None
        assert len(modes) == 1
        assert modes[0] == "UBAHN"

    def test_parse_multiple_modes(self):
        """Test parsing multiple transport modes."""
        modes = parse_transport_modes("UBAHN,SBAHN,BUS")
        assert modes is not None
        assert len(modes) == 3

    def test_parse_modes_with_spaces(self):
        """Test parsing modes with whitespace."""
        modes = parse_transport_modes("UBAHN, SBAHN, BUS")
        assert modes is not None
        assert len(modes) == 3

    def test_parse_none(self):
        """Test parsing None returns None."""
        modes = parse_transport_modes(None)
        assert modes is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        modes = parse_transport_modes("")
        assert modes is None

    def test_parse_invalid_mode_ignored(self):
        """Test that invalid modes are ignored."""
        modes = parse_transport_modes("UBAHN,INVALID,SBAHN")
        assert modes is not None
        assert len(modes) == 2

    def test_parse_alias_sbahn(self):
        """Test S-Bahn alias parsing."""
        modes = parse_transport_modes("S-BAHN")
        assert modes is not None
        assert len(modes) == 1
        assert modes[0] == "SBAHN"


class TestHeatmapService:
    """Tests for HeatmapService."""

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_basic(
        self, sample_stops, fake_session_empty
    ):
        """Test basic heatmap generation returns empty when DB has no rows."""
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache, session=fake_session_empty)

        result = await service.get_cancellation_heatmap()

        assert isinstance(result, HeatmapResponse)
        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_with_time_range(
        self, sample_stops, fake_session_empty
    ):
        """Test heatmap with specific time range."""
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache, session=fake_session_empty)

        result = await service.get_cancellation_heatmap(time_range="1h")

        assert result.time_range is not None
        delta = result.time_range.to_time - result.time_range.from_time
        assert abs(delta.total_seconds() - 3600) < 1

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_empty_stops(self, fake_session_empty):
        """Test heatmap with no rows and no stops."""
        gtfs_schedule = FakeGTFSScheduleService(stops=[])
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache, session=fake_session_empty)

        result = await service.get_cancellation_heatmap()

        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0
        assert result.summary.overall_cancellation_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_without_session_raises(self):
        """Test heatmap fails without a database session."""
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        with pytest.raises(RuntimeError, match="database session"):
            await service.get_cancellation_heatmap()

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_db_error_raises(self):
        """Test heatmap fails when the database query fails."""
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        session = FakeAsyncSession(raise_on_execute=RuntimeError("db down"))
        service = HeatmapService(gtfs_schedule, cache, session=session)

        with pytest.raises(RuntimeError, match="db down"):
            await service.get_cancellation_heatmap()

    def test_data_point_structure(self):
        """Test that HeatmapDataPoint has correct structure."""
        point = HeatmapDataPoint(
            station_id="de:09162:6",
            station_name="Marienplatz",
            latitude=48.137,
            longitude=11.575,
            total_departures=100,
            cancelled_count=5,
            cancellation_rate=0.05,
            delayed_count=10,
            delay_rate=0.10,
            by_transport={},
        )

        assert isinstance(point.station_id, str)
        assert isinstance(point.station_name, str)
        assert isinstance(point.latitude, float)
        assert isinstance(point.longitude, float)
        assert isinstance(point.total_departures, int)
        assert isinstance(point.cancelled_count, int)
        assert isinstance(point.cancellation_rate, float)
        assert 0 <= point.cancellation_rate <= 1

    @pytest.mark.asyncio
    async def test_summary_statistics_empty_without_db(
        self, sample_stops, fake_session_empty
    ):
        """Test that summary statistics are empty when DB has no rows."""
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache, session=fake_session_empty)

        result = await service.get_cancellation_heatmap()

        assert result.summary.total_departures == 0
        assert result.summary.total_cancellations == 0
        assert result.summary.overall_cancellation_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_fetches_breakdown_for_selected_stations(
        self,
    ):
        """Ensure service fetches route_type breakdown only for selected stations."""

        @dataclass
        class StationAggRow:
            stop_id: str
            stop_name: str
            stop_lat: float
            stop_lon: float
            total_departures: int
            cancelled_count: int
            delayed_count: int
            impact_score: int = 0

        @dataclass
        class BreakdownRow:
            stop_id: str
            route_type: int
            total_departures: int
            cancelled_count: int
            delayed_count: int

        @dataclass
        class TotalsRow:
            total_stations: int
            total_departures: int
            total_cancellations: int
            total_delays: int

        @dataclass
        class LineRow:
            route_type: int
            total_departures: int
            cancelled_count: int
            delayed_count: int

        station_rows = [
            StationAggRow(
                stop_id="de:09162:6",
                stop_name="Marienplatz",
                stop_lat=48.13743,
                stop_lon=11.57549,
                total_departures=100,
                cancelled_count=5,
                delayed_count=10,
                impact_score=15,
            )
        ]
        breakdown_rows = [
            BreakdownRow(
                stop_id="de:09162:6",
                route_type=2,
                total_departures=100,
                cancelled_count=5,
                delayed_count=10,
            )
        ]

        totals_rows = [
            TotalsRow(
                total_stations=1,
                total_departures=100,
                total_cancellations=5,
                total_delays=10,
            )
        ]
        line_rows = [
            LineRow(
                route_type=2,
                total_departures=100,
                cancelled_count=5,
                delayed_count=10,
            )
        ]

        session = FakeAsyncSession(
            row_sets=[station_rows, breakdown_rows, totals_rows, line_rows]
        )
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache, session=session)

        result = await service.get_cancellation_heatmap(max_points=1)

        assert len(session.executed_statements) == 4
        assert len(result.data_points) == 1
        assert result.data_points[0].station_id == "de:09162:6"
        assert result.data_points[0].by_transport["BAHN"].total == 100
        assert result.data_points[0].by_transport["BAHN"].cancelled == 5
        assert result.data_points[0].by_transport["BAHN"].delayed == 10


class TestCalculateSummary:
    """Tests for summary calculation."""

    def test_calculate_summary_empty(self):
        """Test summary calculation with empty data."""
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        summary = service._calculate_summary([])

        assert summary.total_stations == 0
        assert summary.total_departures == 0
        assert summary.total_cancellations == 0
        assert summary.overall_cancellation_rate == 0.0
        assert summary.most_affected_station is None
        assert summary.most_affected_line is None

    def test_calculate_summary_single_station(self):
        """Test summary calculation with single station."""
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        data_points = [
            HeatmapDataPoint(
                station_id="de:09162:6",
                station_name="Marienplatz",
                latitude=48.137,
                longitude=11.575,
                total_departures=100,
                cancelled_count=5,
                cancellation_rate=0.05,
                by_transport={
                    "UBAHN": TransportStats(total=100, cancelled=5),
                },
            )
        ]

        summary = service._calculate_summary(data_points)

        assert summary.total_stations == 1
        assert summary.total_departures == 100
        assert summary.total_cancellations == 5
        assert summary.overall_cancellation_rate == 0.05

    def test_calculate_summary_multiple_stations(self):
        """Test summary calculation with multiple stations."""
        gtfs_schedule = FakeGTFSScheduleService()
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        data_points = [
            HeatmapDataPoint(
                station_id="de:09162:6",
                station_name="Marienplatz",
                latitude=48.137,
                longitude=11.575,
                total_departures=100,
                cancelled_count=10,
                cancellation_rate=0.10,
                by_transport={
                    "UBAHN": TransportStats(total=100, cancelled=10),
                },
            ),
            HeatmapDataPoint(
                station_id="de:09162:1",
                station_name="Hauptbahnhof",
                latitude=48.140,
                longitude=11.558,
                total_departures=200,
                cancelled_count=4,
                cancellation_rate=0.02,
                by_transport={
                    "SBAHN": TransportStats(total=200, cancelled=4),
                },
            ),
        ]

        summary = service._calculate_summary(data_points)

        assert summary.total_stations == 2
        assert summary.total_departures == 300
        assert summary.total_cancellations == 14
        assert abs(summary.overall_cancellation_rate - 14 / 300) < 0.001
        # Marienplatz has higher cancellation rate
        assert summary.most_affected_station == "Marienplatz"
