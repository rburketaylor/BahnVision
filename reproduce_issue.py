from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from enum import Enum
import json

class ScheduleRelationship(Enum):
    SCHEDULED = "SCHEDULED"

@dataclass(slots=True)
class DepartureInfo:
    trip_id: str
    schedule_relationship: ScheduleRelationship = ScheduleRelationship.SCHEDULED
    alerts: Optional[List] = None

    def __post_init__(self) -> None:
        if self.alerts is None:
            self.alerts = []

    def to_dict(self) -> Dict:
        return {
            "trip_id": self.trip_id,
            "schedule_relationship": self.schedule_relationship.value,
            "alerts": self.alerts
        }

try:
    d = DepartureInfo(trip_id="123")
    print(f"Instance created: {d}")
    print(f"asdict: {asdict(d)}")
    print(f"to_dict: {d.to_dict()}")

    try:
        print(f"vars: {vars(d)}")
    except TypeError as e:
        print(f"vars failed as expected: {e}")

    # Test modification
    d.trip_id = "456"
    print(f"Modified: {d}")

except Exception as e:
    print(f"FAILED: {e}")
