from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

# Mock imports
class ScheduleRelationship(Enum):
    SCHEDULED = "SCHEDULED"
    SKIPPED = "SKIPPED"
    NO_DATA = "NO_DATA"
    UNSCHEDULED = "UNSCHEDULED"
    CANCELED = "CANCELED"

# 1. Test ScheduledDeparture (Manual Slots)
class ScheduledDeparture:
    """Represents a scheduled departure from a stop with concrete datetimes."""

    # Optimization: Use __slots__ to reduce memory usage for high-volume objects
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
        departure_time: datetime,
        trip_headsign: str,
        route_short_name: str,
        route_long_name: str,
        route_type: int,
        route_color: Optional[str],
        stop_name: str,
        trip_id: str,
        route_id: str,
        arrival_time: Optional[datetime] = None,
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

# 2. Test DepartureInfo (Dataclass Slots)
@dataclass(slots=True)
class DepartureInfo:
    """Combined departure information with real-time updates"""

    trip_id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    trip_headsign: str
    stop_id: str
    stop_name: str
    scheduled_departure: datetime
    scheduled_arrival: Optional[datetime] = None
    real_time_departure: Optional[datetime] = None
    real_time_arrival: Optional[datetime] = None
    departure_delay_seconds: Optional[int] = None
    arrival_delay_seconds: Optional[int] = None
    schedule_relationship: ScheduleRelationship = ScheduleRelationship.SCHEDULED
    vehicle_id: Optional[str] = None
    vehicle_position: Optional[Dict] = None
    alerts: Optional[List] = None  # ServiceAlert list

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []

    def to_dict(self) -> Dict:
        return {
            "trip_id": self.trip_id,
            "route_id": self.route_id,
            "alerts": self.alerts,
        }

def test_manual_slots():
    print("Testing ScheduledDeparture...")
    now = datetime.now(timezone.utc)
    dep = ScheduledDeparture(
        departure_time=now,
        trip_headsign="Headsign",
        route_short_name="S1",
        route_long_name="Long Name",
        route_type=1,
        route_color="FF0000",
        stop_name="Stop",
        trip_id="T1",
        route_id="R1"
    )
    print(f"Created: {dep.trip_id}")
    try:
        dep.new_attr = "fail"
        print("Error: Should not allow new attribute")
    except AttributeError:
        print("Success: Prevented new attribute")

def test_dataclass_slots():
    print("Testing DepartureInfo...")
    now = datetime.now(timezone.utc)
    info = DepartureInfo(
        trip_id="T1",
        route_id="R1",
        route_short_name="S1",
        route_long_name="Long",
        trip_headsign="Head",
        stop_id="S1",
        stop_name="Stop",
        scheduled_departure=now
    )
    print(f"Created: {info.trip_id}, Alerts: {info.alerts}")
    try:
        info.new_attr = "fail"
        print("Error: Should not allow new attribute")
    except AttributeError:
        print("Success: Prevented new attribute")

    d = info.to_dict()
    print(f"Dict: {d}")

if __name__ == "__main__":
    test_manual_slots()
    test_dataclass_slots()
