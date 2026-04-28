# Efficiency Optimizations Compilation

**Date:** 2026-04-28
**Source plans:** archived under `docs/plans/efficiency-optimizations/archive/`

- `archive/efficiency-optimizations-gpt.md`
- `archive/efficiency-optimizations-gemini.md`
- `archive/efficiency-optimizations-kimi.md`
- `archive/efficiency-optimizations-glm.md`

## Purpose

This document consolidates the four efficiency optimization plans into one execution-oriented roadmap. It preserves the repeated high-confidence recommendations, separates verified current-state observations from recommendations, and flags items that need measurement or design review before implementation.

## Verified Current State

The following current-state claims were checked against the codebase while compiling the source plans:

- The static GTFS importer truncates final tables before loading and uses `TRUNCATE TABLE ... CASCADE` in `backend/app/services/gtfs_feed.py`.
- The importer repeatedly runs `ALTER TABLE ... SET UNLOGGED` or `SET LOGGED` during import setup in `backend/app/services/gtfs_feed.py`.
- `stop_times.txt` is extracted to a temporary file before batched Polars reads, and `stop_times` batches default to `500_000` rows in `backend/app/services/gtfs_feed.py`.
- `gtfs_stop_times` currently has an integer surrogate primary key, `arrival_time` and `departure_time` as PostgreSQL `INTERVAL`, and a per-row `feed_id` in `backend/app/models/gtfs.py`.
- `gtfs_stops`, `gtfs_routes`, `gtfs_trips`, `gtfs_calendar`, and `gtfs_calendar_dates` also carry `feed_id`; some static GTFS tables carry `created_at` or `updated_at` in `backend/app/models/gtfs.py`.
- `gtfs_stops.stop_lat` and `gtfs_stops.stop_lon` use `Numeric(9, 6)` in `backend/app/models/gtfs.py`.
- `realtime_station_stats` and `realtime_station_stats_daily` use surrogate `id` primary keys and separate uniqueness constraints in `backend/app/persistence/models.py`.
- `realtime_station_stats.stop_id` has `ondelete="cascade"` to `gtfs_stops`, so truncating static stops with cascade can remove retained realtime history.
- Heatmap aggregation paths still perform second-pass queries for selected stations and route-type breakdowns in `backend/app/services/heatmap_service.py`.
- Route type mapping is fetched from `gtfs_routes` during harvester work in `backend/app/services/gtfs_realtime_harvester.py`.
- Departure cache keys include `from_time.isoformat()` with full precision in `backend/app/services/transit_data.py`.
- Stop search uses `ILIKE '%query%'` in `backend/app/services/gtfs_schedule.py`.
- `docker-compose.yml` sets Postgres memory to `512m`, backend memory to `768m`, and uses `valkey/valkey:latest`.

## Consolidated Priorities

| Priority | Workstream                                                                       | Why It Comes First                                                                                                                                    |
| -------- | -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0       | Preserve realtime history during GTFS imports                                    | Current `TRUNCATE ... CASCADE` can erase retained heatmap/realtime aggregates. This is a correctness and data-retention risk, not just a speed issue. |
| P0       | Add post-import `ANALYZE` and baseline performance instrumentation               | Cheap, low-risk changes that improve planner quality and make later optimizations measurable.                                                         |
| P1       | Compact high-volume GTFS schema                                                  | Repeated across plans; highest storage impact comes from `feed_id`, `INTERVAL` times, timestamps, and surrogate keys on large tables.                 |
| P1       | Make import pipeline atomic and less disk-heavy                                  | Staging imports reduce failed-import risk; streaming and configurable batch sizing reduce temp disk and throughput bottlenecks.                       |
| P1       | Improve heatmap query shape and indexes                                          | Repeated across plans; current query paths do unnecessary round trips and need indexes aligned with filters.                                          |
| P2       | Cache static GTFS metadata used at runtime                                       | Route type maps, active service IDs, and rounded departure cache keys reduce repeated DB work.                                                        |
| P2       | Improve stop search and departure lookup indexes                                 | `pg_trgm`, parent station, and covering departure indexes directly target user-facing query paths.                                                    |
| P3       | Bound cache memory, pin infrastructure versions, and consider serializer changes | Useful resilience/reproducibility work, but lower direct impact than schema/import/query work.                                                        |

## P0: Correctness And Measurement Baseline

### 1. Replace destructive GTFS refresh with a staged import

**Recommendation:** Replace truncate-before-load with a staging-table workflow:

1. Download and parse the new feed into staging tables.
2. Validate required files, row counts, key relationships, and import metadata.
3. Swap or truncate-and-insert final static GTFS tables only after staging succeeds.
4. Preserve old final tables if staging fails.

**Rationale:** The GPT plan identified the highest-risk issue: final GTFS tables are truncated before the replacement feed is known to be valid. Because realtime stats cascade from `gtfs_stops`, the current refresh can also erase retained heatmap history.

**Implementation notes:**

- Remove `CASCADE` from GTFS truncation.
- Drop the realtime-stats-to-`gtfs_stops` cascade dependency or replace it with explicit orphan cleanup after successful import.
- Keep one active static feed as the initial assumption; do not introduce multi-feed semantics unless product requirements change.
- Add orphan cleanup as a deliberate maintenance step, not an implicit side effect of static refresh.

**Tests:**

- Failed import leaves previous GTFS data intact.
- Failed import leaves realtime stats and daily stats intact.
- Successful import removes only explicitly orphaned realtime rows according to the chosen retention rule.
- Import code no longer emits `TRUNCATE ... CASCADE`.

### 2. Run `ANALYZE` after successful imports

**Recommendation:** Run `ANALYZE` on reloaded static GTFS tables after final swap/index recreation:

- `gtfs_stop_times`
- `gtfs_trips`
- `gtfs_stops`
- `gtfs_routes`
- `gtfs_calendar`
- `gtfs_calendar_dates`
- `gtfs_feed_info`

**Rationale:** Large truncates and reloads leave planner statistics stale. This is low risk and should be implemented before more speculative tuning.

**Tests:**

- Unit or integration test verifies the import path invokes `ANALYZE` after final load.
- Import benchmark records query timings immediately after import.

### 3. Add request-level API timing instrumentation

**Recommendation:** Implement global FastAPI request duration metrics and `Server-Timing` output, building on the existing performance profiling plan.

**Rationale:** The Kimi plan correctly notes that some metrics exist, but global request-level timing is still missing. This should happen before larger query rewrites so improvements can be measured consistently.

**Implementation notes:**

- Add a Prometheus histogram such as `bahnvision_api_request_duration_seconds`.
- Add global `Server-Timing: app;dur=...` response timing.
- Preserve existing endpoint-specific timing headers where present.
- Ensure route labels avoid high-cardinality raw paths.

**Tests:**

- Middleware adds `Server-Timing` on normal and error responses.
- `/metrics` exposes the request histogram.
- Existing heatmap timing behavior remains compatible.

## P1: Schema Compaction

### 4. Store GTFS stop times as integer seconds

**Recommendation:** Replace `arrival_time` and `departure_time` `INTERVAL` columns with integer seconds since service midnight.

**Rationale:** All plans that discuss high-volume table size point to `gtfs_stop_times` as the largest storage target. Integer seconds also handle GTFS times beyond 24:00:00 naturally.

**Implementation notes:**

- Proposed columns: `arrival_seconds` and `departure_seconds`, nullable integer.
- Convert GTFS `HH:MM:SS` strings during import.
- Update departure queries to compare integer second ranges rather than intervals.
- Keep API response semantics unchanged by converting to the existing response time representation at service boundaries.

**Tests:**

- Conversion handles null values and times beyond 24 hours.
- Departure lookup behavior matches current results.
- Migration backfills existing interval values accurately.

### 5. Remove unused static GTFS per-row metadata

**Recommendation:** Drop per-row `feed_id`, `created_at`, and `updated_at` from static GTFS data tables where the active-feed-only assumption holds. Keep feed-level metadata in `gtfs_feed_info`.

**Rationale:** The source plans converge on this as a large space saving, especially for `gtfs_stop_times.feed_id`.

**Initial scope:**

- Drop `feed_id` from `gtfs_stop_times` first.
- Then drop `feed_id` from remaining static GTFS tables if no code path needs row-level feed filtering.
- Drop `created_at` and `updated_at` from fully replaced static tables.

**Required code audit before migration:**

- Search import, schedule, and API code for row-level `feed_id` reads or filters.
- Confirm docs do not promise multi-feed static queries.

**Tests:**

- Import still succeeds without populating dropped columns.
- Schedule/departure/search endpoints return unchanged payloads.
- Migrations downgrade cleanly or document irreversible size-optimization choices.

### 6. Replace surrogate keys with composite keys on high-volume tables

**Recommendation:** Use natural composite keys where they match domain uniqueness:

- `gtfs_stop_times`: `(trip_id, stop_sequence)`
- `realtime_station_stats_daily`: `(stop_id, date)`
- `realtime_station_stats`: either keep the current unique key plus surrogate id until route-type semantics are redesigned, or migrate to `(stop_id, bucket_start, bucket_width_minutes, route_type_key)`.

**Rationale:** Gemini and Kimi both recommend removing surrogate keys for storage savings. The realtime hourly table needs more care because `route_type` is nullable today and uses `postgresql_nulls_not_distinct=True`.

**Implementation notes:**

- For `gtfs_stop_times`, confirm no ORM relationship, fixture, or test expects `GTFSStopTime.id`.
- For daily stats, confirm no code references `RealtimeStationStatsDaily.id`.
- For hourly stats, avoid making nullable `route_type` part of a primary key directly. Use a sentinel column or retain the existing uniqueness approach until combined/all-route semantics are clarified.

**Tests:**

- Migration preserves row uniqueness.
- Bulk upsert conflict targets are updated.
- ORM writes and tests no longer depend on surrogate ids.

### 7. Change stop coordinates to floating point

**Recommendation:** Change `gtfs_stops.stop_lat` and `gtfs_stops.stop_lon` from `Numeric(9, 6)` to PostgreSQL `double precision`.

**Rationale:** Six-decimal GTFS coordinates do not need arbitrary precision. Heatmap grid and nearby-stop calculations benefit from native float operations.

**Tests:**

- Migration preserves coordinate precision within an agreed tolerance.
- Nearby stops and heatmap coordinate outputs remain stable within tolerance.

## P1: Import Throughput And Disk Usage

### 8. Make `stop_times` batch size configurable

**Recommendation:** Add `GTFS_STOP_TIMES_BATCH_SIZE`, defaulting conservatively to the current `500_000` or a measured safe value.

**Rationale:** Gemini, Kimi, and GLM all suggest larger batches, but `docker-compose.yml` caps backend memory at `768m`. A fixed jump to 1.5M or 2M rows risks memory pressure.

**Implementation notes:**

- Validate the configured value and log it at import start.
- Benchmark `500_000`, `1_000_000`, `1_500_000`, and `2_000_000` under local Docker limits.
- Keep the queue/backpressure threshold tied to semaphore size and observed memory.

**Tests:**

- Invalid env var values fall back or fail clearly.
- Import path passes the configured batch size into Polars.

### 9. Reduce temporary file I/O

**Recommendation:** Stream smaller GTFS tables from memory to PostgreSQL COPY, and remove avoidable intermediate files.

**Rationale:** Several plans point out that `_copy_polars_df` writes DataFrames to disk before COPY. This is unnecessary for smaller tables.

**Implementation notes:**

- Use an in-memory buffer for smaller tables only.
- Keep memory-aware behavior for `stop_times`.
- Investigate whether `stop_times.txt` can be streamed or buffered in a way compatible with Polars without extracting the whole file first. Treat this as separate from the small-table optimization.

**Tests:**

- COPY behavior remains identical for optional columns and nested ZIP paths.
- Temp files are cleaned up on success and failure.

### 10. Manage table persistence and indexes deliberately

**Recommendation:** Stop repeatedly altering table logging mode when the desired state is already set. Set default persistence through migrations and only alter when the current setting differs.

**Rationale:** GPT identifies repeated `ALTER TABLE ... SET UNLOGGED/LOGGED` as avoidable work. Existing import code does this every refresh.

**Related recommendations:**

- Drop and recreate relevant indexes around large imports only when that measurably helps.
- Consider dropping more indexes than just `gtfs_stop_times` during full replacement, such as `gtfs_trips(service_id)` and stop-name indexes, if benchmarks support it.
- Recreate indexes after final load, then run `ANALYZE`.

**Tests:**

- Import works when tables are already in the desired persistence mode.
- Indexes and constraints are restored after successful imports.
- Failure paths do not leave final tables without required indexes.

### 11. Add GTFS archive cleanup

**Recommendation:** Add `GTFS_FEED_ARCHIVE_RETENTION_COUNT`, defaulting to `2`, and delete older downloaded ZIPs plus stale `.part` files after a successful import.

**Rationale:** GPT and GLM both identify unbounded feed archive growth. This is a low-risk disk cleanup if it runs after a successful import.

**Tests:**

- Keeps the configured number of newest archives.
- Deletes stale partial downloads.
- Does not delete the current archive before successful import completion.

## P1: Heatmap Query Efficiency

### 12. Consolidate heatmap aggregation queries

**Recommendation:** Replace two-pass heatmap aggregation with a single PostgreSQL query that returns station totals and route/transport breakdowns together.

**Rationale:** Gemini and Kimi both identify second-pass heatmap queries. Verified code has a selected-station second pass for route-type breakdowns.

**Implementation options:**

- Use JSON aggregation (`jsonb_object_agg`) grouped by station.
- Use window functions to pick representative/top stations and aggregate breakdowns in the same query shape.
- For daily summaries, aggregate `by_route_type` JSONB in SQL where feasible instead of fetching selected station rows and aggregating in Python.

**Tests:**

- Data parity with existing heatmap responses for short ranges and daily-summary ranges.
- Route-type filters return identical totals and breakdowns.
- Query plans are captured before and after on realistic data.

### 13. Add heatmap-oriented indexes

**Recommendation:** Add indexes aligned with heatmap filters:

- Short-range hourly stats: `(bucket_start, bucket_width_minutes, route_type)` or a measured variant including `stop_id`.
- Daily stats: review whether `(date)` and `(stop_id, date)` are enough for current daily query shapes after consolidation.

**Rationale:** Current hourly indexes cover `(stop_id, bucket_start)` and `(bucket_start)`, but heatmap filters also include `bucket_width_minutes` and optionally `route_type`.

**Tests:**

- `EXPLAIN ANALYZE` confirms index usage on representative short-range heatmap queries.
- Insert/upsert overhead remains acceptable for harvester writes.

### 14. Define historical realtime retention and rollups

**Recommendation:** Add an explicit historical storage policy for realtime/heatmap data so long-term history stays searchable without keeping all detail forever.

**Proposed tiers:**

- Recent detail: keep hourly `realtime_station_stats` for detailed heatmap, debugging, and short-range trend queries.
- Warm history: keep daily per-stop/per-transport summaries for 7d/30d and historical heatmap views.
- Cold history: optionally keep weekly or monthly summaries for long-term trend views if product requirements need multi-month or multi-year history.
- Retention: delete or archive hourly rows only after daily summaries for those rows have been generated, validated, and made queryable.

**Rationale:** The current schema already compresses raw GTFS-RT observations into hourly aggregates and daily summaries, but the plan should state the retention contract explicitly. Without this, preserving realtime history during GTFS imports can gradually grow the database without a clear compaction policy.

**Implementation notes:**

- Define a retention window for hourly rows, such as 30 or 90 days, based on the longest endpoint that needs hourly precision.
- Add a validation step before purging hourly rows: daily row count coverage, total trip counts, delay totals, cancellation totals, and route-type totals must match the source hourly window.
- Document endpoint precision: which endpoints can use daily/monthly summaries and which require hourly data.
- Prefer date partitioning for `realtime_station_stats` if retention deletes become expensive.
- Keep station identifiers stable enough that historical summaries remain searchable after static GTFS refreshes. If a stop disappears from the current feed, historical queries should still be able to resolve at least the stored stop id and last-known display metadata.

**Tests:**

- Daily summaries match hourly source totals before hourly deletion.
- Historical heatmap queries still work after source hourly rows are purged.
- Deleted or changed static stops do not make historical summaries unsearchable.
- Retention jobs do not delete incomplete or unvalidated daily ranges.

### 15. Choose the route-type daily summary storage shape

**Recommendation:** Decide whether daily route-type history should stay compact in JSONB, move to normalized rows, or use a hybrid model.

**Options:**

- JSONB only: keep the current `by_route_type` JSONB on `realtime_station_stats_daily`. This is compact and simple, but harder to index for route-type-heavy historical searches.
- Normalized table: store rows like `(stop_id, date, transport_type, trip_count, delayed_count, cancelled_count, on_time_count, total_delay_seconds)`. This is more searchable and indexable, but creates more rows and indexes.
- Hybrid: keep compact daily station totals in `realtime_station_stats_daily` and add normalized route-type rows only for filter-heavy historical queries.

**Rationale:** GPT recommends normalized daily route-type summaries. Current daily summaries store `by_route_type` as JSONB. Normalization may improve filtered 7d/30d heatmap queries, but it should be treated as a storage-shape decision rather than only a query optimization.

**Decision:** Defer the final storage shape until query consolidation, indexing, and the historical retention policy have been measured.

## P2: Runtime Cache And Query Optimizations

### 16. Cache `route_id -> route_type` for the harvester

**Recommendation:** Cache route type mappings in memory or Valkey and invalidate on successful GTFS import.

**Rationale:** The harvester fetches the mapping from `gtfs_routes`; route types are static across a feed. All source plans that discuss harvester efficiency include this idea.

**Implementation notes:**

- Prefer a small in-process cache tied to active feed identity unless multi-process consistency requires Valkey.
- If stored in Valkey, use a versioned key containing the active feed id.
- Replace private capability checks such as `hasattr(self._cache, "set_json")` with a clearer cache service interface where touched.

**Tests:**

- Cache invalidates after GTFS import.
- Harvester still works when cache is unavailable.

### 17. Cache active service IDs

**Recommendation:** Cache `get_active_service_ids(query_date)` results until the next day or next GTFS import.

**Rationale:** Calendar data is static between imports and is used by departure queries.

**Tests:**

- Cache key includes service date.
- Import invalidation clears stale service IDs.
- Calendar exception behavior is preserved.

### 18. Normalize departure cache keys

**Recommendation:** Round `from_time` in departure cache keys to a minute or five-minute bucket.

**Rationale:** Full-precision `from_time.isoformat()` creates low-reuse cache keys. Rounding increases cache hits for repeated departure lookups.

**Implementation notes:**

- Use one-minute buckets initially to limit behavioral drift.
- Include the rounded query time in logs or metrics for debugging.
- Confirm response semantics are acceptable with existing short TTLs.

**Tests:**

- Calls within the same bucket share cache keys.
- Calls across bucket boundaries do not incorrectly share results.

### 19. Batch or pipeline trip-marker cache updates

**Recommendation:** Review the GTFS-RT trip-marker update path and batch/pipeline Lua or Valkey operations where still per-trip.

**Rationale:** GPT highlights Valkey round trips during trip-marker updates. The code already has some atomic and fallback paths, so this should be benchmark-driven rather than assumed.

**Decision:** Investigate after route-type caching and import/schema work.

## P2: User-Facing Query Indexes

### 20. Add `pg_trgm` stop search index

**Recommendation:** Enable `pg_trgm` and add a GIN trigram index on `gtfs_stops.stop_name`.

**Rationale:** Stop search uses `ILIKE '%query%'`, which does not benefit from a normal btree index for substring search.

**Tests:**

- Migration enables `pg_trgm` safely.
- Search results remain unchanged.
- `EXPLAIN ANALYZE` confirms the trigram index is used for representative queries.

### 21. Add parent-station and departure lookup indexes

**Recommendation:** Add indexes for known lookup paths:

- `gtfs_stops(parent_station)` for child-stop departure lookups.
- `gtfs_stop_times(stop_id, departure_seconds)` after integer time migration.
- Consider a covering departure index including `trip_id` and `arrival_seconds`.

**Rationale:** GPT and GLM both call out station/departure lookup indexes. The exact index shape should follow the post-migration query shape.

**Tests:**

- Departure endpoint query plans improve or remain stable.
- Index build time during import remains acceptable.

### 22. Consider `earthdistance` for nearby stops

**Recommendation:** Defer unless nearby-stop accuracy or performance is a demonstrated issue.

**Rationale:** GLM suggests `earthdistance`, but it adds a PostgreSQL extension and the current bounding-box path may be sufficient for the current feature surface.

## P3: Resilience, Serialization, And Infrastructure

### 23. Bound the fallback cache

**Recommendation:** Add max-size or approximate LRU eviction to the in-memory fallback cache.

**Rationale:** If Valkey is unavailable, large cached payloads can accumulate in process memory. This is especially relevant for heatmap responses.

**Tests:**

- Cache evicts old entries when over size.
- TTL cleanup still works.
- Stale-while-revalidate behavior is preserved.

### 24. Evaluate faster JSON serialization

**Recommendation:** Consider `orjson` only after measuring serialization as a bottleneck.

**Rationale:** It may help large heatmap payloads, but it adds a dependency and can subtly change serialization behavior.

**Decision:** Defer until request timing and profiling artifacts show JSON serialization cost.

### 25. Pin Valkey and review container memory

**Recommendation:** Pin `valkey/valkey` to a specific version and review memory limits for import-heavy local/prod profiles.

**Rationale:** `latest` is a reproducibility risk. Postgres `512m` and backend `768m` may limit large imports or larger Polars batch sizes.

**Implementation notes:**

- Pin Valkey before changing cache behavior so test environments remain stable.
- Consider a separate import profile or documented override for memory-intensive GTFS imports.

## Risky Or Deferred Proposals

### Binary COPY format

GLM recommends PostgreSQL binary COPY and suggests Polars Arrow IPC maps cleanly to it. This should not be accepted without a spike. PostgreSQL binary COPY has a specific wire format; Arrow IPC is not a direct drop-in source for `asyncpg.copy_to_table`.

**Decision:** Defer. Benchmark CSV COPY improvements first through staging, reduced temp I/O, larger batches, and post-load indexing.

### Parallel `CREATE INDEX CONCURRENTLY`

GLM recommends parallel concurrent index creation. This has transactional and operational complexity:

- `CREATE INDEX CONCURRENTLY` cannot run inside a normal transaction block.
- Parallel index builds can increase memory and I/O contention.
- The import process already owns a replacement window for static tables, so non-concurrent builds may be faster and simpler.

**Decision:** Defer until sequential index build time is measured after schema compaction.

### Raising stop-times backpressure threshold

GLM recommends increasing the pending task threshold from 6 to 9-12. This may improve throughput, but memory is already constrained by Docker limits.

**Decision:** Tie backpressure changes to benchmark data and the configurable batch-size work.

### `synchronous_commit = off`

GLM recommends disabling synchronous commit during import. This may be reasonable for rebuildable unlogged static data, but it should be scoped carefully and documented.

**Decision:** Consider only after staged import is in place and crash recovery behavior is clear.

## Suggested Execution Sequence

### Phase 1: Safety and observability

1. Replace destructive import flow with staged import or at minimum remove cascade side effects and protect realtime history.
2. Add post-import `ANALYZE`.
3. Add request-level API timing metrics and global `Server-Timing`.
4. Add import benchmark output for phase timings, final table sizes, and temp disk usage.

### Phase 2: Low-risk import cleanup

1. Add GTFS archive retention cleanup.
2. Add configurable stop-times batch size.
3. Stream smaller COPY tables from memory.
4. Avoid repeated persistence-mode `ALTER TABLE` when no change is needed.

### Phase 3: Schema compaction

1. Migrate stop times to integer seconds.
2. Remove `gtfs_stop_times.feed_id`.
3. Remove unused static GTFS metadata from other tables.
4. Convert stop coordinates to float.
5. Remove surrogate ids where the code audit confirms low blast radius.

### Phase 4: Query optimization

1. Add `pg_trgm` stop search index.
2. Add parent-station and post-migration departure lookup indexes.
3. Consolidate heatmap aggregation queries.
4. Add or adjust heatmap covering indexes after query consolidation.
5. Define historical realtime retention windows and rollup validation.
6. Re-evaluate daily route-type summary storage shape.

### Phase 5: Runtime caching and infrastructure

1. Cache route type maps with import invalidation.
2. Cache active service IDs with import/day invalidation.
3. Round departure cache keys.
4. Bound fallback cache.
5. Pin Valkey and document import memory profiles.

## Validation Matrix

| Area                 | Required Validation                                                                                                                     |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Import safety        | Failed imports preserve prior GTFS data and realtime history.                                                                           |
| Import speed         | Benchmark download, staging load, final swap, index build, analyze, total import time, peak temp disk, and final table size.            |
| Schema migration     | `alembic upgrade head` and `alembic downgrade -1` where feasible; fixture updates; row-count and parity checks.                         |
| Departure API        | Same response shape and ordering before/after integer-time and index changes.                                                           |
| Stop search          | Same search results; faster representative `%query%` searches with trigram index.                                                       |
| Heatmap              | Same totals and route/transport breakdowns for short and long ranges; measured query plan improvement.                                  |
| Historical retention | Daily or monthly rollups remain queryable after detailed hourly rows are purged; validation prevents deleting incomplete source ranges. |
| Harvester            | Same aggregate counts; fewer repeated DB queries; cache-unavailable fallback works.                                                     |
| Observability        | Metrics and `Server-Timing` available on representative API responses and visible in `/metrics`.                                        |

## Open Decisions

- Should static GTFS refresh preserve all historical realtime stats indefinitely, or should it delete orphaned stats after a retention window?
- Is one active static feed a permanent product assumption, or should schema compaction preserve an easy path back to multi-feed support?
- What is the largest expected GTFS feed under local Docker limits and under production limits?
- Should route-type daily summaries remain JSONB, move to a normalized table, or be generated into both forms?
- Are nearby-stop accuracy issues important enough to justify a PostgreSQL extension such as `earthdistance`?
