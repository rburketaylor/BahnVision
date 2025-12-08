"""
GTFS test fixtures and factory functions.

Provides reusable test data for GTFS models and services.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from app.models.gtfs import (
    GTFSStop,
    GTFSRoute,
    GTFSTrip,
    GTFSStopTime,
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSFeedInfo,
)


def create_test_gtfs_stop(
    stop_id: str = "de:09162:6",
    stop_name: str = "München Hbf",
    stop_lat: float = 48.1403,
    stop_lon: float = 11.5583,
    location_type: int = 1,
    parent_station: Optional[str] = None,
    platform_code: Optional[str] = None,
    feed_id: str = "test_feed_001",
) -> GTFSStop:
    """Create a test GTFS stop."""
    return GTFSStop(
        stop_id=stop_id,
        stop_name=stop_name,
        stop_lat=Decimal(str(stop_lat)),
        stop_lon=Decimal(str(stop_lon)),
        location_type=location_type,
        parent_station=parent_station,
        platform_code=platform_code,
        feed_id=feed_id,
    )


def create_test_gtfs_route(
    route_id: str = "1-S1-1",
    agency_id: str = "db",
    route_short_name: str = "S1",
    route_long_name: str = "Freising - München Hbf - Ostbahnhof",
    route_type: int = 2,  # Rail
    route_color: str = "00BFFF",
    feed_id: str = "test_feed_001",
) -> GTFSRoute:
    """Create a test GTFS route."""
    return GTFSRoute(
        route_id=route_id,
        agency_id=agency_id,
        route_short_name=route_short_name,
        route_long_name=route_long_name,
        route_type=route_type,
        route_color=route_color,
        feed_id=feed_id,
    )


def create_test_gtfs_trip(
    trip_id: str = "trip_001",
    route_id: str = "1-S1-1",
    service_id: str = "service_weekday",
    trip_headsign: str = "Ostbahnhof",
    direction_id: int = 0,
    feed_id: str = "test_feed_001",
) -> GTFSTrip:
    """Create a test GTFS trip."""
    return GTFSTrip(
        trip_id=trip_id,
        route_id=route_id,
        service_id=service_id,
        trip_headsign=trip_headsign,
        direction_id=direction_id,
        feed_id=feed_id,
    )


def create_test_gtfs_stop_time(
    trip_id: str = "trip_001",
    stop_id: str = "de:09162:6",
    arrival_time: timedelta = timedelta(hours=8, minutes=0),
    departure_time: timedelta = timedelta(hours=8, minutes=2),
    stop_sequence: int = 1,
    pickup_type: int = 0,
    drop_off_type: int = 0,
    feed_id: str = "test_feed_001",
) -> GTFSStopTime:
    """Create a test GTFS stop time."""
    return GTFSStopTime(
        trip_id=trip_id,
        stop_id=stop_id,
        arrival_time=arrival_time,
        departure_time=departure_time,
        stop_sequence=stop_sequence,
        pickup_type=pickup_type,
        drop_off_type=drop_off_type,
        feed_id=feed_id,
    )


def create_test_gtfs_calendar(
    service_id: str = "service_weekday",
    monday: bool = True,
    tuesday: bool = True,
    wednesday: bool = True,
    thursday: bool = True,
    friday: bool = True,
    saturday: bool = False,
    sunday: bool = False,
    start_date: date = None,
    end_date: date = None,
    feed_id: str = "test_feed_001",
) -> GTFSCalendar:
    """Create a test GTFS calendar."""
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today() + timedelta(days=365)

    return GTFSCalendar(
        service_id=service_id,
        monday=monday,
        tuesday=tuesday,
        wednesday=wednesday,
        thursday=thursday,
        friday=friday,
        saturday=saturday,
        sunday=sunday,
        start_date=start_date,
        end_date=end_date,
        feed_id=feed_id,
    )


def create_test_gtfs_calendar_date(
    service_id: str = "service_weekday",
    date_val: date = None,
    exception_type: int = 1,  # 1=added, 2=removed
    feed_id: str = "test_feed_001",
) -> GTFSCalendarDate:
    """Create a test GTFS calendar date exception."""
    if date_val is None:
        date_val = date.today() + timedelta(days=1)

    return GTFSCalendarDate(
        service_id=service_id,
        date=date_val,
        exception_type=exception_type,
        feed_id=feed_id,
    )


def create_test_gtfs_feed_info(
    feed_id: str = "test_feed_001",
    feed_url: str = "https://example.com/gtfs.zip",
    downloaded_at: datetime = None,
    feed_start_date: date = None,
    feed_end_date: date = None,
    stop_count: int = 1000,
    route_count: int = 50,
    trip_count: int = 5000,
) -> GTFSFeedInfo:
    """Create a test GTFS feed info."""
    if downloaded_at is None:
        downloaded_at = datetime.now(timezone.utc)
    if feed_start_date is None:
        feed_start_date = date.today()
    if feed_end_date is None:
        feed_end_date = date.today() + timedelta(days=365)

    return GTFSFeedInfo(
        feed_id=feed_id,
        feed_url=feed_url,
        downloaded_at=downloaded_at,
        feed_start_date=feed_start_date,
        feed_end_date=feed_end_date,
        stop_count=stop_count,
        route_count=route_count,
        trip_count=trip_count,
    )


def create_test_gtfs_stops() -> List[GTFSStop]:
    """Create a list of test stops for Munich area."""
    return [
        create_test_gtfs_stop(
            stop_id="de:09162:6",
            stop_name="München Hbf",
            stop_lat=48.1403,
            stop_lon=11.5583,
        ),
        create_test_gtfs_stop(
            stop_id="de:09162:10",
            stop_name="Marienplatz",
            stop_lat=48.1373,
            stop_lon=11.5755,
        ),
        create_test_gtfs_stop(
            stop_id="de:09162:20",
            stop_name="Ostbahnhof",
            stop_lat=48.1275,
            stop_lon=11.6050,
        ),
        create_test_gtfs_stop(
            stop_id="de:09162:30",
            stop_name="Sendlinger Tor",
            stop_lat=48.1340,
            stop_lon=11.5670,
        ),
        create_test_gtfs_stop(
            stop_id="de:09162:40",
            stop_name="Karlsplatz (Stachus)",
            stop_lat=48.1391,
            stop_lon=11.5650,
        ),
    ]


def create_test_gtfs_routes() -> List[GTFSRoute]:
    """Create a list of test routes."""
    return [
        create_test_gtfs_route(
            route_id="1-S1-1",
            route_short_name="S1",
            route_long_name="Freising - München - Ostbahnhof",
            route_type=2,
        ),
        create_test_gtfs_route(
            route_id="1-S2-1",
            route_short_name="S2",
            route_long_name="Erding - München - Petershausen",
            route_type=2,
        ),
        create_test_gtfs_route(
            route_id="1-U3-1",
            route_short_name="U3",
            route_long_name="Moosach - Fürstenried West",
            route_type=1,  # Metro
        ),
        create_test_gtfs_route(
            route_id="1-19-1",
            route_short_name="19",
            route_long_name="Berg am Laim - Pasing",
            route_type=0,  # Tram
        ),
    ]


def create_test_gtfs_trips() -> List[GTFSTrip]:
    """Create a list of test trips."""
    return [
        create_test_gtfs_trip(
            trip_id="trip_001",
            route_id="1-S1-1",
            service_id="service_weekday",
            trip_headsign="Ostbahnhof",
        ),
        create_test_gtfs_trip(
            trip_id="trip_002",
            route_id="1-S1-1",
            service_id="service_weekday",
            trip_headsign="Freising",
            direction_id=1,
        ),
        create_test_gtfs_trip(
            trip_id="trip_003",
            route_id="1-U3-1",
            service_id="service_weekday",
            trip_headsign="Fürstenried West",
        ),
    ]


def create_test_gtfs_stop_times() -> List[GTFSStopTime]:
    """Create a list of test stop times."""
    return [
        # Trip 001: München Hbf -> Marienplatz -> Ostbahnhof
        create_test_gtfs_stop_time(
            trip_id="trip_001",
            stop_id="de:09162:6",
            arrival_time=timedelta(hours=8, minutes=0),
            departure_time=timedelta(hours=8, minutes=2),
            stop_sequence=1,
        ),
        create_test_gtfs_stop_time(
            trip_id="trip_001",
            stop_id="de:09162:10",
            arrival_time=timedelta(hours=8, minutes=5),
            departure_time=timedelta(hours=8, minutes=6),
            stop_sequence=2,
        ),
        create_test_gtfs_stop_time(
            trip_id="trip_001",
            stop_id="de:09162:20",
            arrival_time=timedelta(hours=8, minutes=12),
            departure_time=timedelta(hours=8, minutes=12),
            stop_sequence=3,
        ),
        # Trip 002: Reverse direction
        create_test_gtfs_stop_time(
            trip_id="trip_002",
            stop_id="de:09162:20",
            arrival_time=timedelta(hours=9, minutes=0),
            departure_time=timedelta(hours=9, minutes=2),
            stop_sequence=1,
        ),
        create_test_gtfs_stop_time(
            trip_id="trip_002",
            stop_id="de:09162:6",
            arrival_time=timedelta(hours=9, minutes=15),
            departure_time=timedelta(hours=9, minutes=18),
            stop_sequence=2,
        ),
        # Overnight trip example (> 24h time)
        create_test_gtfs_stop_time(
            trip_id="trip_003",
            stop_id="de:09162:30",
            arrival_time=timedelta(hours=25, minutes=30),  # 1:30 AM next day
            departure_time=timedelta(hours=25, minutes=32),
            stop_sequence=1,
        ),
    ]


def create_test_gtfs_calendar_list() -> List[GTFSCalendar]:
    """Create a list of test service calendars."""
    return [
        create_test_gtfs_calendar(
            service_id="service_weekday",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
        ),
        create_test_gtfs_calendar(
            service_id="service_weekend",
            monday=False,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=True,
            sunday=True,
        ),
    ]
