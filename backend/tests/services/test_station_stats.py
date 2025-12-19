"""
Tests for station stats models.

Tests the StationStats and StationTrends Pydantic models.
"""

from datetime import datetime, timezone


from app.models.station_stats import (
    StationStats,
    StationTrends,
    TransportBreakdown,
    TrendDataPoint,
)


class TestStationStatsModels:
    """Tests for station stats Pydantic models."""

    def test_station_stats_model_creation(self):
        """Test StationStats model creation."""
        stats = StationStats(
            station_id="de:09162:1",
            station_name="München Hbf",
            time_range="24h",
            total_departures=1000,
            cancelled_count=50,
            cancellation_rate=0.05,
            delayed_count=200,
            delay_rate=0.2,
            by_transport=[],
            data_from=datetime.now(timezone.utc),
            data_to=datetime.now(timezone.utc),
        )

        assert stats.station_id == "de:09162:1"
        assert stats.station_name == "München Hbf"
        assert stats.cancellation_rate == 0.05
        assert stats.delay_rate == 0.2
        assert stats.performance_score is None
        assert stats.network_avg_cancellation_rate is None

    def test_station_stats_with_performance_score(self):
        """Test StationStats model with performance score."""
        stats = StationStats(
            station_id="de:09162:1",
            station_name="München Hbf",
            time_range="24h",
            total_departures=1000,
            cancelled_count=50,
            cancellation_rate=0.05,
            delayed_count=200,
            delay_rate=0.2,
            performance_score=85.5,
            network_avg_cancellation_rate=0.03,
            network_avg_delay_rate=0.15,
            by_transport=[],
            data_from=datetime.now(timezone.utc),
            data_to=datetime.now(timezone.utc),
        )

        assert stats.performance_score == 85.5
        assert stats.network_avg_cancellation_rate == 0.03

    def test_transport_breakdown_model(self):
        """Test TransportBreakdown model creation."""
        breakdown = TransportBreakdown(
            transport_type="rail",
            display_name="Rail",
            total_departures=500,
            cancelled_count=25,
            cancellation_rate=0.05,
            delayed_count=100,
            delay_rate=0.2,
        )

        assert breakdown.transport_type == "rail"
        assert breakdown.display_name == "Rail"
        assert breakdown.total_departures == 500
        assert breakdown.cancellation_rate == 0.05

    def test_station_stats_with_transport_breakdown(self):
        """Test StationStats with transport breakdown list."""
        breakdown = TransportBreakdown(
            transport_type="rail",
            display_name="Rail",
            total_departures=500,
            cancelled_count=25,
            cancellation_rate=0.05,
            delayed_count=100,
            delay_rate=0.2,
        )

        stats = StationStats(
            station_id="de:09162:1",
            station_name="München Hbf",
            time_range="24h",
            total_departures=1000,
            cancelled_count=50,
            cancellation_rate=0.05,
            delayed_count=200,
            delay_rate=0.2,
            by_transport=[breakdown],
            data_from=datetime.now(timezone.utc),
            data_to=datetime.now(timezone.utc),
        )

        assert len(stats.by_transport) == 1
        assert stats.by_transport[0].transport_type == "rail"

    def test_trend_data_point_model(self):
        """Test TrendDataPoint model creation."""
        point = TrendDataPoint(
            timestamp=datetime.now(timezone.utc),
            total_departures=50,
            cancelled_count=2,
            cancellation_rate=0.04,
            delayed_count=10,
            delay_rate=0.2,
        )

        assert point.total_departures == 50
        assert point.cancellation_rate == 0.04

    def test_station_trends_model(self):
        """Test StationTrends model creation."""
        point = TrendDataPoint(
            timestamp=datetime.now(timezone.utc),
            total_departures=50,
            cancelled_count=2,
            cancellation_rate=0.04,
            delayed_count=10,
            delay_rate=0.2,
        )

        trends = StationTrends(
            station_id="de:09162:1",
            station_name="München Hbf",
            time_range="24h",
            granularity="hourly",
            data_points=[point],
            avg_cancellation_rate=0.04,
            avg_delay_rate=0.2,
            peak_cancellation_rate=0.05,
            peak_delay_rate=0.25,
            data_from=datetime.now(timezone.utc),
            data_to=datetime.now(timezone.utc),
        )

        assert trends.station_id == "de:09162:1"
        assert trends.granularity == "hourly"
        assert len(trends.data_points) == 1
        assert trends.avg_cancellation_rate == 0.04

    def test_station_trends_empty_data_points(self):
        """Test StationTrends with empty data points."""
        trends = StationTrends(
            station_id="de:09162:1",
            station_name="München Hbf",
            time_range="24h",
            granularity="daily",
            data_points=[],
            avg_cancellation_rate=0,
            avg_delay_rate=0,
            peak_cancellation_rate=0,
            peak_delay_rate=0,
            data_from=datetime.now(timezone.utc),
            data_to=datetime.now(timezone.utc),
        )

        assert len(trends.data_points) == 0
        assert trends.granularity == "daily"
