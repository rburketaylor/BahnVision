## 2025-05-23 - Split Queries for Better Indexing
**Learning:** Complex queries with `OR` conditions across joined tables often prevent database query planners from using indexes efficiently, especially on large tables like GTFS `stop_times`.
**Action:** When filtering a large table based on a relationship (e.g., "this stop OR its children"), fetch the related IDs in a separate, lightweight query first, then use an `IN` clause on the large table. This allows the database to use the primary index directly.
