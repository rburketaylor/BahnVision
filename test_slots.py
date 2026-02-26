import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.services.gtfs_schedule import ScheduledDeparture
from app.services.transit_data import DepartureInfo, RouteInfo, StopInfo
from app.services.gtfs_realtime import TripUpdate, VehiclePosition, ServiceAlert

def test_objects():
    print("Testing ScheduledDeparture...")
    try:
        dep = ScheduledDeparture(
            departure_time=datetime.now(timezone.utc),
            trip_headsign="Headsign",
            route_short_name="S1",
            route_long_name="Route Long",
            route_type=1,
            route_color="FF0000",
            stop_name="Stop Name",
            trip_id="trip_1",
            route_id="route_1",
            arrival_time=datetime.now(timezone.utc)
        )
        print(f"Created ScheduledDeparture: {dep.trip_id}")
        try:
            print(f"__dict__: {dep.__dict__}")
        except AttributeError:
            print("No __dict__ as expected (slots)")

        # Test attribute access
        print(f"route_short_name: {dep.route_short_name}")
    except Exception as e:
        print(f"Failed ScheduledDeparture: {e}")
        raise

    print("\nTesting DepartureInfo...")
    try:
        info = DepartureInfo(
            trip_id="trip_1",
            route_id="route_1",
            route_short_name="S1",
            route_long_name="Long",
            trip_headsign="Head",
            stop_id="stop_1",
            stop_name="Stop",
            scheduled_departure=datetime.now(timezone.utc)
        )
        print(f"Created DepartureInfo: {info.trip_id}")
        try:
            print(f"__dict__: {info.__dict__}")
        except AttributeError:
            print("No __dict__ as expected (slots)")

        # Test to_dict
        d = info.to_dict()
        print(f"to_dict keys: {list(d.keys())}")

        # Test from_dict
        info2 = DepartureInfo.from_dict(d)
        print(f"from_dict trip_id: {info2.trip_id}")

    except Exception as e:
        print(f"Failed DepartureInfo: {e}")
        raise

if __name__ == "__main__":
    test_objects()
