## 2026-01-24 - GtfsRealtimeService Batching & Serialization

**Learning:** Generic reflection (like iterating `__dict__`) for serialization is costly in high-frequency loops. Explicit `to_dict` methods eliminate this overhead. Additionally, combining multiple logical cache updates (e.g., entity storage + index storage) into a single `mset_json` call reduces network round-trips.
**Action:** Implement explicit `to_dict` for all high-traffic data models and batch independent cache writes into single requests where possible.

## 2026-02-18 - Loop Invariant Code Motion (datetime.combine)

**Learning:** `datetime.combine(date, time)` is a surprisingly expensive operation to run inside a tight loop (e.g., iterating thousands of database rows). Pre-calculating the midnight timestamp outside the loop and reusing it resulted in an ~8x speedup for that specific operation.
**Action:** Identify loop invariants, especially object creation like `datetime` or `timedelta`, and hoist them out of critical data processing loops.
