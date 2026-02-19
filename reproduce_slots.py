from datetime import datetime
import sys

class ScheduledDeparture:
    """Represents a scheduled departure from a stop with concrete datetimes."""

    # Optimization: Use __slots__ to reduce memory usage per instance and improve
    # attribute access speed. This is crucial as thousands of these objects are created.
    __slots__ = (
        "departure_time",
        "trip_headsign",
        "route_short_name",
        "route_long_name",
        "route_type",
        "route_color",
        "stop_name",
        "trip_id",
        "route_id",
        "arrival_time",
    )

    def __init__(
        self,
        departure_time,
        trip_headsign,
        route_short_name,
        route_long_name,
        route_type,
        route_color,
        stop_name,
        trip_id,
        route_id,
        arrival_time=None,
    ):
        self.departure_time = departure_time
        self.trip_headsign = trip_headsign
        self.route_short_name = route_short_name
        self.route_long_name = route_long_name
        self.route_type = route_type
        self.route_color = route_color
        self.stop_name = stop_name
        self.trip_id = trip_id
        self.route_id = route_id
        self.arrival_time = arrival_time or departure_time

try:
    dep = ScheduledDeparture(
        departure_time=datetime.now(),
        trip_headsign="Headsign",
        route_short_name="Short",
        route_long_name="Long",
        route_type=1,
        route_color="FFFFFF",
        stop_name="Stop",
        trip_id="Trip",
        route_id="Route",
    )
    print("Instance created successfully")
    print(f"trip_id: {dep.trip_id}")

    try:
        print(f"__dict__: {dep.__dict__}")
    except AttributeError:
        print("__dict__ not present (expected)")

    # Test setting a new attribute
    try:
        dep.new_attr = "fail"
    except AttributeError:
        print("Cannot set new attribute (expected)")

except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
