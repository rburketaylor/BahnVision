## 2025-03-02 - [ScheduledDeparture Memory Optimization]
**Learning:** Adding `__slots__` to highly instantiated classes like `ScheduledDeparture` reduces memory overhead by preventing the creation of `__dict__` for each instance, achieving an approximate 21% reduction in memory usage per object (from ~416B to ~328B).
**Action:** Always consider `__slots__` for simple dataclasses or classes representing rows returned from bulk database queries to optimize memory consumption.
