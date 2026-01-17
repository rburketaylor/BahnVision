## 2025-02-14 - GTFS-RT Cache Optimization
**Learning:** The GTFS-RT service was using a 2-step cache retrieval pattern (get index -> mget data) for trip updates. This doubled the number of cache round-trips for high-frequency operations. Storing the list of updates directly under the stop key reduced cache calls by 50% for this operation.
**Action:** When caching collections where items are small and always retrieved together (like trip updates for a stop), prefer storing the list directly rather than using a secondary index + individual keys.
