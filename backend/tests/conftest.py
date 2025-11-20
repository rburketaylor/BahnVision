from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.cache import get_cache_service  # noqa: E402
from app.api.v1.endpoints.mvg.shared.utils import get_client  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.cache import CacheService  # noqa: E402
from app.services.mvg_client import (  # noqa: E402
    Departure,
    MVGServiceError,
    RouteLeg,
    RoutePlan,
    RouteStop,
    Station,
)


class FakeValkey:
    """In-memory Valkey replacement used for tests."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}
        self.should_fail = False

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [
            key
            for key, (_, expires_at) in self._store.items()
            if expires_at is not None and expires_at <= now
        ]
        for key in expired:
            self._store.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        record = self._store.get(key)
        if record is None:
            return None
        value, _ = record
        return value

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool | None = None,
    ) -> bool:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        if nx:
            # Only set when key does not exist.
            if key in self._store:
                return False
        expires_at = time.monotonic() + ex if ex else None
        self._store[key] = (value, expires_at)
        return True

    async def delete(self, *keys: str) -> None:
        self._prune()
        if self.should_fail:
            raise RuntimeError("valkey unavailable")
        for key in keys:
            self._store.pop(key, None)


class FakeMVGClient:
    """Test double for MVG client interactions."""

    def __init__(self) -> None:
        self.departure_calls = 0
        self.route_calls = 0
        self.station_list_calls = 0
        self.fail_departures = False
        self.fail_routes = False
        self.fail_station_list = False
        self.fail_departures_for: set[str] = set()
        self.last_departures_call: dict = {}

    async def get_departures(
        self,
        station_query: str,
        limit: int = 10,
        offset: int = 0,
        transport_types=None,
    ) -> tuple[Station, list[Departure]]:
        self.departure_calls += 1

        # Track call arguments for testing
        self.last_departures_call = {
            "station_query": station_query,
            "limit": limit,
            "offset": offset,
            "transport_types": transport_types,
        }

        if self.fail_departures:
            raise MVGServiceError("departures unavailable")
        types_list = list(transport_types) if transport_types else []
        if types_list:
            primary = types_list[0]
            if hasattr(primary, "name"):
                transport_name = str(primary.name)
            elif hasattr(primary, "value") and isinstance(primary.value, str):
                transport_name = primary.value
            else:
                transport_name = str(primary)
            if transport_name.upper() in self.fail_departures_for:
                raise MVGServiceError(f"departures unavailable for {transport_name}")

        station = Station(
            id=f"station:{station_query}",
            name=station_query.title(),
            place="München",
            latitude=48.13743,
            longitude=11.57549,
        )
        now = datetime.now(tz=timezone.utc)

        # Create mixed-mode departures for testing
        all_departures = [
            Departure(
                planned_time=now + timedelta(minutes=1),
                realtime_time=now + timedelta(minutes=2),
                delay_minutes=1,
                platform="1",
                realtime=True,
                line="U3",
                destination="Olympiazentrum",
                transport_type="UBAHN",
                icon=None,
                cancelled=False,
                messages=["Mind the gap"],
            ),
            Departure(
                planned_time=now + timedelta(minutes=3),
                realtime_time=now + timedelta(minutes=3),
                delay_minutes=0,
                platform="2",
                realtime=True,
                line="Bus 100",
                destination="Hauptbahnhof",
                transport_type="BUS",
                icon=None,
                cancelled=False,
                messages=[],
            ),
            Departure(
                planned_time=now + timedelta(minutes=5),
                realtime_time=now + timedelta(minutes=6),
                delay_minutes=1,
                platform="3",
                realtime=True,
                line="Tram 17",
                destination="Sendlinger Tor",
                transport_type="TRAM",
                icon=None,
                cancelled=False,
                messages=["Slight delay"],
            ),
            Departure(
                planned_time=now + timedelta(minutes=7),
                realtime_time=now + timedelta(minutes=7),
                delay_minutes=0,
                platform="4",
                realtime=True,
                line="U1",
                destination="Messestadt",
                transport_type="UBAHN",
                icon=None,
                cancelled=False,
                messages=[],
            ),
            Departure(
                planned_time=now + timedelta(minutes=9),
                realtime_time=now + timedelta(minutes=10),
                delay_minutes=1,
                platform="5",
                realtime=True,
                line="SBahn 8",
                destination="Flughafen",
                transport_type="SBAHN",
                icon=None,
                cancelled=False,
                messages=["Airport express"],
            ),
        ]

        # Check for failures in the requested transport types
        if transport_types:
            transport_type_names = {
                t.name if hasattr(t, "name") else str(t) for t in transport_types
            }
            for transport_name in transport_type_names:
                if transport_name.upper() in self.fail_departures_for:
                    raise MVGServiceError(
                        f"departures unavailable for {transport_name}"
                    )
            filtered_departures = [
                d for d in all_departures if d.transport_type in transport_type_names
            ]
        else:
            filtered_departures = all_departures

        # Apply limit
        departures_to_return = filtered_departures[:limit]

        return station, departures_to_return

    async def get_all_stations(self) -> list[Station]:
        self.station_list_calls += 1
        if self.fail_station_list:
            raise MVGServiceError("station list unavailable")
        return [
            Station(
                id="station:marienplatz",
                name="Marienplatz",
                place="München",
                latitude=48.13743,
                longitude=11.57549,
            ),
            Station(
                id="station:hauptbahnhof",
                name="Hauptbahnhof",
                place="München",
                latitude=48.140,
                longitude=11.558,
            ),
        ]

    async def search_stations(self, query: str, limit: int = 10) -> list[Station]:
        stations = await self.get_all_stations()
        query_lower = query.lower()
        matches: list[Station] = []
        for station in stations:
            if (
                query_lower in station.name.lower()
                or query_lower in station.place.lower()
            ):
                matches.append(station)
                if len(matches) >= limit:
                    break
        return matches

    async def plan_route(
        self,
        origin_query: str,
        destination_query: str,
        departure_time: datetime | None = None,
        arrival_time: datetime | None = None,
        transport_types=None,
    ) -> tuple[Station, Station, list[RoutePlan]]:
        self.route_calls += 1
        if self.fail_routes:
            raise MVGServiceError("route planning unavailable")
        origin = Station(
            id=f"station:{origin_query}",
            name=origin_query.title(),
            place="München",
            latitude=48.13743,
            longitude=11.57549,
        )
        destination = Station(
            id=f"station:{destination_query}",
            name=destination_query.title(),
            place="München",
            latitude=48.131,
            longitude=11.549,
        )
        now = datetime.now(tz=timezone.utc)
        leg_origin = RouteStop(
            id=origin.id,
            name=origin.name,
            place=origin.place,
            latitude=origin.latitude,
            longitude=origin.longitude,
            planned_time=now,
            realtime_time=now,
            platform="1",
            transport_type="UBAHN",
            line="U3",
            destination=destination.name,
            delay_minutes=0,
            messages=[],
        )
        leg_destination = RouteStop(
            id=destination.id,
            name=destination.name,
            place=destination.place,
            latitude=destination.latitude,
            longitude=destination.longitude,
            planned_time=now + timedelta(minutes=12),
            realtime_time=now + timedelta(minutes=12),
            platform="2",
            transport_type="UBAHN",
            line="U3",
            destination=destination.name,
            delay_minutes=0,
            messages=[],
        )
        leg = RouteLeg(
            origin=leg_origin,
            destination=leg_destination,
            transport_type="UBAHN",
            line="U3",
            direction=destination.name,
            duration_minutes=12,
            distance_meters=4300,
            intermediate_stops=[],
        )
        plan = RoutePlan(
            duration_minutes=12,
            transfers=0,
            departure=leg_origin,
            arrival=leg_destination,
            legs=[leg],
        )
        return origin, destination, [plan]


@pytest.fixture()
def fake_valkey() -> FakeValkey:
    return FakeValkey()


@pytest.fixture()
def cache_service(fake_valkey: FakeValkey) -> CacheService:
    return CacheService(fake_valkey)


@pytest.fixture()
def fake_mvg_client() -> FakeMVGClient:
    return FakeMVGClient()


@pytest.fixture()
def api_client(
    cache_service: CacheService, fake_mvg_client: FakeMVGClient
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_cache_service] = lambda: cache_service
    app.dependency_overrides[get_client] = lambda: fake_mvg_client
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
