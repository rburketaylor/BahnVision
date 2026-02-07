"""Tests for the departures endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.transit.departures import (
    router,
    _departure_info_to_response,
    get_transit_data_service,
)
from app.services.transit_data import DepartureInfo, StopInfo, ScheduleRelationship


@dataclass
class MockServiceAlert:
    """Mock service alert."""

    header_text: str


class TestDepartureInfoToResponse:
    """Tests for _departure_info_to_response converter."""

    def test_converts_departure_info_to_response(self):
        """Test basic conversion."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="S-Bahn Line 1",
            trip_headsign="Erding",
            stop_id="de:09162:6",
            stop_name="München Hbf",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
        )

        result = _departure_info_to_response(dep)

        assert result.trip_id == "trip1"
        assert result.route_short_name == "S1"
        assert result.stop_id == "de:09162:6"
        assert result.headsign == "Erding"

    def test_converts_alerts_from_objects(self):
        """Test that alert objects are converted to strings."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="S-Bahn Line 1",
            trip_headsign="Erding",
            stop_id="de:09162:6",
            stop_name="München Hbf",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            alerts=[MockServiceAlert(header_text="Delay expected")],
        )

        result = _departure_info_to_response(dep)

        assert len(result.alerts) == 1
        assert result.alerts[0] == "Delay expected"

    def test_converts_string_alerts(self):
        """Test that string alerts pass through."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="S-Bahn Line 1",
            trip_headsign="Erding",
            stop_id="de:09162:6",
            stop_name="München Hbf",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            alerts=["String alert"],
        )

        result = _departure_info_to_response(dep)

        assert len(result.alerts) == 1
        assert result.alerts[0] == "String alert"

    def test_handles_realtime_data(self):
        """Test conversion with real-time data."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="S-Bahn Line 1",
            trip_headsign="Erding",
            stop_id="de:09162:6",
            stop_name="München Hbf",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            real_time_departure=datetime(2025, 12, 8, 8, 35, tzinfo=timezone.utc),
            departure_delay_seconds=300,
            schedule_relationship=ScheduleRelationship.SCHEDULED,
        )

        result = _departure_info_to_response(dep)

        assert result.departure_delay_seconds == 300
        assert result.realtime_departure == datetime(
            2025, 12, 8, 8, 35, tzinfo=timezone.utc
        )
        assert result.schedule_relationship == "SCHEDULED"


class FakeTransitDataService:
    """Fake transit data service for testing."""

    def __init__(self):
        self.stop_info = StopInfo(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.140,
            stop_lon=11.558,
        )
        self.departures = [
            DepartureInfo(
                trip_id="trip1",
                route_id="route1",
                route_short_name="S1",
                route_long_name="S-Bahn Line 1",
                trip_headsign="Erding",
                stop_id="de:09162:6",
                stop_name="München Hbf",
                scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            )
        ]
        self._realtime_available = True

    async def get_stop_info(self, stop_id: str):
        if stop_id == "nonexistent":
            return None
        return self.stop_info

    async def get_departures_for_stop(
        self,
        stop_id: str,
        limit: int = 10,
        offset_minutes: int = 0,
        from_time: datetime | None = None,
        include_real_time: bool = True,
    ):
        return self.departures

    def is_realtime_available(self):
        return self._realtime_available


@pytest.fixture
def departures_client():
    """Create test client for departures endpoint."""
    from contextlib import asynccontextmanager

    from app.api.v1.shared.rate_limit import limiter

    @asynccontextmanager
    async def null_lifespan(app: FastAPI):
        yield {}

    app = FastAPI(lifespan=null_lifespan)
    app.include_router(router, prefix="/api/v1/transit")

    fake_service = FakeTransitDataService()

    app.dependency_overrides[get_transit_data_service] = lambda: fake_service

    # Disable rate limiting for tests (avoids Valkey connection requirement)
    original_enabled = limiter.enabled
    limiter.enabled = False

    yield TestClient(app), fake_service

    # Restore original state
    limiter.enabled = original_enabled
    app.dependency_overrides.clear()


class TestDeparturesEndpoint:
    """Tests for /departures endpoint."""

    def test_get_departures_success(self, departures_client):
        """Test successful departures retrieval."""
        client, _ = departures_client

        response = client.get("/api/v1/transit/departures?stop_id=de:09162:6")

        assert response.status_code == 200
        data = response.json()
        assert data["stop"]["id"] == "de:09162:6"
        assert len(data["departures"]) == 1

    def test_get_departures_not_found(self, departures_client):
        """Test departures for nonexistent stop."""
        client, _ = departures_client

        response = client.get("/api/v1/transit/departures?stop_id=nonexistent")

        assert response.status_code == 404

    def test_get_departures_with_limit(self, departures_client):
        """Test departures with limit parameter."""
        client, _ = departures_client

        response = client.get("/api/v1/transit/departures?stop_id=de:09162:6&limit=5")

        assert response.status_code == 200

    def test_get_departures_with_offset(self, departures_client):
        """Test departures with offset_minutes parameter."""
        client, _ = departures_client

        response = client.get(
            "/api/v1/transit/departures?stop_id=de:09162:6&offset_minutes=30"
        )

        assert response.status_code == 200

    def test_get_departures_with_from_time(self, departures_client):
        """Test departures with absolute from_time parameter."""
        client, _ = departures_client

        response = client.get(
            "/api/v1/transit/departures?stop_id=de:09162:6&from_time=2025-01-01T12:00:00Z"
        )

        assert response.status_code == 200

    def test_get_departures_realtime_available(self, departures_client):
        """Test realtime_available field in response."""
        client, fake_service = departures_client
        fake_service._realtime_available = True

        response = client.get("/api/v1/transit/departures?stop_id=de:09162:6")

        assert response.status_code == 200
        data = response.json()
        assert data["realtime_available"] is True

    def test_get_departures_realtime_disabled(self, departures_client):
        """Test realtime_available when disabled."""
        client, fake_service = departures_client
        fake_service._realtime_available = False

        response = client.get(
            "/api/v1/transit/departures?stop_id=de:09162:6&include_realtime=false"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["realtime_available"] is False
