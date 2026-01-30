## 2025-05-23 - Two-Step Query Optimization for GTFS Departures
**Learning:** Joining `GTFSStop` to `GTFSStopTime` with an `OR` condition (`st.stop_id == id OR s.parent_station == id`) prevents efficient index usage on the massive `stop_times` table.
**Action:** Split into two steps: 1) Resolve all relevant stop IDs (parent & children) using a fast query on `gtfs_stops`. 2) Query `gtfs_stop_times` using `stop_id IN (...)`. This leverages the index on `stop_id` and is significantly faster despite the extra round-trip.
