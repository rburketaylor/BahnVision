"""
Tests for the heatmap endpoint.
"""

from __future__ import annotations

from app.models.heatmap import HeatmapOverviewResponse, HeatmapResponse
from app.services.heatmap_cache import (
    heatmap_cancellations_cache_key,
    heatmap_live_snapshot_cache_key,
    heatmap_overview_cache_key,
)
from app.services.heatmap_service import resolve_max_points
from tests.api.conftest import CacheScenario


def test_heatmap_cancellations_cache_hit(api_client, fake_cache):
    """Test heatmap endpoint with cache hit scenario."""
    cached_payload = {
        "time_range": {
            "from": "2025-01-15T00:00:00Z",
            "to": "2025-01-16T00:00:00Z",
        },
        "data_points": [
            {
                "station_id": "de:09162:6",
                "station_name": "Marienplatz",
                "latitude": 48.137,
                "longitude": 11.575,
                "total_departures": 1250,
                "cancelled_count": 45,
                "cancellation_rate": 0.036,
                "by_transport": {
                    "UBAHN": {"total": 500, "cancelled": 20},
                    "SBAHN": {"total": 750, "cancelled": 25},
                },
            }
        ],
        "summary": {
            "total_stations": 1,
            "total_departures": 1250,
            "total_cancellations": 45,
            "overall_cancellation_rate": 0.036,
            "most_affected_station": "Marienplatz",
            "most_affected_line": "U-Bahn",
        },
    }

    # Configure cache to return cached payload
    # Cache key includes: time_range, transport_modes, bucket_width, max_points (effective density)
    max_points = resolve_max_points(zoom_level=10, max_points=None)
    fake_cache.configure(
        heatmap_cancellations_cache_key(
            time_range="24h",
            transport_modes=None,
            bucket_width_minutes=60,
            max_points=max_points,
        ),
        CacheScenario(fresh_value=cached_payload),
    )

    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "hit"

    # Validate response structure
    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    assert len(validated.data_points) == 1
    assert validated.data_points[0].station_name == "Marienplatz"
    assert validated.summary.total_stations == 1


def test_heatmap_cancellations_cache_miss(api_client, fake_cache, fake_gtfs_schedule):
    """Test heatmap endpoint with cache miss and fresh fetch."""
    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "miss"

    # Validate response structure (empty since fake session returns no data)
    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    # Fake session returns empty results, so data_points will be empty
    assert validated.summary.total_stations == 0


def test_heatmap_live_cache_hit(api_client, fake_cache):
    """Test live heatmap endpoint with cache hit scenario."""
    cached_payload = {
        "time_range": {
            "from": "2025-01-15T00:00:00Z",
            "to": "2025-01-15T00:05:00Z",
        },
        "last_updated_at": "2025-01-15T00:05:00Z",
        "data_points": [
            {
                "station_id": "de:09162:6",
                "station_name": "Marienplatz",
                "latitude": 48.137,
                "longitude": 11.575,
                "total_departures": 10,
                "cancelled_count": 1,
                "cancellation_rate": 0.1,
                "delayed_count": 0,
                "delay_rate": 0.0,
                "by_transport": {
                    "UBAHN": {"total": 10, "cancelled": 1, "delayed": 0},
                },
            }
        ],
        "summary": {
            "total_stations": 1,
            "total_departures": 10,
            "total_cancellations": 1,
            "overall_cancellation_rate": 0.1,
            "total_delays": 0,
            "overall_delay_rate": 0.0,
            "most_affected_station": "Marienplatz",
            "most_affected_line": "U-Bahn",
        },
    }

    fake_cache.configure(
        heatmap_live_snapshot_cache_key(),
        CacheScenario(fresh_value=cached_payload),
    )

    response = api_client.get("/api/v1/heatmap/cancellations?time_range=live")
    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "hit"

    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    assert validated.last_updated_at is not None
    assert len(validated.data_points) == 1


def test_heatmap_live_cache_miss_returns_503(api_client, fake_cache):
    """Test live heatmap endpoint returns 503 when snapshot is missing."""
    response = api_client.get("/api/v1/heatmap/cancellations?time_range=live")
    assert response.status_code == 503
    assert response.headers.get("X-Cache-Status") == "miss"


def test_heatmap_live_transport_filter(api_client, fake_cache):
    """Test live heatmap endpoint filters by transport modes."""
    cached_payload = {
        "time_range": {
            "from": "2025-01-15T00:00:00Z",
            "to": "2025-01-15T00:05:00Z",
        },
        "last_updated_at": "2025-01-15T00:05:00Z",
        "data_points": [
            {
                "station_id": "de:09162:6",
                "station_name": "Marienplatz",
                "latitude": 48.137,
                "longitude": 11.575,
                "total_departures": 12,
                "cancelled_count": 2,
                "cancellation_rate": 0.166,
                "delayed_count": 1,
                "delay_rate": 0.083,
                "by_transport": {
                    "UBAHN": {"total": 5, "cancelled": 2, "delayed": 0},
                    "BUS": {"total": 7, "cancelled": 0, "delayed": 1},
                },
            }
        ],
        "summary": {
            "total_stations": 1,
            "total_departures": 12,
            "total_cancellations": 2,
            "overall_cancellation_rate": 0.166,
            "total_delays": 1,
            "overall_delay_rate": 0.083,
            "most_affected_station": "Marienplatz",
            "most_affected_line": "U-Bahn",
        },
    }

    fake_cache.configure(
        heatmap_live_snapshot_cache_key(),
        CacheScenario(fresh_value=cached_payload),
    )

    response = api_client.get(
        "/api/v1/heatmap/cancellations?time_range=live&transport_modes=UBAHN"
    )
    assert response.status_code == 200
    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    assert validated.summary.total_departures == 5
    assert validated.data_points[0].cancelled_count == 2


def test_heatmap_overview_live_transport_filter(api_client, fake_cache):
    """Test live heatmap overview endpoint filters by transport modes."""
    cached_payload = {
        "time_range": {
            "from": "2025-01-15T00:00:00Z",
            "to": "2025-01-15T00:05:00Z",
        },
        "last_updated_at": "2025-01-15T00:05:00Z",
        "data_points": [
            {
                "station_id": "de:09162:6",
                "station_name": "Marienplatz",
                "latitude": 48.137,
                "longitude": 11.575,
                "total_departures": 12,
                "cancelled_count": 2,
                "cancellation_rate": 0.166,
                "delayed_count": 1,
                "delay_rate": 0.083,
                "by_transport": {
                    "UBAHN": {"total": 5, "cancelled": 2, "delayed": 0},
                    "BUS": {"total": 7, "cancelled": 0, "delayed": 1},
                },
            }
        ],
        "summary": {
            "total_stations": 1,
            "total_departures": 12,
            "total_cancellations": 2,
            "overall_cancellation_rate": 0.166,
            "total_delays": 1,
            "overall_delay_rate": 0.083,
            "most_affected_station": "Marienplatz",
            "most_affected_line": "U-Bahn",
        },
    }

    fake_cache.configure(
        heatmap_live_snapshot_cache_key(),
        CacheScenario(fresh_value=cached_payload),
    )

    response = api_client.get(
        "/api/v1/heatmap/overview?time_range=live&transport_modes=UBAHN"
    )
    assert response.status_code == 200
    data = response.json()
    validated = HeatmapOverviewResponse.model_validate(data)
    assert validated.summary.total_departures == 5
    assert validated.total_impacted_stations == 1
    assert validated.last_updated_at is not None


def test_heatmap_overview_cache_key_normalizes_transport_modes(api_client, fake_cache):
    """Semantically equivalent transport_modes should share a cache key."""
    cached_payload = {
        "time_range": {"from": "2025-01-01T00:00:00Z", "to": "2025-01-01T01:00:00Z"},
        "points": [],
        "summary": {
            "total_stations": 1,
            "total_departures": 10,
            "total_cancellations": 1,
            "overall_cancellation_rate": 0.1,
            "total_delays": 0,
            "overall_delay_rate": 0.0,
            "most_affected_station": None,
            "most_affected_line": None,
        },
        "total_impacted_stations": 0,
    }
    fake_cache.configure(
        heatmap_overview_cache_key(
            time_range=None,
            transport_modes="BUS,UBAHN",
            bucket_width_minutes=60,
            metrics="both",
        ),
        CacheScenario(fresh_value=cached_payload),
    )

    response = api_client.get("/api/v1/heatmap/overview?transport_modes= ubahn , bus ")
    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "hit"


def test_heatmap_cancellations_with_time_range(
    api_client, fake_cache, fake_gtfs_schedule
):
    """Test heatmap endpoint with different time ranges."""
    for time_range in ["1h", "6h", "24h", "7d"]:
        response = api_client.get(
            f"/api/v1/heatmap/cancellations?time_range={time_range}"
        )
        assert response.status_code == 200, f"Failed for time_range={time_range}"

        data = response.json()
        validated = HeatmapResponse.model_validate(data)
        assert validated.time_range is not None


def test_heatmap_cancellations_with_transport_filter(
    api_client, fake_cache, fake_gtfs_schedule
):
    """Test heatmap endpoint with transport mode filtering."""
    response = api_client.get(
        "/api/v1/heatmap/cancellations?transport_modes=UBAHN,SBAHN"
    )
    assert response.status_code == 200

    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    assert validated.summary is not None


def test_heatmap_cancellations_invalid_time_range(api_client):
    """Test heatmap endpoint with invalid time range."""
    response = api_client.get("/api/v1/heatmap/cancellations?time_range=invalid")
    assert response.status_code == 422


def test_heatmap_cancellations_invalid_bucket_width(api_client):
    """Test heatmap endpoint with invalid bucket width."""
    # Too small
    response = api_client.get("/api/v1/heatmap/cancellations?bucket_width=5")
    assert response.status_code == 422

    # Too large
    response = api_client.get("/api/v1/heatmap/cancellations?bucket_width=2000")
    assert response.status_code == 422


def test_heatmap_cancellations_response_structure(
    api_client, fake_cache, fake_gtfs_schedule
):
    """Test that heatmap response has correct structure."""
    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 200

    data = response.json()

    # Check top-level keys
    assert "time_range" in data
    assert "data_points" in data
    assert "summary" in data

    # Check time_range structure
    assert "from" in data["time_range"]
    assert "to" in data["time_range"]

    # Check summary structure
    summary = data["summary"]
    assert "total_stations" in summary
    assert "total_departures" in summary
    assert "total_cancellations" in summary
    assert "overall_cancellation_rate" in summary

    # Check data_point structure if any exist
    if len(data["data_points"]) > 0:
        point = data["data_points"][0]
        assert "station_id" in point
        assert "station_name" in point
        assert "latitude" in point
        assert "longitude" in point
        assert "total_departures" in point
        assert "cancelled_count" in point
        assert "cancellation_rate" in point
        assert "by_transport" in point


def test_heatmap_cancellations_stop_list_failure(
    api_client, fake_cache, fake_gtfs_schedule
):
    """Test heatmap endpoint handles stop list failure gracefully."""
    fake_gtfs_schedule.scenario.fail_stop_list = True

    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 200

    # Should return empty data on failure
    data = response.json()
    validated = HeatmapResponse.model_validate(data)
    assert validated.summary.total_stations == 0
    assert len(validated.data_points) == 0


class TestDailyAggregationEndpoint:
    """Tests for the daily aggregation endpoint."""

    def test_trigger_daily_aggregation_queues_background_task(self, api_client):
        """Test that the aggregation endpoint queues a background task."""
        response = api_client.post("/api/v1/heatmap/aggregate-daily")

        assert response.status_code == 200
        assert response.headers.get("X-Background-Task") == "queued"

        data = response.json()
        assert data["status"] == "queued"
        assert "message" in data

    def test_trigger_daily_aggregation_response_structure(self, api_client):
        """Test that the aggregation endpoint returns expected structure."""
        response = api_client.post("/api/v1/heatmap/aggregate-daily")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "message" in data
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)


def test_heatmap_health_returns_503_on_dependency_failure(api_client, monkeypatch):
    """Health endpoint should return 503 when DB dependency check fails."""

    class _FailingSessionContext:
        async def __aenter__(self):
            raise RuntimeError("db unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.api.v1.endpoints.heatmap.AsyncSessionFactory",
        lambda: _FailingSessionContext(),
    )

    response = api_client.get("/api/v1/heatmap/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
