## 2026-02-26 - High-Volume DTO Optimization
**Learning:** High-frequency data objects (like GTFS `TripUpdate`, `VehiclePosition`, `ScheduledDeparture`) should use `__slots__` (either manually or via `@dataclass(slots=True)`) to significantly reduce memory overhead and improve attribute access speed in Python services handling large datasets.
**Action:** Always apply `__slots__` to transient data transfer objects created in loops or cached in bulk.
