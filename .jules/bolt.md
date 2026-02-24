# Bolt's Performance Journal ⚡

## 2024-05-23 - Dataclass Memory Optimization
**Learning:** High-frequency data objects (like `ScheduledDeparture`, `TripUpdate`, `VehiclePosition`) are instantiated in large numbers during feed processing and API responses. Standard Python classes and dataclasses use a `__dict__` for attribute storage, which has significant memory overhead.
**Action:** Use `__slots__` for manual classes and `@dataclass(slots=True)` for dataclasses to reduce memory footprint and improve attribute access speed for these high-volume objects.
