import sys
from dataclasses import dataclass
from datetime import datetime

@dataclass
class DepartureInfoNoSlots:
    trip_id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    trip_headsign: str
    stop_id: str
    stop_name: str
    scheduled_departure: datetime

@dataclass(slots=True)
class DepartureInfoSlots:
    trip_id: str
    route_id: str
    route_short_name: str
    route_long_name: str
    trip_headsign: str
    stop_id: str
    stop_name: str
    scheduled_departure: datetime

no_slots = DepartureInfoNoSlots("a", "b", "c", "d", "e", "f", "g", datetime.now())
slots = DepartureInfoSlots("a", "b", "c", "d", "e", "f", "g", datetime.now())

print("No slots:", sys.getsizeof(no_slots) + sys.getsizeof(no_slots.__dict__))
print("Slots:", sys.getsizeof(slots))
