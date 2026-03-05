
## 2025-03-09 - [Reduce memory footprint of DataClasses via `__slots__`]
**Learning:** High-traffic data structures mapped directly via SQLAlchemy/cache often waste considerable memory on internal `__dict__` overhead. `DepartureInfo`, `TripUpdate`, `VehiclePosition`, `ServiceAlert`, `RouteInfo`, and `StopInfo` are created very frequently.
**Action:** Use `@dataclass(slots=True)` for high-frequency data objects to explicitly eliminate `__dict__` overhead, which reduced the memory usage from ~22MB to ~19MB per 100k instances in a synthetic test.
