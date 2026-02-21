## 2025-05-18 - [Memory] Use __slots__ for High-Frequency Data Objects
**Learning:** `ScheduledDeparture`, `DepartureInfo`, and other GTFS data objects are instantiated in very high volumes (thousands per request). Adding `__slots__` significantly reduces memory overhead and improves attribute access speed.
**Action:** When creating new high-frequency data classes, always use `__slots__` or `@dataclass(slots=True)`.
