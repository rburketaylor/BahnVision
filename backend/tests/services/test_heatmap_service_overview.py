"""Tests for HeatmapService.get_heatmap_overview method.

These tests verify the lightweight heatmap overview functionality
using the API endpoint integration tests approach since the service
requires a database session with proper fixtures.
"""

import pytest

from app.models.heatmap import HeatmapOverviewResponse, HeatmapPointLight


class TestHeatmapPointLightModel:
    """Unit tests for the HeatmapPointLight model."""

    def test_valid_point_creation(self):
        """Should create a valid lightweight point."""
        point = HeatmapPointLight(
            id="de:11000:900100001",
            lat=52.5219,
            lon=13.4115,
            i=0.15,
            n="Berlin Hbf",
        )

        assert point.id == "de:11000:900100001"
        assert point.lat == 52.5219
        assert point.lon == 13.4115
        assert point.i == 0.15
        assert point.n == "Berlin Hbf"

    def test_intensity_validation_min(self):
        """Intensity must be >= 0."""
        with pytest.raises(ValueError):
            HeatmapPointLight(
                id="test",
                lat=52.0,
                lon=13.0,
                i=-0.1,  # Invalid: below 0
                n="Test Station",
            )

    def test_intensity_validation_max(self):
        """Intensity must be <= 1."""
        with pytest.raises(ValueError):
            HeatmapPointLight(
                id="test",
                lat=52.0,
                lon=13.0,
                i=1.5,  # Invalid: above 1
                n="Test Station",
            )

    def test_intensity_at_boundaries(self):
        """Intensity at boundary values should be valid."""
        point_zero = HeatmapPointLight(
            id="test1", lat=52.0, lon=13.0, i=0.0, n="Zero intensity"
        )
        point_one = HeatmapPointLight(
            id="test2", lat=52.0, lon=13.0, i=1.0, n="Max intensity"
        )

        assert point_zero.i == 0.0
        assert point_one.i == 1.0

    def test_minimal_fields_only(self):
        """Point should only have the minimal required fields."""
        point = HeatmapPointLight(
            id="test",
            lat=52.0,
            lon=13.0,
            i=0.5,
            n="Test",
        )

        # Verify it has only the expected fields
        fields = set(point.model_fields.keys())
        expected_fields = {"id", "lat", "lon", "i", "n"}
        assert fields == expected_fields

        # Verify it does NOT have detailed fields
        assert not hasattr(point, "total_departures")
        assert not hasattr(point, "by_transport")
        assert not hasattr(point, "cancellation_rate")
        assert not hasattr(point, "delay_rate")


class TestHeatmapOverviewResponseModel:
    """Unit tests for the HeatmapOverviewResponse model."""

    def test_valid_response_creation(self):
        """Should create a valid overview response."""
        from datetime import datetime, timezone
        from app.models.heatmap import TimeRange, HeatmapSummary

        now = datetime.now(timezone.utc)
        response = HeatmapOverviewResponse(
            time_range=TimeRange.model_validate(
                {
                    "from": now,
                    "to": now,
                }
            ),
            points=[
                HeatmapPointLight(
                    id="test", lat=52.0, lon=13.0, i=0.5, n="Test Station"
                )
            ],
            summary=HeatmapSummary(
                total_stations=1,
                total_departures=100,
                total_cancellations=5,
                overall_cancellation_rate=0.05,
                total_delays=10,
                overall_delay_rate=0.1,
            ),
            total_impacted_stations=1,
        )

        assert len(response.points) == 1
        assert response.total_impacted_stations == 1

    def test_points_count_matches_total(self):
        """Points count should match total_impacted_stations when creating response."""
        from datetime import datetime, timezone
        from app.models.heatmap import TimeRange, HeatmapSummary

        now = datetime.now(timezone.utc)
        points = [
            HeatmapPointLight(
                id=f"test{i}", lat=52.0, lon=13.0, i=0.1 * i, n=f"Station {i}"
            )
            for i in range(1, 6)
        ]

        response = HeatmapOverviewResponse(
            time_range=TimeRange.model_validate({"from": now, "to": now}),
            points=points,
            summary=HeatmapSummary(
                total_stations=5,
                total_departures=500,
                total_cancellations=25,
                overall_cancellation_rate=0.05,
                total_delays=50,
                overall_delay_rate=0.1,
            ),
            total_impacted_stations=len(points),
        )

        assert len(response.points) == response.total_impacted_stations


class TestPickMostAffectedStationLight:
    """Unit tests for the _pick_most_affected_station_light helper."""

    def test_picks_highest_intensity(self):
        """Should pick the station with highest intensity."""
        from app.services.heatmap_service import _pick_most_affected_station_light

        points = [
            HeatmapPointLight(id="low", lat=52.0, lon=13.0, i=0.1, n="Low Impact"),
            HeatmapPointLight(id="high", lat=52.0, lon=13.0, i=0.9, n="High Impact"),
            HeatmapPointLight(id="mid", lat=52.0, lon=13.0, i=0.5, n="Medium Impact"),
        ]

        result = _pick_most_affected_station_light(points)
        assert result == "High Impact"

    def test_empty_list_returns_none(self):
        """Should return None for empty list."""
        from app.services.heatmap_service import _pick_most_affected_station_light

        result = _pick_most_affected_station_light([])
        assert result is None

    def test_single_station(self):
        """Should return the only station's name."""
        from app.services.heatmap_service import _pick_most_affected_station_light

        points = [
            HeatmapPointLight(id="only", lat=52.0, lon=13.0, i=0.5, n="Only Station"),
        ]

        result = _pick_most_affected_station_light(points)
        assert result == "Only Station"
