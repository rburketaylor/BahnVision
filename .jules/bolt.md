## 2024-05-18 - [Reduce memory footprint of dataclasses]
**Learning:** Using `__slots__` or `@dataclass(slots=True)` can reduce the memory footprint of classes by eliminating the `__dict__` overhead. This provides a ~67% to ~86% reduction in object size, which significantly improves performance when caching thousands of schedule departures, trip updates, vehicle positions, etc.
**Action:** When defining high-traffic dataclasses (e.g. models, schedules, updates) that have fixed fields and no need for dynamic attribute assignment, explicitly use `__slots__` or `@dataclass(slots=True)`.
