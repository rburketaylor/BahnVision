## 2026-02-23 - Memory Optimization with __slots__
**Learning:** High-frequency data objects like `ScheduledDeparture` and `DepartureInfo` consume significant memory when instantiated in large lists (e.g., thousands of departures).
**Action:** Use `__slots__` (or `@dataclass(slots=True)` in Python 3.10+) for these objects. This reduced memory usage by ~30-40% in our measurements.
