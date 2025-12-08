"""
Unit tests for TransitDataService.

Tests combined static and real-time transit data functionality.
"""

from datetime import datetime, timezone

from app.services.transit_data import (
    DepartureInfo,
    RouteInfo,
    StopInfo,
    ScheduleRelationship,
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
