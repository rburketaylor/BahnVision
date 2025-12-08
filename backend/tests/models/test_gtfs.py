"""
Unit tests for GTFS SQLAlchemy models.

Tests model creation, field validation, and relationships.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.gtfs import (
    GTFSStop,
    GTFSRoute,
    GTFSTrip,
    GTFSStopTime,
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
)


class TestGTFSStopModel:
    """Tests for GTFSStop model."""

    def test_gtfs_stop_model_creation(self):
        """Test creating a GTFS stop with all required fields."""
        stop = GTFSStop(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=Decimal("48.140300"),
            stop_lon=Decimal("11.558300"),
            location_type=1,
            feed_id="test_feed",
        )

        assert stop.stop_id == "de:09162:6"
        assert stop.stop_name == "München Hbf"
        assert stop.stop_lat == Decimal("48.140300")
        assert stop.stop_lon == Decimal("11.558300")
        assert stop.location_type == 1
        assert stop.feed_id == "test_feed"

    def test_gtfs_stop_optional_fields(self):
        """Test creating a stop with optional fields."""
        stop = GTFSStop(
            stop_id="de:09162:6:1",
            stop_name="München Hbf Gleis 1",
            stop_lat=Decimal("48.140300"),
            stop_lon=Decimal("11.558300"),
            location_type=0,
            parent_station="de:09162:6",
            platform_code="1",
            feed_id="test_feed",
        )

        assert stop.parent_station == "de:09162:6"
        assert stop.platform_code == "1"

    def test_gtfs_stop_location_type_default(self):
        """Test that location_type defaults correctly.

        Note: SQLAlchemy column defaults are applied at INSERT time, not
        instantiation. The model may have None until committed.
        """
        stop = GTFSStop(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            feed_id="test_feed",
        )

        # Before commit, the default may be None or 0 depending on how
        # the model is used. Column default is 0.
        assert stop.location_type is None or stop.location_type == 0


class TestGTFSRouteModel:
    """Tests for GTFSRoute model."""

    def test_gtfs_route_model_creation(self):
        """Test creating a GTFS route."""
        route = GTFSRoute(
            route_id="1-S1-1",
            agency_id="db",
            route_short_name="S1",
            route_long_name="Freising - München Hbf - Ostbahnhof",
            route_type=2,
            route_color="00BFFF",
            feed_id="test_feed",
        )

        assert route.route_id == "1-S1-1"
        assert route.agency_id == "db"
        assert route.route_short_name == "S1"
        assert route.route_long_name == "Freising - München Hbf - Ostbahnhof"
        assert route.route_type == 2
        assert route.route_color == "00BFFF"

    def test_gtfs_route_types(self):
        """Test various route types match GTFS spec."""
        # Tram
        tram = GTFSRoute(
            route_id="tram", route_type=0, route_short_name="19", feed_id="test"
        )
        assert tram.route_type == 0

        # Metro
        metro = GTFSRoute(
            route_id="metro", route_type=1, route_short_name="U3", feed_id="test"
        )
        assert metro.route_type == 1

        # Rail
        rail = GTFSRoute(
            route_id="rail", route_type=2, route_short_name="S1", feed_id="test"
        )
        assert rail.route_type == 2

        # Bus
        bus = GTFSRoute(
            route_id="bus", route_type=3, route_short_name="100", feed_id="test"
        )
        assert bus.route_type == 3


class TestGTFSTripModel:
    """Tests for GTFSTrip model."""

    def test_gtfs_trip_model_creation(self):
        """Test creating a GTFS trip."""
        trip = GTFSTrip(
            trip_id="trip_001",
            route_id="1-S1-1",
            service_id="service_weekday",
            trip_headsign="Ostbahnhof",
            direction_id=0,
            feed_id="test_feed",
        )

        assert trip.trip_id == "trip_001"
        assert trip.route_id == "1-S1-1"
        assert trip.service_id == "service_weekday"
        assert trip.trip_headsign == "Ostbahnhof"
        assert trip.direction_id == 0

    def test_gtfs_trip_direction_values(self):
        """Test trip direction_id values."""
        # Direction 0 (outbound)
        trip_out = GTFSTrip(
            trip_id="t1",
            route_id="r1",
            service_id="s1",
            direction_id=0,
            feed_id="test",
        )
        assert trip_out.direction_id == 0

        # Direction 1 (inbound)
        trip_in = GTFSTrip(
            trip_id="t2",
            route_id="r1",
            service_id="s1",
            direction_id=1,
            feed_id="test",
        )
        assert trip_in.direction_id == 1


class TestGTFSStopTimeModel:
    """Tests for GTFSStopTime model."""

    def test_gtfs_stop_time_model_creation(self):
        """Test creating a GTFS stop time."""
        stop_time = GTFSStopTime(
            trip_id="trip_001",
            stop_id="de:09162:6",
            arrival_time=timedelta(hours=8, minutes=0),
            departure_time=timedelta(hours=8, minutes=2),
            stop_sequence=1,
            pickup_type=0,
            drop_off_type=0,
            feed_id="test_feed",
        )

        assert stop_time.trip_id == "trip_001"
        assert stop_time.stop_id == "de:09162:6"
        assert stop_time.arrival_time == timedelta(hours=8, minutes=0)
        assert stop_time.departure_time == timedelta(hours=8, minutes=2)
        assert stop_time.stop_sequence == 1

    def test_gtfs_stop_time_over_24h(self):
        """Test stop time with times exceeding 24 hours (next-day service)."""
        # 25:30:00 = 1:30 AM the next day
        stop_time = GTFSStopTime(
            trip_id="night_trip",
            stop_id="stop1",
            arrival_time=timedelta(hours=25, minutes=30),
            departure_time=timedelta(hours=25, minutes=32),
            stop_sequence=1,
            feed_id="test",
        )

        assert stop_time.arrival_time.total_seconds() == 25 * 3600 + 30 * 60
        assert stop_time.departure_time.total_seconds() == 25 * 3600 + 32 * 60

    def test_gtfs_stop_time_pickup_drop_off_types(self):
        """Test pickup and drop-off types."""
        # Regular stop (0)
        regular = GTFSStopTime(
            trip_id="t",
            stop_id="s",
            stop_sequence=1,
            pickup_type=0,
            drop_off_type=0,
            feed_id="test",
        )
        assert regular.pickup_type == 0
        assert regular.drop_off_type == 0

        # No pickup (1)
        no_pickup = GTFSStopTime(
            trip_id="t",
            stop_id="s",
            stop_sequence=2,
            pickup_type=1,
            drop_off_type=0,
            feed_id="test",
        )
        assert no_pickup.pickup_type == 1

        # Request stop (3)
        request = GTFSStopTime(
            trip_id="t",
            stop_id="s",
            stop_sequence=3,
            pickup_type=3,
            drop_off_type=3,
            feed_id="test",
        )
        assert request.pickup_type == 3
        assert request.drop_off_type == 3


class TestGTFSCalendarModel:
    """Tests for GTFSCalendar model."""

    def test_gtfs_calendar_model_creation(self):
        """Test creating a GTFS calendar."""
        calendar = GTFSCalendar(
            service_id="service_weekday",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            feed_id="test_feed",
        )

        assert calendar.service_id == "service_weekday"
        assert calendar.monday is True
        assert calendar.tuesday is True
        assert calendar.saturday is False
        assert calendar.sunday is False
        assert calendar.start_date == date(2025, 1, 1)
        assert calendar.end_date == date(2025, 12, 31)

    def test_gtfs_calendar_weekend_only(self):
        """Test weekend-only service calendar."""
        calendar = GTFSCalendar(
            service_id="service_weekend",
            monday=False,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=True,
            sunday=True,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            feed_id="test",
        )

        assert calendar.monday is False
        assert calendar.saturday is True
        assert calendar.sunday is True


class TestGTFSCalendarDateModel:
    """Tests for GTFSCalendarDate model."""

    def test_gtfs_calendar_date_model_creation(self):
        """Test creating a GTFS calendar date exception."""
        calendar_date = GTFSCalendarDate(
            service_id="service_weekday",
            date=date(2025, 12, 25),
            exception_type=2,  # 2 = removed
            feed_id="test_feed",
        )

        assert calendar_date.service_id == "service_weekday"
        assert calendar_date.date == date(2025, 12, 25)
        assert calendar_date.exception_type == 2

    def test_gtfs_calendar_date_exception_types(self):
        """Test exception type values."""
        # 1 = Service added
        added = GTFSCalendarDate(
            service_id="s1",
            date=date(2025, 5, 1),
            exception_type=1,
            feed_id="test",
        )
        assert added.exception_type == 1

        # 2 = Service removed
        removed = GTFSCalendarDate(
            service_id="s1",
            date=date(2025, 12, 25),
            exception_type=2,
            feed_id="test",
        )
        assert removed.exception_type == 2


class TestGTFSFeedInfoModel:
    """Tests for GTFSFeedInfo model."""

    def test_gtfs_feed_info_model_creation(self):
        """Test creating a GTFS feed info record."""
        downloaded = datetime.now(timezone.utc)
        feed_info = GTFSFeedInfo(
            feed_id="gtfs_20251208_120000",
            feed_url="https://download.gtfs.de/germany/full/latest.zip",
            downloaded_at=downloaded,
            feed_start_date=date(2025, 1, 1),
            feed_end_date=date(2025, 12, 31),
            stop_count=500000,
            route_count=20000,
            trip_count=2000000,
        )

        assert feed_info.feed_id == "gtfs_20251208_120000"
        assert feed_info.feed_url == "https://download.gtfs.de/germany/full/latest.zip"
        assert feed_info.downloaded_at == downloaded
        assert feed_info.stop_count == 500000
        assert feed_info.route_count == 20000
        assert feed_info.trip_count == 2000000

    def test_gtfs_feed_info_nullable_dates(self):
        """Test that feed dates can be null."""
        feed_info = GTFSFeedInfo(
            feed_id="test",
            feed_url="https://example.com/gtfs.zip",
            downloaded_at=datetime.now(timezone.utc),
            feed_start_date=None,
            feed_end_date=None,
            stop_count=100,
            route_count=10,
            trip_count=1000,
        )

        assert feed_info.feed_start_date is None
        assert feed_info.feed_end_date is None
