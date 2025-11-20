"""Unit tests for mvg_mapping module."""

from datetime import datetime, timezone
from typing import Any


from app.services.mvg_dto import Departure, RouteLeg, RoutePlan, RouteStop, Station
from app.services.mvg_mapping import (
    DataMapper,
    extract_routes,
    map_departure,
    map_route_leg,
    map_route_plan,
    map_route_stop,
    map_station,
)


class TestDataMapper:
    """Tests for DataMapper utility class."""

    def test_safe_get_returns_first_match(self):
        data = {"a": 1, "b": 2}
        assert DataMapper.safe_get(data, "a", "b") == 1
        assert DataMapper.safe_get(data, "b", "a") == 2

    def test_safe_get_returns_default_on_miss(self):
        data = {"a": 1}
        assert DataMapper.safe_get(data, "c", default="default") == "default"

    def test_safe_get_handles_none_data(self):
        assert DataMapper.safe_get(None, "a", default="default") == "default"

    def test_safe_get_nested_returns_value(self):
        data = {"a": {"b": {"c": 1}}}
        assert DataMapper.safe_get_nested(data, ["a", "b", "c"]) == 1

    def test_safe_get_nested_handles_missing_keys(self):
        data = {"a": {"b": 1}}
        assert DataMapper.safe_get_nested(data, ["a", "c"]) is None

    def test_safe_get_nested_handles_none_data(self):
        assert DataMapper.safe_get_nested(None, ["a"]) is None

    def test_convert_type_int(self):
        assert DataMapper.convert_type("123", int) == 123
        assert DataMapper.convert_type(123.45, int) == 123
        assert DataMapper.convert_type(None, int) is None

    def test_convert_type_float(self):
        assert DataMapper.convert_type("123.45", float) == 123.45
        assert DataMapper.convert_type(123, float) == 123.0
        assert DataMapper.convert_type(None, float) is None

    def test_convert_type_datetime(self):
        ts = 1600000000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        assert DataMapper.convert_type(ts, datetime) == dt
        assert DataMapper.convert_type(str(ts), datetime) == dt
        assert DataMapper.convert_type(None, datetime) is None

    def test_convert_type_str(self):
        assert DataMapper.convert_type(123, str) == "123"
        assert DataMapper.convert_type(None, str) is None

    def test_convert_type_error_handling(self):
        assert DataMapper.convert_type("invalid", int) is None

    def test_extract_minutes(self):
        assert DataMapper.extract_minutes(10) == 10
        assert DataMapper.extract_minutes("10") == 10
        assert DataMapper.extract_minutes({"minutes": 10}) == 10
        assert DataMapper.extract_minutes({"duration": 10}) == 10
        assert DataMapper.extract_minutes(None) is None


def test_map_station():
    data = {
        "id": "station-1",
        "name": "Test Station",
        "place": "Munich",
        "latitude": 48.1,
        "longitude": 11.5,
    }
    station = map_station(data)
    assert isinstance(station, Station)
    assert station.id == "station-1"
    assert station.name == "Test Station"
    assert station.place == "Munich"
    assert station.latitude == 48.1
    assert station.longitude == 11.5


def test_map_departure():
    ts_planned = 1600000000
    ts_realtime = 1600000060
    data = {
        "planned": ts_planned,
        "time": ts_realtime,
        "delay": 1,
        "platform": "1",
        "realtime": True,
        "line": "U3",
        "destination": "Moosach",
        "type": "UBAHN",
        "icon": "subway",
        "cancelled": False,
        "messages": ["msg1"],
    }
    departure = map_departure(data)
    assert isinstance(departure, Departure)
    assert departure.planned_time == datetime.fromtimestamp(ts_planned, tz=timezone.utc)
    assert departure.realtime_time == datetime.fromtimestamp(
        ts_realtime, tz=timezone.utc
    )
    assert departure.delay_minutes == 1
    assert departure.platform == "1"
    assert departure.realtime is True
    assert departure.line == "U3"
    assert departure.destination == "Moosach"
    assert departure.transport_type == "UBAHN"
    assert departure.icon == "subway"
    assert departure.cancelled is False
    assert departure.messages == ["msg1"]


def test_map_departure_handles_missing_fields():
    data: dict[str, Any] = {}
    departure = map_departure(data)
    assert departure.delay_minutes == 0
    assert departure.cancelled is False
    assert departure.messages == []


def test_map_route_stop():
    ts = 1600000000
    data = {
        "station": {
            "id": "station-1",
            "name": "Test Station",
            "place": "Munich",
            "latitude": 48.1,
            "longitude": 11.5,
        },
        "planned": ts,
        "time": ts,
        "platform": "2",
        "line": {"label": "U3", "transportType": "UBAHN", "destination": "Moosach"},
        "delayInMinutes": 0,
        "messages": [],
    }
    stop = map_route_stop(data)
    assert isinstance(stop, RouteStop)
    assert stop.id == "station-1"
    assert stop.name == "Test Station"
    assert stop.transport_type == "UBAHN"
    assert stop.line == "U3"


def test_map_route_stop_none():
    assert map_route_stop(None) is None


def test_map_route_leg():
    data = {
        "departure": {"station": {"id": "start"}},
        "arrival": {"station": {"id": "end"}},
        "line": {"label": "U3", "transportType": "UBAHN"},
        "duration": 10,
        "distance": 1000,
        "intermediateStops": [],
    }
    leg = map_route_leg(data)
    assert isinstance(leg, RouteLeg)
    assert leg.origin.id == "start"
    assert leg.destination.id == "end"
    assert leg.transport_type == "UBAHN"
    assert leg.duration_minutes == 10
    assert leg.distance_meters == 1000


def test_map_route_leg_none():
    assert map_route_leg({}) is None


def test_map_route_plan():
    data = {
        "duration": 20,
        "transfers": 1,
        "departure": {"station": {"id": "start"}},
        "arrival": {"station": {"id": "end"}},
        "legs": [
            {
                "departure": {"station": {"id": "start"}},
                "arrival": {"station": {"id": "end"}},
                "line": {"label": "U3"},
            }
        ],
    }
    plan = map_route_plan(data)
    assert isinstance(plan, RoutePlan)
    assert plan.duration_minutes == 20
    assert plan.transfers == 1
    assert len(plan.legs) == 1


def test_extract_routes():
    assert extract_routes(None) == []
    assert extract_routes([{"id": 1}]) == [{"id": 1}]
    assert extract_routes({"routes": [{"id": 1}]}) == [{"id": 1}]
    assert extract_routes({"connections": [{"id": 1}]}) == [{"id": 1}]
    assert extract_routes({}) == []
