## 2024-02-28 - [Memory footprint of high-traffic classes]
**Learning:** The `ScheduledDeparture` class in `gtfs_schedule.py` was instantiating thousands of objects during peak load. Using `__slots__` reduced memory usage from ~416B to ~328B (21% reduction per object) by preventing dynamic `__dict__` creation.
**Action:** For simple data transfer objects or high-volume models returned by database queries in the backend architecture, explicitly declare `__slots__` to limit memory usage.
