## 2024-05-24 - Init
**Learning:** Initializing journal.
**Action:** Keep records of critical performance learnings.
## 2024-05-24 - Optimize memory footprint of dataclasses using slots
**Learning:** In Python 3.10+, adding `slots=True` to `@dataclass` decorators for high-traffic classes like `DepartureInfo`, `TripUpdate`, etc., eliminates the `__dict__` overhead, drastically reducing memory usage (~50% less) and slightly improving attribute access time.
**Action:** Always use `@dataclass(slots=True)` for data objects that are created frequently and do not need dynamic attribute assignments.
