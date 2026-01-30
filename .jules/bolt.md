## 2026-01-24 - GtfsRealtimeService Batching & Serialization

**Learning:** Generic reflection (like iterating `__dict__`) for serialization is costly in high-frequency loops. Explicit `to_dict` methods eliminate this overhead. Additionally, combining multiple logical cache updates (e.g., entity storage + index storage) into a single `mset_json` call reduces network round-trips.
**Action:** Implement explicit `to_dict` for all high-traffic data models and batch independent cache writes into single requests where possible.
