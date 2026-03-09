## 2025-03-09 - [Reduce memory footprint of high-traffic dataclasses]
**Learning:** High-traffic dataclasses like DepartureInfo, TripUpdate, etc. can consume significant memory due to the overhead of the instance `__dict__`.
**Action:** Apply `@dataclass(slots=True)` to these dataclasses to prevent the creation of `__dict__`, potentially reducing the memory per object by around 80%.
