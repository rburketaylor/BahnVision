"""
Unit tests for Transit API endpoints.

Tests the /api/v1/transit/* endpoints using mocked dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient

from app.services.cache import CacheService, get_cache_service
from app.api.v1.endpoints.transit.stops import get_transit_data_service
from tests.api.conftest import FakeCacheService


@dataclass
class FakeGTFSStop:
    """Fake GTFS stop for testing."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    location_type: int = 0
    parent_station: Optional[str] = None
    zone_id: Optional[str] = None
    wheelchair_boarding: int = 0


@dataclass
class FakeStopInfo:
    """Fake stop info for transit data service."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    zone_id: Optional[str] = None
    wheelchair_boarding: int = 0


class FakeTransitDataService:
    """Fake TransitDataService for transit endpoint testing."""

    def __init__(self) -> None:
        self.stops: list[FakeStopInfo] = [
            FakeStopInfo(
                stop_id="de:09162:6",
                stop_name="Marienplatz",
                stop_lat=48.137,
                stop_lon=11.575,
            ),
            FakeStopInfo(
                stop_id="de:09162:70",
                stop_name="Hauptbahnhof",
                stop_lat=48.140,
                stop_lon=11.558,
            ),
        ]
        self._stop_not_found = False

    async def search_stops(self, query: str, limit: int = 10) -> List[FakeStopInfo]:
        return [s for s in self.stops if query.lower() in s.stop_name.lower()][:limit]

    async def get_stop_info(self, stop_id: str) -> Optional[FakeStopInfo]:
        for stop in self.stops:
            if stop.stop_id == stop_id:
                return stop
        return None


@pytest.fixture
def fake_transit_data_service() -> FakeTransitDataService:
    return FakeTransitDataService()


@pytest.fixture
def fake_cache() -> FakeCacheService:
    return FakeCacheService()


@pytest.fixture
def transit_api_client(
    fake_cache: FakeCacheService,
    fake_transit_data_service: FakeTransitDataService,
) -> TestClient:
    """Create test client with transit dependencies mocked.

    We create the app without running the lifespan to avoid
    Valkey/database connection attempts during unit tests.
    """
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from app.api.routes import api_router
    from app.api.v1.shared.rate_limit import limiter

    # Create a minimal test app without the full lifespan
    @asynccontextmanager
    async def null_lifespan(app: FastAPI):
        yield {}

    test_app = FastAPI(lifespan=null_lifespan)
    test_app.include_router(api_router, prefix="/api/v1")

    # Override dependencies
    test_app.dependency_overrides[CacheService] = lambda: fake_cache
    test_app.dependency_overrides[get_cache_service] = lambda: fake_cache
    test_app.dependency_overrides[get_transit_data_service] = lambda: (
        fake_transit_data_service
    )

    # Disable rate limiting for tests (avoids Valkey connection requirement)
    original_enabled = limiter.enabled
    limiter.enabled = False

    client = TestClient(test_app)
    yield client

    # Restore original state
    limiter.enabled = original_enabled
    test_app.dependency_overrides.clear()


class TestTransitStopsSearchEndpoint:
    """Tests for /api/v1/transit/stops/search endpoint."""

    def test_transit_stops_search_endpoint_success(
        self, transit_api_client, fake_transit_data_service
    ):
        """Test successful stop search."""
        response = transit_api_client.get(
            "/api/v1/transit/stops/search?query=Marienplatz"
        )
        assert response.status_code == 200

        data = response.json()
        # Response should contain results
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "Marienplatz"

    def test_transit_stops_search_endpoint_empty_results(
        self, transit_api_client, fake_transit_data_service
    ):
        """Test stop search with no results."""
        response = transit_api_client.get(
            "/api/v1/transit/stops/search?query=NonexistentPlace"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) == 0

    def test_transit_stops_search_endpoint_with_limit(
        self, transit_api_client, fake_transit_data_service
    ):
        """Test stop search with limit parameter."""
        response = transit_api_client.get(
            "/api/v1/transit/stops/search?query=a&limit=1"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) <= 1


class TestTransitStopDetailsEndpoint:
    """Tests for /api/v1/transit/stops/{stop_id} endpoint."""

    def test_transit_stop_details_success(
        self, transit_api_client, fake_transit_data_service
    ):
        """Test successful stop details retrieval."""
        response = transit_api_client.get("/api/v1/transit/stops/de:09162:6")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "de:09162:6"
        assert data["name"] == "Marienplatz"
        assert "latitude" in data
        assert "longitude" in data

    def test_transit_stop_details_not_found(
        self, transit_api_client, fake_transit_data_service
    ):
        """Test stop details for non-existent stop."""
        response = transit_api_client.get("/api/v1/transit/stops/unknown_stop_id")
        assert response.status_code == 404


class TestTransitStopsSearchValidation:
    """Tests for input validation on search endpoint."""

    def test_transit_stops_search_empty_query(self, transit_api_client):
        """Test stop search with empty query."""
        response = transit_api_client.get("/api/v1/transit/stops/search?query=")
        # Should fail validation (min_length=1)
        assert response.status_code == 422

    def test_transit_stops_search_missing_query(self, transit_api_client):
        """Test stop search without query parameter."""
        response = transit_api_client.get("/api/v1/transit/stops/search")
        # Should fail validation (required parameter)
        assert response.status_code == 422

    def test_transit_stops_search_invalid_limit(self, transit_api_client):
        """Test stop search with invalid limit."""
        response = transit_api_client.get(
            "/api/v1/transit/stops/search?query=test&limit=0"
        )
        # Should fail validation (ge=1)
        assert response.status_code == 422

        response = transit_api_client.get(
            "/api/v1/transit/stops/search?query=test&limit=100"
        )
        # Should fail validation (le=50)
        assert response.status_code == 422
