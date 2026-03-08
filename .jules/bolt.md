
## 2024-03-22 - [Data Object Memory Optimization]
**Learning:** High-traffic data structures representing transit entities (like `ScheduledDeparture`) consume significantly more memory due to Python's default `__dict__` behavior (344 bytes vs 112 bytes). When querying thousands of departures (e.g., in a busy station over an entire day), this creates memory pressure and increases GC overhead.
**Action:** Always use `__slots__` for plain Python classes or `@dataclass(slots=True)` for dataclasses representing high-volume transit entities (departures, stops, routes) to dramatically reduce the memory footprint.
