"""Unit tests for MVGClient data mapping and fan-out behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

import app.services.mvg_client as mvg_client_module
from app.services.mvg_mapping import (
    extract_routes,
    map_route_leg,
    map_route_plan,
    map_route_stop,
)
from app.services.mvg_client import (
    MVGClient,
    MVGServiceError,
    RouteLeg,
    RoutePlan,
    RouteStop,
    Station,
    StationNotFoundError,
    MvgApiError,
)


class DummyTransport(SimpleNamespace):
    """Simple transport type stub with a name attribute."""


@pytest.fixture(autouse=True)
def immediate_to_thread(monkeypatch):
    """Run asyncio.to_thread calls inline for deterministic tests."""

    async def _immediate(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(mvg_client_module.asyncio, "to_thread", _immediate)


@pytest.fixture
def station_payload() -> dict[str, Any]:
    """Base station payload reused across tests."""
    return {
        "id": "de:09162:5",
        "name": "Marienplatz",
        "place": "München",
        "latitude": 48.137154,
        "longitude": 11.576124,
    }


@pytest.mark.asyncio
async def test_get_station_success(monkeypatch, station_payload):
    """MVGClient.get_station maps successful lookups to Station dataclass."""

    class StubApi:
        @staticmethod
        def station(query: str) -> dict[str, Any]:
            assert query == "Marienplatz"
            return station_payload

    monkeypatch.setattr(mvg_client_module, "MvgApi", StubApi)

    client = MVGClient()
    station = await client.get_station("Marienplatz")

    assert station == Station(**station_payload)


@pytest.mark.asyncio
async def test_get_station_wraps_mvg_api_errors(monkeypatch):
    """MVG API errors are wrapped in MVGServiceError."""

    class FailingApi:
        @staticmethod
        def station(query: str) -> dict[str, Any]:
            raise MvgApiError("remote error")

    monkeypatch.setattr(mvg_client_module, "MvgApi", FailingApi)

    client = MVGClient()
    with pytest.raises(MVGServiceError):
        await client.get_station("Marienplatz")


@pytest.mark.asyncio
async def test_get_station_not_found(monkeypatch):
    """None responses raise StationNotFoundError."""

    class EmptyApi:
        @staticmethod
        def station(query: str) -> None:
            return None

    monkeypatch.setattr(mvg_client_module, "MvgApi", EmptyApi)

    client = MVGClient()
    with pytest.raises(StationNotFoundError):
        await client.get_station("Unknown Station")


def test_fetch_departures_returns_empty_on_bad_request(monkeypatch):
    """_fetch_departures suppresses MVG 400 errors and returns an empty list."""
    captured: dict[str, Any] = {}

    class DeparturesApi:
        def __init__(self, station_id: str) -> None:
            captured["station_id"] = station_id

        def departures(
            self,
            *,
            limit: int,
            offset: int,
            transport_types: list[Any] | None,
        ) -> list[dict[str, Any]]:
            captured["params"] = (limit, offset, transport_types)
            raise MvgApiError("400 Bad Request")

    monkeypatch.setattr(mvg_client_module, "MvgApi", DeparturesApi)

    result = MVGClient._fetch_departures("station-1", 5, 2, ["UBAHN"])

    assert result == []
    assert captured["station_id"] == "station-1"
    assert captured["params"] == (5, 2, ["UBAHN"])


def test_fetch_departures_re_raises_unexpected_errors(monkeypatch):
    """Non-400 errors bubble out of _fetch_departures."""

    class DeparturesApi:
        def __init__(self, station_id: str) -> None:
            self.station_id = station_id

        def departures(
            self,
            *,
            limit: int,
            offset: int,
            transport_types: list[Any] | None,
        ) -> list[dict[str, Any]]:
            raise MvgApiError("500 Internal Server Error")

    monkeypatch.setattr(mvg_client_module, "MvgApi", DeparturesApi)

    with pytest.raises(MvgApiError):
        MVGClient._fetch_departures("station-1", 5, 0, None)


@pytest.mark.asyncio
async def test_get_departures_without_filters(monkeypatch):
    """No transport filters call _fetch_departures once and map departures."""
    station = Station("station-1", "Marienplatz", "München", 48.1, 11.5)

    async def fake_get_station(self, query: str) -> Station:
        assert query == "Marienplatz"
        return station

    monkeypatch.setattr(MVGClient, "get_station", fake_get_station)

    captured: dict[str, Any] = {}

    def fake_fetch(station_id: str, limit: int, offset: int, transport_types: list[Any] | None):
        captured["args"] = (station_id, limit, offset, transport_types)
        return [
            {
                "planned": 1_700_000_000,
                "time": 1_700_000_060,
                "delay": 5,
                "line": "U3",
                "destination": "Moosach",
                "type": "UBAHN",
                "platform": "Gleis 1",
                "messages": ["crowded"],
            }
        ]

    monkeypatch.setattr(MVGClient, "_fetch_departures", staticmethod(fake_fetch))

    client = MVGClient()
    result_station, departures = await client.get_departures("Marienplatz", limit=5, offset=1)

    assert result_station == station
    assert captured["args"] == ("station-1", 5, 1, None)
    assert len(departures) == 1
    assert departures[0].line == "U3"
    assert departures[0].realtime_time == datetime.fromtimestamp(1_700_000_060, tz=timezone.utc)


@pytest.mark.asyncio
async def test_get_departures_with_filters_merges_and_limits(monkeypatch):
    """Fan-out per transport merges results, sorts, limits, and records metrics."""
    station = Station("station-1", "Marienplatz", "München", 48.1, 11.5)

    async def fake_get_station(self, query: str) -> Station:  # pragma: no cover - signature clarity
        return station

    monkeypatch.setattr(MVGClient, "get_station", fake_get_station)

    payloads = {
        "UBAHN": [
            {
                "planned": 1_700_000_500,
                "time": 1_700_000_560,
                "delay": 5,
                "line": "U3",
                "destination": "Later Train",
                "type": "UBAHN",
            }
        ],
        "BUS": [
            {
                "planned": 1_700_000_100,
                "time": 1_700_000_200,
                "delay": 10,
                "line": "54",
                "destination": "Earlier Bus",
                "type": "BUS",
            }
        ],
    }

    def fake_fetch(station_id: str, limit: int, offset: int, transport_types: list[Any] | None):
        transport_name = transport_types[0].name if transport_types else "ALL"
        return payloads[transport_name]

    monkeypatch.setattr(MVGClient, "_fetch_departures", staticmethod(fake_fetch))

    metrics: list[tuple[str, str, str]] = []

    def fake_record(endpoint: str, transport_type: str, result: str) -> None:
        metrics.append((endpoint, transport_type, result))

    monkeypatch.setattr(mvg_client_module, "record_mvg_transport_request", fake_record)

    client = MVGClient()
    ubahn = DummyTransport(name="UBAHN")
    bus = DummyTransport(name="BUS")

    _, departures = await client.get_departures(
        "Marienplatz",
        limit=1,
        transport_types=[ubahn, bus],
    )

    assert len(departures) == 1
    assert departures[0].destination == "Earlier Bus"
    assert metrics == [
        ("departures", "UBAHN", "success"),
        ("departures", "BUS", "success"),
    ]


@pytest.mark.asyncio
async def test_get_departures_failure_propagates(monkeypatch):
    """Any transport failure raises MVGServiceError and records failure metric."""
    station = Station("station-1", "Marienplatz", "München", 48.1, 11.5)

    async def fake_get_station(self, query: str) -> Station:
        return station

    monkeypatch.setattr(MVGClient, "get_station", fake_get_station)

    def fake_fetch(station_id: str, limit: int, offset: int, transport_types: list[Any] | None):
        transport_name = transport_types[0].name
        if transport_name == "UBAHN":
            raise MvgApiError("Request timed out")
        return [
            {
                "planned": 1_700_001_000,
                "time": 1_700_001_060,
                "delay": 10,
                "line": "54",
                "destination": "Later Bus",
                "type": "BUS",
            }
        ]

    monkeypatch.setattr(MVGClient, "_fetch_departures", staticmethod(fake_fetch))

    metrics: list[tuple[str, str, str]] = []

    def fake_record(endpoint: str, transport_type: str, result: str) -> None:
        metrics.append((endpoint, transport_type, result))

    monkeypatch.setattr(mvg_client_module, "record_mvg_transport_request", fake_record)

    client = MVGClient()
    ubahn = DummyTransport(name="UBAHN")
    bus = DummyTransport(name="BUS")

    with pytest.raises(MVGServiceError):
        await client.get_departures("Marienplatz", limit=5, transport_types=[ubahn, bus])

    assert metrics == [("departures", "UBAHN", "timeout")]


def test_extract_routes_handles_multiple_payload_shapes():
    """_extract_routes picks the correct list regardless of payload wrapping."""
    list_payload = [
        {"id": "route-1"},
        "invalid",
        None,
    ]
    dict_payload = {
        "connections": [
            {"id": "route-2"},
            [],
            None,
        ]
    }

    assert extract_routes(list_payload) == [{"id": "route-1"}]
    assert extract_routes(dict_payload) == [{"id": "route-2"}]
    assert extract_routes({"routes": [{"id": "route-3"}]}) == [{"id": "route-3"}]
    assert extract_routes(None) == []


def test_map_route_stop_handles_nested_station_fields():
    """map_route_stop maps nested station/line metadata and tolerates partial payloads."""
    raw_stop = {
        "station": {
            "id": "de:09162:5",
            "name": "Marienplatz",
            "place": "München",
            "latitude": "48.137154",
            "longitude": "11.576124",
        },
        "planned": 1_700_000_000,
        "time": 1_700_000_120,
        "platform": "Gleis 1",
        "line": {"label": "U3", "transportType": "UBAHN", "destination": "Moosach"},
        "messages": ["Delayed"],
        "delayInMinutes": 2,
    }
    stop = map_route_stop(raw_stop)
    assert isinstance(stop, RouteStop)
    assert stop.id == "de:09162:5"
    assert stop.name == "Marienplatz"
    assert stop.latitude == pytest.approx(48.137154)
    assert stop.transport_type == "UBAHN"
    assert stop.line == "U3"
    assert stop.destination == "Moosach"
    assert stop.delay_minutes == 2
    assert stop.messages == ["Delayed"]

    minimal_stop = {
        "stationId": "alternate",
        "name": "Alt",
        "place": "Munich",
        "plannedTime": 1_700_000_500,
    }
    assert map_route_stop(minimal_stop) is not None
    assert map_route_stop(None) is None


def test_map_route_leg_maps_transport_metadata():
    """map_route_leg builds RouteLeg with direction, duration, and intermediate stops."""
    raw_leg = {
        "origin": {
            "stationId": "start",
            "name": "Origin",
            "place": "Munich",
            "planned": 1_700_000_000,
            "time": 1_700_000_060,
        },
        "arrival": {
            "stop": {"id": "end", "name": "Destination", "place": "Munich"},
            "scheduledArrivalTime": 1_700_000_300,
            "arrivalTime": 1_700_000_360,
        },
        "line": {"name": "U3", "transportType": "UBAHN", "destination": "Moosach"},
        "duration": {"minutes": 5},
        "distanceInMeters": 1500,
        "intermediateStops": [
            {
                "station": {"id": "intermediate", "name": "Mid", "place": "Munich"},
                "planned": 1_700_000_150,
            },
            {},
        ],
    }

    leg = map_route_leg(raw_leg)
    assert isinstance(leg, RouteLeg)
    assert leg.transport_type == "UBAHN"
    assert leg.line == "U3"
    assert leg.direction == "Moosach"
    assert leg.duration_minutes == 5
    assert len(leg.intermediate_stops) == 1

    assert map_route_leg({}) is None


def test_map_route_plan_maps_duration_transfers_and_legs():
    """map_route_plan converts duration/transfers and nests mapped legs."""
    raw_plan = {
        "duration": {"minutes": 25},
        "changes": "2",
        "departure": {"stationId": "start", "name": "Origin"},
        "arrival": {"stationId": "end", "name": "Destination"},
        "legs": [
            {
                "departure": {"stationId": "start", "name": "Origin"},
                "arrival": {"stationId": "mid", "name": "Mid"},
                "line": {"symbol": "S1", "transportType": "SBAHN"},
                "duration": 10,
                "distance": {"meters": 1000},
            },
            {
                "origin": {"stationId": "mid", "name": "Mid"},
                "destination": {"stationId": "end", "name": "Destination"},
                "line": {"label": "U3", "transportType": "UBAHN"},
                "duration": {"minutes": 15},
                "distanceInMeters": 2000,
            },
        ],
    }

    plan = map_route_plan(raw_plan)
    assert isinstance(plan, RoutePlan)
    assert plan.duration_minutes == 25
    assert plan.transfers == 2
    assert isinstance(plan.departure, RouteStop)
    assert isinstance(plan.arrival, RouteStop)
    assert len(plan.legs) == 2
