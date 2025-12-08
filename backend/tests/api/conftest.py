from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.dependencies import get_station_repository
from app.persistence.repositories import StationPayload
from app.services.cache import CacheService, get_cache_service
from app.api.v1.endpoints.heatmap import get_gtfs_schedule


@dataclass
class CacheScenario:
    """Configuration for fake cache behavior."""

    fresh_value: dict[str, Any] | None = None
    stale_value: dict[str, Any] | None = None
    should_timeout: bool = False
    recorded_sets: list[tuple[str, dict[str, Any], int | None, int | None]] | None = (
        None
    )


class FakeCacheService:
    """Lightweight fake CacheService for testing."""

    def __init__(self) -> None:
        self._cache: dict[str, CacheScenario] = {}
        self.recorded_sets: list[tuple[str, dict[str, Any], int | None, int | None]] = (
            []
        )
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
            raise TimeoutError("Timed out acquiring cache lock for key")
        yield


@dataclass
class FakeStationRecord:
    station_id: str
    name: str
    place: str
    latitude: float
    longitude: float


class FakeStationRepository:
    def __init__(self) -> None:
        self._records: dict[str, FakeStationRecord] = {}
        self.upsert_batches: list[list[StationPayload]] = []

    async def get_all_stations(self) -> list[FakeStationRecord]:
        return list(self._records.values())

    async def upsert_stations(
        self, payloads: list[StationPayload]
    ) -> list[FakeStationRecord]:
        self.upsert_batches.append(payloads)
        for payload in payloads:
            self._records[payload.station_id] = FakeStationRecord(
                station_id=payload.station_id,
                name=payload.name,
                place=payload.place,
                latitude=payload.latitude,
                longitude=payload.longitude,
            )
        return list(self._records.values())


@pytest.fixture
def fake_cache() -> FakeCacheService:
    return FakeCacheService()


@pytest.fixture
def fake_station_repository() -> FakeStationRepository:
    return FakeStationRepository()


@dataclass
class FakeGTFSStop:
    """Fake GTFS stop for testing."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    location_type: int = 0
    parent_station: Optional[str] = None


@dataclass
class GTFSScheduleScenario:
    """Configuration for fake GTFS schedule service behavior."""

    fail_stop_list: bool = False


class FakeGTFSScheduleService:
    """Fake GTFS schedule service for heatmap testing."""

    def __init__(self) -> None:
        self.scenario = GTFSScheduleScenario()
        self.stops: list[FakeGTFSStop] = [
            FakeGTFSStop(
                stop_id="de:09162:6",
                stop_name="Marienplatz",
                stop_lat=48.137,
                stop_lon=11.575,
            ),
            FakeGTFSStop(
                stop_id="de:09162:70",
                stop_name="Hauptbahnhof",
                stop_lat=48.140,
                stop_lon=11.558,
            ),
        ]

    async def get_all_stops(self, limit: int = 10000) -> List[FakeGTFSStop]:
        if self.scenario.fail_stop_list:
            raise Exception("Failed to fetch stop list")
        return self.stops[:limit]


@pytest.fixture
def fake_gtfs_schedule() -> FakeGTFSScheduleService:
    return FakeGTFSScheduleService()


@pytest.fixture
def api_client(
    fake_cache: FakeCacheService,
    fake_station_repository: FakeStationRepository,
    fake_gtfs_schedule: FakeGTFSScheduleService,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[CacheService] = lambda: fake_cache
    app.dependency_overrides[get_cache_service] = lambda: fake_cache
    app.dependency_overrides[get_station_repository] = lambda: fake_station_repository
    app.dependency_overrides[get_gtfs_schedule] = lambda: fake_gtfs_schedule
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
