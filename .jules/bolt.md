## 2024-05-19 - Use slots for dataclasses
**Learning:** High-traffic dataclasses like TripUpdate, VehiclePosition, ServiceAlert, DepartureInfo, RouteInfo, and StopInfo are repeatedly created during data parsing. By default, dataclasses use a `__dict__` to store attributes, which uses a significant amount of memory.
**Action:** Use `@dataclass(slots=True)` for such classes to eliminate `__dict__` overhead and significantly reduce memory usage.
