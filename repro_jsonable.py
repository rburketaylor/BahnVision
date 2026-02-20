
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import json
from fastapi.encoders import jsonable_encoder

@dataclass(slots=True)
class ServiceAlert:
    alert_id: str
    header_text: str

    def to_dict(self):
        return {"alert_id": self.alert_id, "header_text": self.header_text}

@dataclass(slots=True)
class DepartureInfo:
    trip_id: str
    alerts: Optional[List[ServiceAlert]] = None

    def to_dict(self):
        return {
            "trip_id": self.trip_id,
            "alerts": [a.to_dict() for a in self.alerts] if self.alerts else []
        }

def test_jsonable_encoder():
    print("Testing jsonable_encoder with slotted dataclasses...")
    alert = ServiceAlert(alert_id="1", header_text="Delay")
    dep = DepartureInfo(trip_id="trip1", alerts=[alert])

    try:
        # Test 1: Encoder on the dataclass instance directly (though code calls to_dict first)
        encoded = jsonable_encoder(dep)
        print(f"jsonable_encoder(dep) result: {encoded}")
    except Exception as e:
        print(f"Error in jsonable_encoder(dep): {e}")

    try:
        # Test 2: Encoder on the dict returned by to_dict
        d = dep.to_dict()
        encoded = jsonable_encoder(d)
        print(f"jsonable_encoder(dep.to_dict()) result: {encoded}")
    except Exception as e:
        print(f"Error in jsonable_encoder(dep.to_dict()): {e}")

if __name__ == "__main__":
    test_jsonable_encoder()
