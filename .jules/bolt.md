## 2024-03-12 - [__slots__ Memory Optimization for High-Traffic Objects]
**Learning:** The memory usage of standard Python classes with a __dict__ can be significant for high-traffic objects like `ScheduledDeparture`. Applying `__slots__` reduces the memory footprint per object significantly (from 344 bytes to 112 bytes).
**Action:** Apply `__slots__` to all high-traffic data transfer objects and models used in bulk returns to prevent unnecessary memory consumption.
