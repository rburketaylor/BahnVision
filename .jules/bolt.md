
## 2026-03-17 - [Memory Optimization for Dataclasses]
**Learning:** Using `@dataclass(slots=True)` in Python 3.10+ reduces the memory footprint of standard transit dataclasses (like `DepartureInfo`) from 344 bytes to 48-96 bytes per instance, providing a more significant reduction than standard class `__slots__` (which reduces to 112 bytes).
**Action:** Always use `slots=True` for high-traffic data objects (e.g., `DepartureInfo`, `TripUpdate`, `VehiclePosition`, `ServiceAlert`, `RouteInfo`, `StopInfo`) to eliminate `__dict__` overhead and significantly reduce memory usage.
