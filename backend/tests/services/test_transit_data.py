"""
Unit tests for TransitDataService.

Tests combined static and real-time transit data functionality.
"""

from dataclasses import dataclass as dc
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.transit_data import (
    DepartureInfo,
    RouteInfo,
    StopInfo,
    ScheduleRelationship,
    TransitDataService,
)


class TestDepartureInfo:
    """Tests for DepartureInfo dataclass."""

    def test_departure_info_creation(self):
        """Test creating a DepartureInfo."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
        )

        assert dep.trip_id == "trip1"
        assert dep.route_short_name == "S1"
        assert dep.alerts == []

    def test_departure_info_defaults_alerts_list(self):
        """Test that alerts defaults to empty list."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
        )

        assert dep.alerts is not None
        assert isinstance(dep.alerts, list)
        assert len(dep.alerts) == 0

    def test_departure_info_with_real_time(self):
        """Test DepartureInfo with real-time updates."""
        scheduled = datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc)
        real_time = datetime(2025, 12, 8, 8, 35, tzinfo=timezone.utc)

        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=scheduled,
            real_time_departure=real_time,
            departure_delay_seconds=300,
        )

        assert dep.departure_delay_seconds == 300
        assert dep.real_time_departure == real_time

    def test_departure_info_optional_fields_default(self):
        """Test that optional fields default to None."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
        )

        assert dep.scheduled_arrival is None
        assert dep.real_time_departure is None
        assert dep.real_time_arrival is None
        assert dep.departure_delay_seconds is None
        assert dep.arrival_delay_seconds is None
        assert dep.vehicle_id is None
        assert dep.vehicle_position is None


class TestDepartureInfoSerialization:
    """Tests for DepartureInfo to_dict and from_dict methods."""

    def test_to_dict_and_from_dict_roundtrip(self):
        """Test that to_dict and from_dict are inverse operations."""
        original = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            scheduled_arrival=datetime(2025, 12, 8, 8, 29, tzinfo=timezone.utc),
            real_time_departure=datetime(2025, 12, 8, 8, 35, tzinfo=timezone.utc),
            real_time_arrival=datetime(2025, 12, 8, 8, 34, tzinfo=timezone.utc),
            departure_delay_seconds=300,
            arrival_delay_seconds=300,
            schedule_relationship=ScheduleRelationship.SCHEDULED,
            vehicle_id="vehicle123",
            vehicle_position={"latitude": 48.1351, "longitude": 11.5820},
        )

        serialized = original.to_dict()
        restored = DepartureInfo.from_dict(serialized)

        assert restored.trip_id == original.trip_id
        assert restored.route_id == original.route_id
        assert restored.scheduled_departure == original.scheduled_departure
        assert restored.scheduled_arrival == original.scheduled_arrival
        assert restored.real_time_departure == original.real_time_departure
        assert restored.departure_delay_seconds == original.departure_delay_seconds
        assert restored.schedule_relationship == original.schedule_relationship
        assert restored.vehicle_id == original.vehicle_id
        assert restored.vehicle_position == original.vehicle_position

    def test_to_dict_converts_datetimes_to_iso_strings(self):
        """Test that to_dict converts datetime fields to ISO format strings."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            real_time_departure=datetime(2025, 12, 8, 8, 35, tzinfo=timezone.utc),
        )

        result = dep.to_dict()

        assert isinstance(result["scheduled_departure"], str)
        assert result["scheduled_departure"] == "2025-12-08T08:30:00+00:00"
        assert isinstance(result["real_time_departure"], str)
        assert result["real_time_departure"] == "2025-12-08T08:35:00+00:00"

    def test_to_dict_converts_enum_to_string(self):
        """Test that to_dict converts ScheduleRelationship enum to string."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            schedule_relationship=ScheduleRelationship.SKIPPED,
        )

        result = dep.to_dict()

        assert result["schedule_relationship"] == "SKIPPED"

    def test_from_dict_converts_string_to_enum(self):
        """Test that from_dict converts string to ScheduleRelationship enum."""
        data = {
            "trip_id": "trip1",
            "route_id": "route1",
            "route_short_name": "S1",
            "route_long_name": "Test Route",
            "trip_headsign": "Destination",
            "stop_id": "stop1",
            "stop_name": "Test Stop",
            "scheduled_departure": "2025-12-08T08:30:00+00:00",
            "schedule_relationship": "SKIPPED",
            "alerts": [],
        }

        result = DepartureInfo.from_dict(data)

        assert result.schedule_relationship == ScheduleRelationship.SKIPPED

    def test_from_dict_does_not_mutate_input(self):
        """Test that from_dict does not modify the input dictionary."""
        data = {
            "trip_id": "trip1",
            "route_id": "route1",
            "route_short_name": "S1",
            "route_long_name": "Test Route",
            "trip_headsign": "Destination",
            "stop_id": "stop1",
            "stop_name": "Test Stop",
            "scheduled_departure": "2025-12-08T08:30:00+00:00",
            "schedule_relationship": "SCHEDULED",
            "alerts": [],
        }
        original_schedule_relationship = data["schedule_relationship"]
        original_scheduled_departure = data["scheduled_departure"]

        DepartureInfo.from_dict(data)

        # Input should not be mutated
        assert data["schedule_relationship"] == original_schedule_relationship
        assert data["scheduled_departure"] == original_scheduled_departure

    def test_to_dict_handles_none_optional_fields(self):
        """Test that to_dict handles None optional fields correctly."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
        )

        result = dep.to_dict()

        assert result["scheduled_arrival"] is None
        assert result["real_time_departure"] is None
        assert result["vehicle_id"] is None

    def test_from_dict_handles_none_optional_fields(self):
        """Test that from_dict handles None optional fields correctly."""
        data = {
            "trip_id": "trip1",
            "route_id": "route1",
            "route_short_name": "S1",
            "route_long_name": "Test Route",
            "trip_headsign": "Destination",
            "stop_id": "stop1",
            "stop_name": "Test Stop",
            "scheduled_departure": "2025-12-08T08:30:00+00:00",
            "scheduled_arrival": None,
            "real_time_departure": None,
            "real_time_arrival": None,
            "departure_delay_seconds": None,
            "arrival_delay_seconds": None,
            "schedule_relationship": "SCHEDULED",
            "vehicle_id": None,
            "vehicle_position": None,
            "alerts": [],
        }

        result = DepartureInfo.from_dict(data)

        assert result.scheduled_arrival is None
        assert result.real_time_departure is None
        assert result.vehicle_id is None

    def test_to_dict_with_service_alerts(self):
        """Test that to_dict properly serializes ServiceAlert objects."""
        from app.services.gtfs_realtime import ServiceAlert

        alert = ServiceAlert(
            alert_id="alert1",
            cause="TECHNICAL_PROBLEM",
            effect="SIGNIFICANT_DELAYS",
            header_text="S-Bahn delays",
            description_text="Due to technical issues",
            affected_routes={"S1", "S2"},
            affected_stops={"stop1", "stop2"},
            start_time=datetime(2025, 12, 8, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 12, 8, 18, 0, tzinfo=timezone.utc),
            timestamp=datetime(2025, 12, 8, 5, 30, tzinfo=timezone.utc),
        )

        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            alerts=[alert],
        )

        result = dep.to_dict()

        assert len(result["alerts"]) == 1
        alert_dict = result["alerts"][0]
        assert alert_dict["alert_id"] == "alert1"
        assert alert_dict["cause"] == "TECHNICAL_PROBLEM"
        # Sets should be converted to lists
        assert isinstance(alert_dict["affected_routes"], list)
        assert set(alert_dict["affected_routes"]) == {"S1", "S2"}
        # Datetimes should be ISO strings
        assert isinstance(alert_dict["start_time"], str)
        assert alert_dict["start_time"] == "2025-12-08T06:00:00+00:00"

    def test_from_dict_with_service_alerts(self):
        """Test that from_dict properly reconstructs ServiceAlert objects."""
        data = {
            "trip_id": "trip1",
            "route_id": "route1",
            "route_short_name": "S1",
            "route_long_name": "Test Route",
            "trip_headsign": "Destination",
            "stop_id": "stop1",
            "stop_name": "Test Stop",
            "scheduled_departure": "2025-12-08T08:30:00+00:00",
            "scheduled_arrival": None,
            "real_time_departure": None,
            "real_time_arrival": None,
            "departure_delay_seconds": None,
            "arrival_delay_seconds": None,
            "schedule_relationship": "SCHEDULED",
            "vehicle_id": None,
            "vehicle_position": None,
            "alerts": [
                {
                    "alert_id": "alert1",
                    "cause": "TECHNICAL_PROBLEM",
                    "effect": "SIGNIFICANT_DELAYS",
                    "header_text": "Delays",
                    "description_text": "Technical issues",
                    "affected_routes": ["S1", "S2"],
                    "affected_stops": ["stop1"],
                    "start_time": "2025-12-08T06:00:00+00:00",
                    "end_time": "2025-12-08T18:00:00+00:00",
                    "timestamp": "2025-12-08T05:30:00+00:00",
                }
            ],
        }

        result = DepartureInfo.from_dict(data)

        assert len(result.alerts) == 1
        alert = result.alerts[0]
        assert alert.alert_id == "alert1"
        assert alert.cause == "TECHNICAL_PROBLEM"
        # Lists should be converted back to sets
        assert isinstance(alert.affected_routes, set)
        assert alert.affected_routes == {"S1", "S2"}
        # ISO strings should be converted back to datetimes
        assert isinstance(alert.start_time, datetime)
        assert alert.start_time == datetime(2025, 12, 8, 6, 0, tzinfo=timezone.utc)

    def test_to_dict_from_dict_roundtrip_with_alerts(self):
        """Test full round-trip serialization with ServiceAlert objects."""
        from app.services.gtfs_realtime import ServiceAlert

        alert = ServiceAlert(
            alert_id="alert1",
            cause="STRIKE",
            effect="NO_SERVICE",
            header_text="Strike",
            description_text="Workers on strike",
            affected_routes={"U1"},
            affected_stops=set(),
            start_time=datetime(2025, 12, 8, 0, 0, tzinfo=timezone.utc),
            end_time=None,
            timestamp=datetime(2025, 12, 7, 18, 0, tzinfo=timezone.utc),
        )

        original = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="U1",
            route_long_name="U-Bahn Line 1",
            trip_headsign="Olympiazentrum",
            stop_id="stop1",
            stop_name="Marienplatz",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            alerts=[alert],
        )

        serialized = original.to_dict()
        restored = DepartureInfo.from_dict(serialized)

        assert len(restored.alerts) == 1
        restored_alert = restored.alerts[0]
        assert restored_alert.alert_id == alert.alert_id
        assert restored_alert.cause == alert.cause
        assert restored_alert.affected_routes == alert.affected_routes


class TestRouteInfo:
    """Tests for RouteInfo dataclass."""

    def test_route_info_creation(self):
        """Test creating a RouteInfo."""
        route = RouteInfo(
            route_id="1-S1-1",
            route_short_name="S1",
            route_long_name="Freising - München",
            route_type=2,
            route_color="00BFFF",
            route_text_color="FFFFFF",
        )

        assert route.route_id == "1-S1-1"
        assert route.route_type == 2
        assert route.alerts == []

    def test_route_info_defaults_alerts_list(self):
        """Test that alerts defaults to empty list."""
        route = RouteInfo(
            route_id="1-S1-1",
            route_short_name="S1",
            route_long_name="Test Route",
            route_type=2,
            route_color="00BFFF",
            route_text_color="FFFFFF",
        )

        assert route.alerts is not None
        assert isinstance(route.alerts, list)

    def test_route_info_active_trips_default(self):
        """Test RouteInfo active_trips default."""
        route = RouteInfo(
            route_id="1-S1-1",
            route_short_name="S1",
            route_long_name="Test Route",
            route_type=2,
            route_color="00BFFF",
            route_text_color="FFFFFF",
        )

        assert route.active_trips == 0


class TestStopInfo:
    """Tests for StopInfo dataclass."""

    def test_stop_info_creation(self):
        """Test creating a StopInfo."""
        stop = StopInfo(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.1403,
            stop_lon=11.5583,
        )

        assert stop.stop_id == "de:09162:6"
        assert stop.stop_name == "München Hbf"
        assert stop.upcoming_departures == []
        assert stop.alerts == []

    def test_stop_info_defaults_lists(self):
        """Test that lists default to empty."""
        stop = StopInfo(
            stop_id="stop1",
            stop_name="Test Stop",
            stop_lat=48.0,
            stop_lon=11.0,
        )

        assert stop.upcoming_departures is not None
        assert stop.alerts is not None
        assert isinstance(stop.upcoming_departures, list)
        assert isinstance(stop.alerts, list)

    def test_stop_info_optional_fields(self):
        """Test StopInfo optional fields."""
        stop = StopInfo(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.1403,
            stop_lon=11.5583,
        )

        assert stop.zone_id is None
        assert stop.wheelchair_boarding == 0

    def test_stop_info_with_zone_id(self):
        """Test StopInfo with zone_id set."""
        stop = StopInfo(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.1403,
            stop_lon=11.5583,
            zone_id="M",
        )

        assert stop.zone_id == "M"


class TestScheduleRelationship:
    """Tests for ScheduleRelationship enum."""

    def test_schedule_relationship_values(self):
        """Test ScheduleRelationship enum values."""
        assert ScheduleRelationship.SCHEDULED.value == "SCHEDULED"
        assert ScheduleRelationship.SKIPPED.value == "SKIPPED"
        assert ScheduleRelationship.NO_DATA.value == "NO_DATA"
        assert ScheduleRelationship.UNSCHEDULED.value == "UNSCHEDULED"

    def test_schedule_relationship_membership(self):
        """Test that values can be used for comparison."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            schedule_relationship=ScheduleRelationship.SCHEDULED,
        )

        assert dep.schedule_relationship == ScheduleRelationship.SCHEDULED

    def test_schedule_relationship_skipped(self):
        """Test setting skipped relationship."""
        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            schedule_relationship=ScheduleRelationship.SKIPPED,
        )

        assert dep.schedule_relationship == ScheduleRelationship.SKIPPED


class TestTransitDataServiceDepartureInfo:
    """Additional tests for DepartureInfo edge cases."""

    def test_departure_info_with_vehicle_position(self):
        """Test DepartureInfo with vehicle position data."""
        vehicle_pos = {
            "latitude": 48.1351,
            "longitude": 11.5820,
            "bearing": 90.0,
            "speed": 45.0,
        }

        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            vehicle_id="vehicle123",
            vehicle_position=vehicle_pos,
        )

        assert dep.vehicle_id == "vehicle123"
        assert dep.vehicle_position["latitude"] == 48.1351
        assert dep.vehicle_position["bearing"] == 90.0

    def test_departure_info_with_alerts(self):
        """Test DepartureInfo with alerts list."""
        alerts = [{"id": "alert1", "header": "Delay on S-Bahn"}]

        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            alerts=alerts,
        )

        assert len(dep.alerts) == 1
        assert dep.alerts[0]["id"] == "alert1"

    def test_departure_info_all_delay_fields(self):
        """Test DepartureInfo with all delay fields set."""
        scheduled = datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc)
        real_departure = datetime(2025, 12, 8, 8, 35, tzinfo=timezone.utc)
        real_arrival = datetime(2025, 12, 8, 8, 34, tzinfo=timezone.utc)

        dep = DepartureInfo(
            trip_id="trip1",
            route_id="route1",
            route_short_name="S1",
            route_long_name="Test Route",
            trip_headsign="Destination",
            stop_id="stop1",
            stop_name="Test Stop",
            scheduled_departure=scheduled,
            scheduled_arrival=datetime(2025, 12, 8, 8, 29, tzinfo=timezone.utc),
            real_time_departure=real_departure,
            real_time_arrival=real_arrival,
            departure_delay_seconds=300,
            arrival_delay_seconds=300,
        )

        assert dep.departure_delay_seconds == 300
        assert dep.arrival_delay_seconds == 300
        assert dep.real_time_departure == real_departure
        assert dep.real_time_arrival == real_arrival


# =============================================================================
# TransitDataService Method Tests
# =============================================================================


@dc
class MockStop:
    """Mock GTFS stop."""

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


@dc
class MockRoute:
    """Mock GTFS route."""

    route_id: str
    route_short_name: str
    route_long_name: str
    route_type: int
    route_color: str


@dc
class MockScheduledDeparture:
    """Mock scheduled departure."""

    trip_id: str
    route_id: str
    trip_headsign: str
    departure_time: datetime
    arrival_time: datetime = None
    route_short_name: str = "S1"
    route_long_name: str = "S-Bahn Line 1"


class FakeGtfsSchedule:
    """Fake GTFS schedule service for testing."""

    def __init__(self):
        self.stops = [
            MockStop("stop1", "Marienplatz", 48.137, 11.577),
            MockStop("stop2", "Hauptbahnhof", 48.140, 11.558),
        ]
        self.departures = [
            MockScheduledDeparture(
                trip_id="trip1",
                route_id="route1",
                trip_headsign="Destination A",
                departure_time=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            ),
            MockScheduledDeparture(
                trip_id="trip2",
                route_id="route1",
                trip_headsign="Destination B",
                departure_time=datetime(2025, 12, 8, 8, 45, tzinfo=timezone.utc),
            ),
        ]

    async def get_departures_for_stop(self, stop_id: str, scheduled_time, limit: int):
        return self.departures[:limit]

    async def search_stops(self, query: str, limit: int = 10):
        return [s for s in self.stops if query.lower() in s.stop_name.lower()][:limit]


class FakeGtfsRealtime:
    """Fake GTFS realtime service for testing."""

    def __init__(self):
        self.trip_updates = []
        self.vehicle_positions = []
        self.alerts = []

    async def get_trip_updates_for_stop(self, stop_id: str):
        return self.trip_updates

    async def get_vehicle_position(self, vehicle_id: str):
        return None

    async def get_vehicle_position_by_trip(self, trip_id: str):
        return None

    async def get_alerts_for_route(self, route_id: str):
        return self.alerts

    async def fetch_trip_updates(self):
        return self.trip_updates

    async def fetch_vehicle_positions(self):
        return self.vehicle_positions

    async def fetch_alerts(self):
        return self.alerts

    async def get_vehicle_positions_by_trips(self, trip_ids):
        return {}


class FakeCacheService:
    """Fake cache service for testing."""

    def __init__(self):
        self._cache = {}

    async def get_json(self, key: str):
        return self._cache.get(key)

    async def get_stale_json(self, key: str):
        """Get stale JSON from cache (returns None by default)."""
        return self._cache.get(f"{key}:stale")

    async def set_json(self, key: str, value, ttl_seconds=None, stale_ttl_seconds=None):
        self._cache[key] = value

    async def mget_json(self, keys: list):
        """Batch get JSON from cache."""
        return {key: self._cache.get(key) for key in keys}


class FakeDbSession:
    """Fake database session for testing."""

    def __init__(self, stops=None, routes=None):
        self._stops = {s.stop_id: s for s in (stops or [])}
        self._routes = {r.route_id: r for r in (routes or [])}

    async def execute(self, stmt):
        # Simplified mock that returns based on query type
        return FakeResult(self._stops, self._routes)


class FakeResult:
    """Fake SQLAlchemy result."""

    def __init__(self, stops, routes):
        self._stops = stops
        self._routes = routes
        self._query_type = None

    def scalar_one_or_none(self):
        # Return first item for simplicity
        if self._stops:
            return list(self._stops.values())[0]
        return None

    def scalars(self):
        return FakeScalars(list(self._routes.values()))


class FakeScalars:
    """Fake scalars result."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


@pytest.fixture
def transit_service():
    """Create TransitDataService with fake dependencies."""
    cache = FakeCacheService()
    schedule = FakeGtfsSchedule()
    realtime = FakeGtfsRealtime()
    db = FakeDbSession(
        stops=[
            MockStop("stop1", "Marienplatz", 48.137, 11.577),
        ],
        routes=[
            MockRoute("route1", "S1", "S-Bahn Line 1", 2, "00FF00"),
        ],
    )

    with patch("app.services.transit_data.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            gtfs_rt_enabled=True,
            gtfs_schedule_cache_ttl_seconds=300,
            gtfs_stop_cache_ttl_seconds=600,
        )
        service = TransitDataService(cache, schedule, realtime, db)

    return service


class TestTransitDataServiceMethods:
    """Tests for TransitDataService methods."""

    @pytest.mark.asyncio
    async def test_is_realtime_available_true(self, transit_service):
        """Test is_realtime_available returns True when configured."""
        assert transit_service.is_realtime_available() is True

    @pytest.mark.asyncio
    async def test_is_realtime_available_false_when_disabled(self):
        """Test is_realtime_available returns False when RT disabled."""
        cache = FakeCacheService()
        schedule = FakeGtfsSchedule()
        realtime = FakeGtfsRealtime()
        db = FakeDbSession()

        with patch("app.services.transit_data.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(gtfs_rt_enabled=False)
            service = TransitDataService(cache, schedule, realtime, db)

        assert service.is_realtime_available() is False

    @pytest.mark.asyncio
    async def test_is_realtime_available_false_when_no_service(self):
        """Test is_realtime_available returns False when no realtime service."""
        cache = FakeCacheService()
        schedule = FakeGtfsSchedule()
        db = FakeDbSession()

        with patch("app.services.transit_data.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(gtfs_rt_enabled=True)
            service = TransitDataService(cache, schedule, None, db)

        assert service.is_realtime_available() is False

    @pytest.mark.asyncio
    async def test_search_stops_returns_matching_stops(self, transit_service):
        """Test search_stops returns stops matching query."""
        result = await transit_service.search_stops("marien", limit=10)

        assert len(result) == 1
        assert result[0].stop_id == "stop1"
        assert result[0].stop_name == "Marienplatz"

    @pytest.mark.asyncio
    async def test_search_stops_returns_empty_for_no_match(self, transit_service):
        """Test search_stops returns empty list for no matches."""
        result = await transit_service.search_stops("nonexistent", limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_search_stops_respects_limit(self, transit_service):
        """Test search_stops respects the limit parameter."""
        # Add more stops to the schedule
        transit_service.gtfs_schedule.stops.extend(
            [
                MockStop("stop3", "Marienstr", 48.0, 11.0),
                MockStop("stop4", "Marienberg", 48.0, 11.0),
            ]
        )

        result = await transit_service.search_stops("marien", limit=2)

        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_search_stops_handles_exception(self, transit_service):
        """Test search_stops returns empty list on exception."""
        transit_service.gtfs_schedule.search_stops = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await transit_service.search_stops("test", limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_returns_departures(self, transit_service):
        """Test get_departures_for_stop returns departure info."""
        result = await transit_service.get_departures_for_stop(
            "stop1", limit=10, include_real_time=False
        )

        assert len(result) == 2
        assert result[0].trip_id == "trip1"
        assert result[0].route_short_name == "S1"
        assert result[0].stop_name == "Marienplatz"

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_empty_when_no_departures(
        self, transit_service
    ):
        """Test get_departures_for_stop returns empty list when no departures."""
        transit_service.gtfs_schedule.departures = []

        result = await transit_service.get_departures_for_stop("stop1", limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_handles_exception(self, transit_service):
        """Test get_departures_for_stop returns empty list on exception."""
        transit_service.gtfs_schedule.get_departures_for_stop = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await transit_service.get_departures_for_stop("stop1", limit=10)

        assert result == []

    @pytest.mark.asyncio
    async def test_refresh_real_time_data_success(self, transit_service):
        """Test refresh_real_time_data returns counts."""
        transit_service.gtfs_realtime.trip_updates = [MagicMock(), MagicMock()]
        transit_service.gtfs_realtime.vehicle_positions = [MagicMock()]
        transit_service.gtfs_realtime.alerts = [MagicMock(), MagicMock(), MagicMock()]

        result = await transit_service.refresh_real_time_data()

        assert result["trip_updates"] == 2
        assert result["vehicle_positions"] == 1
        assert result["alerts"] == 3

    @pytest.mark.asyncio
    async def test_refresh_real_time_data_handles_exceptions(self, transit_service):
        """Test refresh_real_time_data handles fetch exceptions."""
        transit_service.gtfs_realtime.fetch_trip_updates = AsyncMock(
            side_effect=Exception("Network error")
        )
        transit_service.gtfs_realtime.fetch_vehicle_positions = AsyncMock(
            return_value=[MagicMock()]
        )
        transit_service.gtfs_realtime.fetch_alerts = AsyncMock(return_value=[])

        result = await transit_service.refresh_real_time_data()

        assert result["trip_updates"] == 0  # Exception case
        assert result["vehicle_positions"] == 1
        assert result["alerts"] == 0

    @pytest.mark.asyncio
    async def test_get_vehicle_position_delegates_to_realtime(self, transit_service):
        """Test get_vehicle_position delegates to realtime service."""
        result = await transit_service.get_vehicle_position("vehicle123")

        assert result is None  # Our fake returns None

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_returns_cached_data(self, transit_service):
        """Test get_departures_for_stop returns cached data on cache hit."""
        # Pre-populate cache with serialized departures

        cached_departures = [
            {
                "trip_id": "cached_trip",
                "route_id": "route1",
                "route_short_name": "S1",
                "route_long_name": "Cached Route",
                "trip_headsign": "From Cache",
                "stop_id": "stop1",
                "stop_name": "Test Stop",
                "scheduled_departure": "2025-12-08T10:00:00+00:00",
                "scheduled_arrival": None,
                "real_time_departure": None,
                "real_time_arrival": None,
                "departure_delay_seconds": None,
                "arrival_delay_seconds": None,
                "schedule_relationship": "SCHEDULED",
                "vehicle_id": None,
                "vehicle_position": None,
                "alerts": [],
            }
        ]

        # Cache key without time bucket (Issue 5 fix: removed time bucket for stale-while-revalidate)
        cache_key = "departures:stop1:10:0:False"

        # Pre-populate the cache
        await transit_service.cache.set_json(cache_key, cached_departures)

        # Call should return cached data
        result = await transit_service.get_departures_for_stop(
            "stop1", limit=10, include_real_time=False
        )

        assert len(result) == 1
        assert result[0].trip_id == "cached_trip"
        assert result[0].trip_headsign == "From Cache"

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_caches_result(self, transit_service):
        """Test get_departures_for_stop stores result in cache."""
        # First call - should populate cache
        result = await transit_service.get_departures_for_stop(
            "stop1", limit=10, include_real_time=False
        )

        assert len(result) == 2

        # Cache key without time bucket (Issue 5 fix: removed time bucket for stale-while-revalidate)
        cache_key = "departures:stop1:10:0:False"

        cached = await transit_service.cache.get_json(cache_key)
        assert cached is not None
        assert len(cached) == 2
        assert cached[0]["trip_id"] == "trip1"
