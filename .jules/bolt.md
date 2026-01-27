## 2025-02-14 - GTFS OR Join Optimization
**Learning:** Postgres/SQLAlchemy performance can degrade significantly when joining a large table (`gtfs_stop_times`) with a smaller one (`gtfs_stops`) using an `OR` condition across the join (`st.stop_id == id OR s.parent_station == id`).
**Action:** Split such queries into two steps: 1) Resolve the IDs from the smaller table first. 2) Query the large table using a simple `IN` clause with the resolved IDs. This enables efficient index usage.
