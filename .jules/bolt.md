## 2024-03-24 - [Memory optimization for high-traffic dataclasses]
**Learning:** Using `@dataclass(slots=True)` instead of regular `@dataclass` or `__slots__` reduces the memory footprint of objects from 344 bytes to 112 bytes in Python. Standard class `__slots__` provides similar memory reductions.
**Action:** Apply `slots=True` to high-traffic dataclasses, and `__slots__` to regular high-traffic classes like `TripUpdate`, `VehiclePosition`, `ServiceAlert` and `ScheduledDeparture` to reduce overall memory usage.
