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
    async def test_get_cancellation_heatmap_basic(self, sample_stops):
        """Test basic heatmap generation returns empty without DB session.

        Without a database session, the service cannot query real data and
        returns empty results (no more simulated/fake data fallback).
        """
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        result = await service.get_cancellation_heatmap()

        assert isinstance(result, HeatmapResponse)
        # No DB session means no data points (no fake data fallback)
        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_with_time_range(self, sample_stops):
        """Test heatmap with specific time range."""
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        result = await service.get_cancellation_heatmap(time_range="1h")

        assert result.time_range is not None
        delta = result.time_range.to_time - result.time_range.from_time
        assert abs(delta.total_seconds() - 3600) < 1

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_empty_stops(self):
        """Test heatmap with no stops."""
        gtfs_schedule = FakeGTFSScheduleService(stops=[])
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        result = await service.get_cancellation_heatmap()

        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0
        assert result.summary.overall_cancellation_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_stop_failure(self):
        """Test heatmap handles stop fetch failure."""
        gtfs_schedule = FakeGTFSScheduleService()
        gtfs_schedule.fail_stops = True
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        result = await service.get_cancellation_heatmap()

        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0

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
    async def test_summary_statistics_empty_without_db(self, sample_stops):
        """Test that summary statistics are empty without DB session."""
        gtfs_schedule = FakeGTFSScheduleService(stops=sample_stops)
        cache = FakeCache()
        service = HeatmapService(gtfs_schedule, cache)

        result = await service.get_cancellation_heatmap()

        # Without DB session, no data is available
        assert result.summary.total_departures == 0
        assert result.summary.total_cancellations == 0
        assert result.summary.overall_cancellation_rate == 0.0


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
