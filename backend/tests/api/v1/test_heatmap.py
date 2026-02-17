"""
Tests for the heatmap endpoint.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.shared.constants import RATE_LIMIT_HEATMAP_CANCELLATIONS
from app.api.v1.shared.rate_limit import limiter
from app.models.heatmap import HeatmapOverviewResponse, HeatmapResponse
from app.services.heatmap_cache import (
    heatmap_cancellations_cache_key,
    heatmap_live_snapshot_cache_key,
    heatmap_overview_cache_key,
)
from app.services.heatmap_service import resolve_max_points
from tests.api.conftest import CacheScenario


@contextmanager
def _heatmap_test_client(fake_cache, fake_gtfs_schedule):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoints import heatmap as heatmap_endpoint
    from tests.api.conftest import FakeAsyncSession

    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(heatmap_endpoint.router, prefix="/api/v1/heatmap")
    app.dependency_overrides[heatmap_endpoint.get_cache_service] = lambda: fake_cache
    app.dependency_overrides[heatmap_endpoint.get_gtfs_schedule] = lambda: (
        fake_gtfs_schedule
    )
    app.dependency_overrides[heatmap_endpoint.get_session] = lambda: FakeAsyncSession()

    original_enabled = limiter.enabled
    limiter.enabled = False

    try:
        with TestClient(app) as client:
            yield client
    finally:
        limiter.enabled = original_enabled
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_heatmap_rate_limit_state():
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


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


def test_heatmap_cancellations_lock_timeout_returns_503(api_client, fake_cache):
    """Lock timeouts should surface as retriable 503 errors."""
    fake_cache.set_lock_timeout(True)

    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 503
    assert response.headers.get("X-Cache-Status") == "miss-timeout"


def test_heatmap_cancellations_cache_write_failure_sets_header(
    api_client, fake_cache, monkeypatch
):
    """Write failures after fresh generation should be reflected in cache headers."""

    async def _failing_set_json(*_args, **_kwargs):
        raise RuntimeError("cache write failed")

    monkeypatch.setattr(fake_cache, "set_json", _failing_set_json)
    response = api_client.get("/api/v1/heatmap/cancellations")

    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "miss-write-failed"


def test_heatmap_cancellations_http_exception_passthrough(
    fake_cache, fake_gtfs_schedule, monkeypatch
):
    """Heatmap endpoint should not mask HTTPException raised during generation."""
    from fastapi import HTTPException
    from app.api.v1.endpoints import heatmap as heatmap_endpoint

    async def _raise_http(self, *_args, **_kwargs):
        raise HTTPException(status_code=418, detail="teapot")

    monkeypatch.setattr(
        heatmap_endpoint.HeatmapService,
        "get_cancellation_heatmap",
        _raise_http,
    )

    with _heatmap_test_client(fake_cache, fake_gtfs_schedule) as client:
        response = client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 418
    assert response.json()["detail"] == "teapot"


def test_heatmap_cancellations_invalid_cache_payload_falls_back_to_fresh_data(
    api_client, fake_cache, fake_gtfs_schedule
):
    """Malformed cache payload should be treated as cache miss with fresh generation."""
    max_points = resolve_max_points(zoom_level=10, max_points=None)
    fake_cache.configure(
        heatmap_cancellations_cache_key(
            time_range="24h",
            transport_modes=None,
            bucket_width_minutes=60,
            max_points=max_points,
        ),
        CacheScenario(fresh_value={"bad": "payload"}),
    )

    response = api_client.get("/api/v1/heatmap/cancellations")
    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "miss"


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


def test_heatmap_live_malformed_cache_payload_treated_as_miss(api_client, fake_cache):
    """Malformed live cache payload should be treated as a cache miss."""
    fake_cache.configure(
        heatmap_live_snapshot_cache_key(),
        CacheScenario(fresh_value={"bad": "payload"}),
    )

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


def test_heatmap_overview_http_exception_passthrough(
    fake_cache, fake_gtfs_schedule, monkeypatch
):
    """Overview endpoint should not mask HTTPException raised during generation."""
    from fastapi import HTTPException
    from app.api.v1.endpoints import heatmap as heatmap_endpoint

    async def _raise_http(self, *_args, **_kwargs):
        raise HTTPException(status_code=418, detail="teapot")

    monkeypatch.setattr(
        heatmap_endpoint.HeatmapService,
        "get_heatmap_overview",
        _raise_http,
    )

    with _heatmap_test_client(fake_cache, fake_gtfs_schedule) as client:
        response = client.get("/api/v1/heatmap/overview")
    assert response.status_code == 418
    assert response.json()["detail"] == "teapot"


def test_heatmap_overview_lock_timeout_returns_503(api_client, fake_cache):
    """Overview misses should also honor single-flight lock timeouts."""
    fake_cache.set_lock_timeout(True)

    response = api_client.get("/api/v1/heatmap/overview")
    assert response.status_code == 503
    assert response.headers.get("X-Cache-Status") == "miss-timeout"


def test_heatmap_overview_lock_timeout_returns_cached_response(
    fake_cache, fake_gtfs_schedule, monkeypatch
):
    """Lock timeouts should return a cached response if another worker filled it."""
    cache_key = heatmap_overview_cache_key(
        time_range=None,
        transport_modes=None,
        bucket_width_minutes=60,
        metrics="both",
    )
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

    cache_reads = 0
    original_get_json = fake_cache.get_json

    async def _get_json(key: str):
        nonlocal cache_reads
        if key == cache_key:
            cache_reads += 1
            return cached_payload if cache_reads > 1 else None
        return await original_get_json(key)

    monkeypatch.setattr(fake_cache, "get_json", _get_json)
    fake_cache.set_lock_timeout(True)

    with _heatmap_test_client(fake_cache, fake_gtfs_schedule) as client:
        response = client.get("/api/v1/heatmap/overview")

    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "hit"
    assert cache_reads == 2


def test_heatmap_overview_cache_write_failure_sets_header(
    api_client, fake_cache, monkeypatch
):
    """Overview responses should expose cache write failures in headers."""

    async def _failing_set_json(*_args, **_kwargs):
        raise RuntimeError("cache write failed")

    monkeypatch.setattr(fake_cache, "set_json", _failing_set_json)
    response = api_client.get("/api/v1/heatmap/overview")

    assert response.status_code == 200
    assert response.headers.get("X-Cache-Status") == "miss-write-failed"


@pytest.mark.asyncio
async def test_refresh_task_registry_deduplicates_per_cache_key():
    """Refresh registry should only allow one in-flight task per key."""
    from app.api.v1.endpoints import heatmap as heatmap_endpoint

    cache_key = "heatmap:refresh:dedupe"

    try:
        assert await heatmap_endpoint._try_mark_refresh_in_flight(cache_key) is True
        assert await heatmap_endpoint._try_mark_refresh_in_flight(cache_key) is False
    finally:
        await heatmap_endpoint._clear_refresh_in_flight(cache_key)

    assert await heatmap_endpoint._try_mark_refresh_in_flight(cache_key) is True
    await heatmap_endpoint._clear_refresh_in_flight(cache_key)


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


def test_heatmap_cancellations_rate_limited(api_client):
    """Cancellations endpoint should enforce configured per-minute rate limit."""
    app = api_client.app
    original_enabled = limiter.enabled
    had_limiter_state = hasattr(app.state, "limiter")
    original_state_limiter = getattr(app.state, "limiter", None)
    original_handler = app.exception_handlers.get(RateLimitExceeded)

    limiter.enabled = True
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    try:
        limiter.reset()
        limit = RATE_LIMIT_HEATMAP_CANCELLATIONS.per_minute
        for _ in range(limit):
            response = api_client.get("/api/v1/heatmap/cancellations")
            assert response.status_code == 200

        response = api_client.get("/api/v1/heatmap/cancellations")
        assert response.status_code == 429
    finally:
        limiter.enabled = original_enabled
        limiter.reset()
        if had_limiter_state:
            app.state.limiter = original_state_limiter
        elif hasattr(app.state, "limiter"):
            delattr(app.state, "limiter")

        if original_handler is None:
            app.exception_handlers.pop(RateLimitExceeded, None)
        else:
            app.exception_handlers[RateLimitExceeded] = original_handler


class TestDailyAggregationEndpoint:
    """Tests for the daily aggregation endpoint."""

    def test_trigger_daily_aggregation_requires_admin_auth(
        self, api_client, monkeypatch
    ):
        """Endpoint should reject unauthenticated callers when admin key is configured."""
        monkeypatch.setattr(
            "app.api.v1.shared.dependencies.get_settings",
            lambda: SimpleNamespace(admin_api_key="secret-token"),
        )

        response = api_client.post("/api/v1/heatmap/aggregate-daily")
        assert response.status_code == 401

    def test_trigger_daily_aggregation_rejects_invalid_admin_key(
        self, api_client, monkeypatch
    ):
        monkeypatch.setattr(
            "app.api.v1.shared.dependencies.get_settings",
            lambda: SimpleNamespace(admin_api_key="secret-token"),
        )

        response = api_client.post(
            "/api/v1/heatmap/aggregate-daily",
            headers={"X-API-Key": "wrong-token"},
        )
        assert response.status_code == 403

    def test_trigger_daily_aggregation_queues_background_task_when_authorized(
        self, api_client, monkeypatch
    ):
        """Test that the aggregation endpoint queues a background task."""
        monkeypatch.setattr(
            "app.api.v1.shared.dependencies.get_settings",
            lambda: SimpleNamespace(admin_api_key="secret-token"),
        )
        response = api_client.post(
            "/api/v1/heatmap/aggregate-daily",
            headers={"X-API-Key": "secret-token"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Background-Task") == "queued"

        data = response.json()
        assert data["status"] == "queued"
        assert "message" in data

    def test_trigger_daily_aggregation_response_structure(
        self, api_client, monkeypatch
    ):
        """Test that the aggregation endpoint returns expected structure."""
        monkeypatch.setattr(
            "app.api.v1.shared.dependencies.get_settings",
            lambda: SimpleNamespace(admin_api_key="secret-token"),
        )
        response = api_client.post(
            "/api/v1/heatmap/aggregate-daily",
            headers={"X-API-Key": "secret-token"},
        )

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
