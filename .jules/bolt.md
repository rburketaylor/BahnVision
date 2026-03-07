
## 2024-05-28 - [Memory optimization for high-traffic dataclasses]
**Learning:** High-traffic data structures parsing GTFS feeds (like TripUpdate, DepartureInfo) can create significant memory overhead due to `__dict__` creation for each instance.
**Action:** Always use `@dataclass(slots=True)` for data objects created in high volumes during stream processing to reduce memory allocation per instance.
