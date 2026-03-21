## 2024-05-24 - High-Traffic Dataclass Memory Overhead
**Learning:** Standard transit dataclasses (like DepartureInfo, TripUpdate) use ~344 bytes per instance due to `__dict__` overhead. In Python 3.10+, adding `slots=True` to the `@dataclass` decorator significantly reduces memory footprint to ~48-96 bytes, which is even more efficient than standard class `__slots__` (112 bytes).
**Action:** Always use `@dataclass(slots=True)` for high-traffic data objects instantiated frequently during parsing or responding to requests.
