"""
Unit tests for GTFS dataclass models.

Tests dataclass __post_init__ defaults and field handling.
"""

from datetime import datetime, timezone

from app.services.gtfs_realtime import (
    TripUpdate,
    VehiclePosition,
    ServiceAlert,
)

from app.services.transit_data import (
    DepartureInfo,
    RouteInfo,
    StopInfo,
    ScheduleRelationship,
)


class TestTripUpdateDataclass:
    """Tests for TripUpdate dataclass."""

    def test_trip_update_defaults_timestamp(self):
        """Test that TripUpdate defaults timestamp to current time."""
        before = datetime.now(timezone.utc)
        tu = TripUpdate(
            trip_id="trip1",
            route_id="route1",
            stop_id="stop1",
            stop_sequence=1,
        )
        after = datetime.now(timezone.utc)

        assert tu.timestamp is not None
        assert before <= tu.timestamp <= after

    def test_trip_update_with_explicit_timestamp(self):
        """Test TripUpdate with explicitly set timestamp."""
        explicit_time = datetime(2025, 12, 8, 10, 0, 0, tzinfo=timezone.utc)
        tu = TripUpdate(
            trip_id="trip1",
            route_id="route1",
            stop_id="stop1",
            stop_sequence=1,
            timestamp=explicit_time,
        )

        assert tu.timestamp == explicit_time

    def test_trip_update_delay_fields(self):
        """Test TripUpdate delay fields default to None."""
        tu = TripUpdate(
            trip_id="trip1",
            route_id="route1",
            stop_id="stop1",
            stop_sequence=1,
        )

        assert tu.arrival_delay is None
        assert tu.departure_delay is None

    def test_trip_update_schedule_relationship_default(self):
        """Test TripUpdate schedule_relationship default."""
        tu = TripUpdate(
            trip_id="trip1",
            route_id="route1",
            stop_id="stop1",
            stop_sequence=1,
        )

        assert tu.schedule_relationship == "SCHEDULED"


class TestVehiclePositionDataclass:
    """Tests for VehiclePosition dataclass."""

    def test_vehicle_position_defaults_timestamp(self):
        """Test that VehiclePosition defaults timestamp to current time."""
        before = datetime.now(timezone.utc)
        vp = VehiclePosition(
            trip_id="trip1",
            vehicle_id="vehicle1",
            route_id="route1",
            latitude=48.1351,
            longitude=11.5820,
        )
        after = datetime.now(timezone.utc)

        assert vp.timestamp is not None
        assert before <= vp.timestamp <= after

    def test_vehicle_position_with_explicit_timestamp(self):
        """Test VehiclePosition with explicitly set timestamp."""
        explicit_time = datetime(2025, 12, 8, 10, 0, 0, tzinfo=timezone.utc)
        vp = VehiclePosition(
            trip_id="trip1",
            vehicle_id="vehicle1",
            route_id="route1",
            latitude=48.1351,
            longitude=11.5820,
            timestamp=explicit_time,
        )

        assert vp.timestamp == explicit_time

    def test_vehicle_position_optional_fields(self):
        """Test VehiclePosition optional fields default to None."""
        vp = VehiclePosition(
            trip_id="trip1",
            vehicle_id="vehicle1",
            route_id="route1",
            latitude=48.1351,
            longitude=11.5820,
        )

        assert vp.bearing is None
        assert vp.speed is None

    def test_vehicle_position_with_optional_fields(self):
        """Test VehiclePosition with optional fields set."""
        vp = VehiclePosition(
            trip_id="trip1",
            vehicle_id="vehicle1",
            route_id="route1",
            latitude=48.1351,
            longitude=11.5820,
            bearing=90.0,
            speed=50.5,
        )

        assert vp.bearing == 90.0
        assert vp.speed == 50.5


class TestServiceAlertDataclass:
    """Tests for ServiceAlert dataclass."""

    def test_service_alert_defaults_timestamp(self):
        """Test that ServiceAlert defaults timestamp to current time."""
        before = datetime.now(timezone.utc)
        alert = ServiceAlert(
            alert_id="alert1",
            cause="TECHNICAL_PROBLEM",
            effect="SIGNIFICANT_DELAYS",
            header_text="Test Alert",
            description_text="Test Description",
            affected_routes={"route1"},
            affected_stops={"stop1"},
        )
        after = datetime.now(timezone.utc)

        assert alert.timestamp is not None
        assert before <= alert.timestamp <= after

    def test_service_alert_with_explicit_timestamp(self):
        """Test ServiceAlert with explicitly set timestamp."""
        explicit_time = datetime(2025, 12, 8, 10, 0, 0, tzinfo=timezone.utc)
        alert = ServiceAlert(
            alert_id="alert1",
            cause="TECHNICAL_PROBLEM",
            effect="SIGNIFICANT_DELAYS",
            header_text="Test Alert",
            description_text="Test Description",
            affected_routes={"route1"},
            affected_stops={"stop1"},
            timestamp=explicit_time,
        )

        assert alert.timestamp == explicit_time

    def test_service_alert_time_range_defaults(self):
        """Test ServiceAlert start/end time defaults."""
        alert = ServiceAlert(
            alert_id="alert1",
            cause="TECHNICAL_PROBLEM",
            effect="SIGNIFICANT_DELAYS",
            header_text="Test Alert",
            description_text="Test Description",
            affected_routes={"route1"},
            affected_stops={"stop1"},
        )

        assert alert.start_time is None
        assert alert.end_time is None

    def test_service_alert_affected_sets(self):
        """Test ServiceAlert affected routes and stops as sets."""
        alert = ServiceAlert(
            alert_id="alert1",
            cause="ACCIDENT",
            effect="DETOUR",
            header_text="Test",
            description_text="Test",
            affected_routes={"route1", "route2", "route3"},
            affected_stops={"stop1", "stop2"},
        )

        assert len(alert.affected_routes) == 3
        assert len(alert.affected_stops) == 2
        assert "route1" in alert.affected_routes
        assert "stop1" in alert.affected_stops


class TestDepartureInfoDataclass:
    """Tests for DepartureInfo dataclass."""

    def test_departure_info_defaults_alerts_list(self):
        """Test that DepartureInfo defaults alerts to empty list."""
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

    def test_departure_info_schedule_relationship_default(self):
        """Test DepartureInfo schedule_relationship default."""
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

        assert dep.schedule_relationship == ScheduleRelationship.SCHEDULED

    def test_departure_info_optional_fields_none(self):
        """Test DepartureInfo optional fields default to None."""
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


class TestRouteInfoDataclass:
    """Tests for RouteInfo dataclass."""

    def test_route_info_defaults_alerts_list(self):
        """Test that RouteInfo defaults alerts to empty list."""
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
        assert len(route.alerts) == 0

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


class TestStopInfoDataclass:
    """Tests for StopInfo dataclass."""

    def test_stop_info_defaults_lists(self):
        """Test that StopInfo defaults lists to empty."""
        stop = StopInfo(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.1403,
            stop_lon=11.5583,
        )

        assert stop.upcoming_departures is not None
        assert stop.alerts is not None
        assert isinstance(stop.upcoming_departures, list)
        assert isinstance(stop.alerts, list)
        assert len(stop.upcoming_departures) == 0
        assert len(stop.alerts) == 0

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
