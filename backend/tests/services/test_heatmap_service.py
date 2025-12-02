"""
Tests for the heatmap service.
"""

from __future__ import annotations

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
from app.services.mvg_dto import Station


class FakeCache:
    """Fake cache for testing."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        pass


class FakeMVGClient:
    """Fake MVG client for testing."""

    def __init__(self, stations: list[Station] | None = None):
        self.stations = stations or []
        self.fail_stations = False

    async def get_all_stations(self) -> list[Station]:
        if self.fail_stations:
            raise Exception("Station list unavailable")
        return self.stations


@pytest.fixture
def sample_stations() -> list[Station]:
    """Sample stations for testing."""
    return [
        Station(
            id="de:09162:6",
            name="Marienplatz",
            place="München",
            latitude=48.13743,
            longitude=11.57549,
        ),
        Station(
            id="de:09162:1",
            name="Hauptbahnhof",
            place="München",
            latitude=48.140,
            longitude=11.558,
        ),
        Station(
            id="de:09162:10",
            name="Sendlinger Tor",
            place="München",
            latitude=48.134,
            longitude=11.567,
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
        assert modes[0].name == "UBAHN"

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
        assert modes[0].name == "SBAHN"


class TestHeatmapService:
    """Tests for HeatmapService."""

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_basic(self, sample_stations):
        """Test basic heatmap generation."""
        client = FakeMVGClient(stations=sample_stations)
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap()

        assert isinstance(result, HeatmapResponse)
        assert len(result.data_points) > 0
        assert result.summary.total_stations > 0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_with_time_range(self, sample_stations):
        """Test heatmap with specific time range."""
        client = FakeMVGClient(stations=sample_stations)
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap(time_range="1h")

        assert result.time_range is not None
        delta = result.time_range.to_time - result.time_range.from_time
        assert abs(delta.total_seconds() - 3600) < 1

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_empty_stations(self):
        """Test heatmap with no stations."""
        client = FakeMVGClient(stations=[])
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap()

        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0
        assert result.summary.overall_cancellation_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_cancellation_heatmap_station_failure(self):
        """Test heatmap handles station fetch failure."""
        client = FakeMVGClient()
        client.fail_stations = True
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap()

        assert len(result.data_points) == 0
        assert result.summary.total_stations == 0

    @pytest.mark.asyncio
    async def test_data_point_structure(self, sample_stations):
        """Test that data points have correct structure."""
        client = FakeMVGClient(stations=sample_stations)
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap()

        for point in result.data_points:
            assert isinstance(point.station_id, str)
            assert isinstance(point.station_name, str)
            assert isinstance(point.latitude, float)
            assert isinstance(point.longitude, float)
            assert isinstance(point.total_departures, int)
            assert isinstance(point.cancelled_count, int)
            assert isinstance(point.cancellation_rate, float)
            assert 0 <= point.cancellation_rate <= 1

    @pytest.mark.asyncio
    async def test_summary_statistics(self, sample_stations):
        """Test that summary statistics are calculated correctly."""
        client = FakeMVGClient(stations=sample_stations)
        cache = FakeCache()
        service = HeatmapService(client, cache)

        result = await service.get_cancellation_heatmap()

        # Summary should aggregate data points
        total_deps = sum(p.total_departures for p in result.data_points)
        total_cancelled = sum(p.cancelled_count for p in result.data_points)

        assert result.summary.total_departures == total_deps
        assert result.summary.total_cancellations == total_cancelled

        if total_deps > 0:
            expected_rate = total_cancelled / total_deps
            assert abs(result.summary.overall_cancellation_rate - expected_rate) < 0.001


class TestCalculateSummary:
    """Tests for summary calculation."""

    def test_calculate_summary_empty(self):
        """Test summary calculation with empty data."""
        client = FakeMVGClient()
        cache = FakeCache()
        service = HeatmapService(client, cache)

        summary = service._calculate_summary([])

        assert summary.total_stations == 0
        assert summary.total_departures == 0
        assert summary.total_cancellations == 0
        assert summary.overall_cancellation_rate == 0.0
        assert summary.most_affected_station is None
        assert summary.most_affected_line is None

    def test_calculate_summary_single_station(self):
        """Test summary calculation with single station."""
        client = FakeMVGClient()
        cache = FakeCache()
        service = HeatmapService(client, cache)

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
        client = FakeMVGClient()
        cache = FakeCache()
        service = HeatmapService(client, cache)

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
