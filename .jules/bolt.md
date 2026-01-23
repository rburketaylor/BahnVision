## 2025-05-23 - [Optimizing Complex Joins with Two-Step Queries]
**Learning:** Complex SQL joins with `OR` conditions across tables (e.g., `WHERE table1.col = x OR table2.col = x`) can severely hamper query planner performance by preventing effective index usage.
**Action:** Split the query into two steps: 1) Resolve the IDs from the smaller/joined table first. 2) Use an `IN` clause on the main table with the resolved IDs. This is often faster even with the overhead of an extra round-trip, as it allows simple index lookups on the large table.
