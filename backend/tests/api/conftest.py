from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.cache import CacheService
from app.services.mvg_client import (
    Departure,
    MVGClient,
    MVGServiceError,
    RouteLeg,
    RoutePlan,
    RouteNotFoundError,
    RouteStop,
    Station,
    StationNotFoundError,
)


@dataclass
class CacheScenario:
    """Configuration for fake cache behavior."""

    fresh_value: dict[str, Any] | None = None
    stale_value: dict[str, Any] | None = None
    should_timeout: bool = False
    recorded_sets: list[tuple[str, dict[str, Any], int | None, int | None]] | None = None


class FakeCacheService:
    """Lightweight fake CacheService for testing."""

    def __init__(self) -> None:
        self._cache: dict[str, CacheScenario] = {}
        self.recorded_sets: list[tuple[str, dict[str, Any], int | None, int | None]] = []
        self._lock_timeout = False

    def configure(self, key: str, scenario: CacheScenario) -> None:
        """Set up cache behavior for a specific key."""
        self._cache[key] = scenario
        if scenario.recorded_sets is not None:
            self.recorded_sets = scenario.recorded_sets

    def set_lock_timeout(self, enabled: bool) -> None:
        """Control whether single_flight raises TimeoutError."""
        self._lock_timeout = enabled

    async def get_json(self, key: str) -> dict[str, Any] | None:
        """Return fresh cached value if configured."""
        scenario = self._cache.get(key)
        if scenario is None:
            return None
        return scenario.fresh_value

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        """Return stale cached value if configured."""
        scenario = self._cache.get(key)
        if scenario is None:
            return None
        return scenario.stale_value

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        stale_ttl_seconds: int | None = None,
    ) -> None:
        """Record the set operation."""
        self.recorded_sets.append((key, value, ttl_seconds, stale_ttl_seconds))

    @asynccontextmanager
    async def single_flight(
        self,
        key: str,
        ttl_seconds: int,
        wait_timeout: float,
        retry_delay: float,
    ) -> AsyncIterator[None]:
        """Simulate single-flight lock behavior."""
        if self._lock_timeout:
            raise TimeoutError(f"Timed out while acquiring cache lock for key '{key}'.")
        yield


@dataclass
class MVGClientScenario:
    """Configuration for fake MVG client behavior."""

    fail_departures: bool = False
    fail_station_search: bool = False
    fail_route: bool = False
    not_found_station: bool = False
    not_found_route: bool = False
    departures_result: tuple[Station, list[Departure]] | None = None
    station_search_result: list[Station] | None = None
    route_result: tuple[Station, Station, list[RoutePlan]] | None = None


class FakeMVGClient:
    """Fake MVG client for testing endpoint error paths."""

    def __init__(self) -> None:
        self.scenario = MVGClientScenario()
        self.call_count_departures = 0
        self.call_count_station_search = 0
        self.call_count_route = 0

    def configure(self, scenario: MVGClientScenario) -> None:
        """Set up MVG client behavior."""
        self.scenario = scenario

    async def get_station(self, query: str) -> Station:
        """Minimal station lookup implementation."""
        if self.scenario.not_found_station:
            raise StationNotFoundError(f"Station not found for query '{query}'.")
        return Station(
            id="de:09162:6",
            name="Marienplatz",
            place="München",
            latitude=48.137,
            longitude=11.575,
        )

    async def get_departures(
        self,
        station_query: str,
        limit: int = 10,
        offset: int = 0,
        transport_types: Any = None,
    ) -> tuple[Station, list[Departure]]:
        """Return configured departures or raise error."""
        self.call_count_departures += 1
        if self.scenario.fail_departures:
            raise MVGServiceError("Failed to retrieve departures from MVG.")
        if self.scenario.not_found_station:
            raise StationNotFoundError(f"Station not found for query '{station_query}'.")
        if self.scenario.departures_result:
            return self.scenario.departures_result

        # Default successful response
        station = Station(
            id="de:09162:6",
            name="Marienplatz",
            place="München",
            latitude=48.137,
            longitude=11.575,
        )
        departures = [
            Departure(
                planned_time=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
                realtime_time=datetime(2025, 1, 15, 10, 2, tzinfo=timezone.utc),
                delay_minutes=2,
                platform="1",
                realtime=True,
                line="U3",
                destination="Fürstenried West",
                transport_type="UBAHN",
                icon="mdi-subway",
                cancelled=False,
                messages=[],
            )
        ]
        return station, departures

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        """Return configured station search results or raise error."""
        self.call_count_station_search += 1
        if self.scenario.fail_station_search:
            raise MVGServiceError("Failed to search MVG stations.")
        if self.scenario.station_search_result is not None:
            return self.scenario.station_search_result

        # Default successful response
        return [
            Station(
                id="de:09162:6",
                name="Marienplatz",
                place="München",
                latitude=48.137,
                longitude=11.575,
            )
        ]

    async def plan_route(
        self,
        origin_query: str,
        destination_query: str,
        departure_time: datetime | None = None,
        arrival_time: datetime | None = None,
        transport_types: Any = None,
    ) -> tuple[Station, Station, list[RoutePlan]]:
        """Return configured route or raise error."""
        self.call_count_route += 1
        if self.scenario.fail_route:
            raise MVGServiceError("Failed to retrieve route information from MVG.")
        if self.scenario.not_found_route:
            raise RouteNotFoundError(
                f"No MVG routes available between '{origin_query}' and '{destination_query}'."
            )
        if self.scenario.route_result:
            return self.scenario.route_result

        # Default successful response
        origin = Station(
            id="de:09162:6",
            name="Marienplatz",
            place="München",
            latitude=48.137,
            longitude=11.575,
        )
        destination = Station(
            id="de:09162:70",
            name="Hauptbahnhof",
            place="München",
            latitude=48.140,
            longitude=11.558,
        )
        departure_stop = RouteStop(
            id="de:09162:6",
            name="Marienplatz",
            place="München",
            latitude=48.137,
            longitude=11.575,
            planned_time=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            realtime_time=datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc),
            platform="1",
            transport_type="UBAHN",
            line="U4",
            destination="Westendstraße",
            delay_minutes=0,
            messages=[],
        )
        arrival_stop = RouteStop(
            id="de:09162:70",
            name="Hauptbahnhof",
            place="München",
            latitude=48.140,
            longitude=11.558,
            planned_time=datetime(2025, 1, 15, 10, 10, tzinfo=timezone.utc),
            realtime_time=datetime(2025, 1, 15, 10, 10, tzinfo=timezone.utc),
            platform="2",
            transport_type="UBAHN",
            line="U4",
            destination="Westendstraße",
            delay_minutes=0,
            messages=[],
        )
        leg = RouteLeg(
            origin=departure_stop,
            destination=arrival_stop,
            transport_type="UBAHN",
            line="U4",
            direction="Westendstraße",
            duration_minutes=10,
            distance_meters=2000,
            intermediate_stops=[],
        )
        plan = RoutePlan(
            duration_minutes=10,
            transfers=0,
            departure=departure_stop,
            arrival=arrival_stop,
            legs=[leg],
        )
        return origin, destination, [plan]


@pytest.fixture
def fake_cache() -> FakeCacheService:
    """Provide a fake cache service instance."""
    return FakeCacheService()


@pytest.fixture
def fake_mvg_client() -> FakeMVGClient:
    """Provide a fake MVG client instance."""
    return FakeMVGClient()


@pytest.fixture
def api_client(fake_cache: FakeCacheService, fake_mvg_client: FakeMVGClient) -> TestClient:
    """Provide a TestClient with dependency overrides."""
    app = create_app()

    # Override dependencies
    app.dependency_overrides[CacheService] = lambda: fake_cache

    # Import the actual dependencies to override them
    from app.api.v1.endpoints.mvg import get_cache_service, get_client

    app.dependency_overrides[get_cache_service] = lambda: fake_cache
    app.dependency_overrides[get_client] = lambda: fake_mvg_client

    client = TestClient(app)

    yield client

    # Clean up overrides
    app.dependency_overrides.clear()
