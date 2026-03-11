## 2024-03-24 - [Optimize high-traffic dataclasses memory footprint]
**Learning:** Python's default dataclasses create a `__dict__` for every instance, causing unnecessary memory overhead. `slots=True` avoids this dynamically-sized dict allocation.
**Action:** Use `@dataclass(slots=True)` for high-traffic data objects (e.g., DepartureInfo, TripUpdate) to eliminate `__dict__` overhead and significantly reduce memory usage.
