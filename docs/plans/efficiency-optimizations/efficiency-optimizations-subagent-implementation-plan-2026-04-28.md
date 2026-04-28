# Efficiency Optimizations Subagent Implementation Plan

**Date:** 2026-04-28
**Source roadmap:** `docs/plans/efficiency-optimizations/efficiency-optimizations-compilation-2026-04-28.md`
**Audience:** Coordinating agent plus multiple less-capable implementation agents.

## Purpose

This document splits the efficiency optimization roadmap into coordinated subagent work packages. It is intentionally detailed because the implementation should be safe for agents that can complete focused tasks but should not be expected to infer broad architecture, migration ordering, or cross-file ownership.

The goal is to let agents work together without overwriting each other, while keeping the highest-risk changes behind explicit merge gates.

## Ground Rules For Every Agent

- Work only in the files assigned to your work package unless the package explicitly says otherwise.
- Do not revert edits made by another agent.
- Do not combine packages unless the coordinator assigns that package to you.
- Do not change public API response shapes unless the package explicitly requires it.
- Do not add new runtime dependencies unless the package explicitly authorizes it.
- Do not implement deferred items:
  - PostgreSQL binary COPY.
  - Parallel `CREATE INDEX CONCURRENTLY`.
  - `synchronous_commit = off`.
  - `earthdistance`.
  - `orjson`.
- For migrations, never import ORM models into migration files. Use Alembic operations and raw SQL.
- Every package must add or update tests named in its package.
- Every final response from a subagent must include:
  - Files changed.
  - Tests run.
  - Any behavior intentionally left unchanged.
  - Any blockers or follow-up decisions.

## Coordination Model

Use one coordinator/integrator and multiple implementation agents. The coordinator owns sequencing, conflict resolution, final test runs, and decisions that cross package boundaries.

Subagents must not all start at once. Use the waves below.

| Wave   | Can Run In Parallel | Merge Gate Before Next Wave                                           |
| ------ | ------------------- | --------------------------------------------------------------------- |
| Wave 0 | Agent 0 only        | Baseline state captured and package boundaries confirmed.             |
| Wave 1 | Agents 1, 2, 3, 4   | Unit tests for changed areas pass; config/migration names reconciled. |
| Wave 2 | Agent 5 only        | Import safety and realtime-history preservation are merged.           |
| Wave 3 | Agents 6 and 10     | Historical retention and runtime caching pass focused tests.          |
| Wave 4 | Agent 7 only        | Stop-time seconds migration applies and focused tests pass.           |
| Wave 5 | Agent 8 only        | Static schema compaction migration applies and focused tests pass.    |
| Wave 6 | Agents 9 and 11     | Heatmap/query/index changes pass focused tests.                       |
| Wave 7 | Agent 0 only        | Full backend test pass or documented failures.                        |

## Shared Branch Hygiene

When possible, each package should be completed in a separate branch or worktree. If all agents work in one worktree, the coordinator must serialize packages that touch the same files.

High-conflict files:

- `backend/app/services/gtfs_feed.py`
- `backend/app/models/gtfs.py`
- `backend/app/persistence/models.py`
- `backend/app/core/config.py`
- `backend/app/services/heatmap_service.py`
- `backend/alembic/versions/*`

Only one active agent should edit any high-conflict file at a time.

## Package Overview

| Agent    | Package                                         | Primary Scope                                                     | Parallel Safety                |
| -------- | ----------------------------------------------- | ----------------------------------------------------------------- | ------------------------------ |
| Agent 0  | Coordinator / integrator                        | Planning, merge order, final validation                           | Runs alone at start/end        |
| Agent 1  | Request timing observability                    | `metrics.py`, `main.py`, metrics tests                            | Safe with import/cache work    |
| Agent 2  | Low-risk importer cleanup                       | GTFS batch config, archive cleanup, `ANALYZE`, persistence checks | Do not run with Agent 5        |
| Agent 3  | Cache memory bounds and Valkey pin              | `cache.py`, config, Docker                                        | Safe with Agent 1/2            |
| Agent 4  | Query/index audit and migration prep            | Read-only audit plus migration skeleton decisions                 | Safe if mostly docs/tests      |
| Agent 5  | Import safety and realtime-history preservation | Import transaction/staging/cascade removal                        | Runs after Agent 2             |
| Agent 6  | Historical retention service                    | Daily validation, purge policy, optional monthly design           | Runs after Agent 5 design lock |
| Agent 7  | GTFS stop-time seconds migration                | `gtfs.py`, importer, schedule queries, migration                  | Runs alone for schema files    |
| Agent 8  | Static schema compaction                        | metadata removal, coordinates, composite keys                     | Runs after Agent 7             |
| Agent 9  | Heatmap query consolidation                     | `heatmap_service.py`, heatmap indexes/tests                       | Runs after schema merge        |
| Agent 10 | Runtime static metadata caching                 | harvester route types, active service IDs, departure key rounding | Safe after Agent 2             |
| Agent 11 | Search/departure indexes                        | `pg_trgm`, parent/departure indexes, tests                        | Runs after Agent 7             |

## Agent 0: Coordinator / Integrator

### Ownership

Agent 0 owns the implementation sequence, package handoff, final review, and final validation.

### Write Scope

- `docs/plans/efficiency-optimizations/*`
- Commit messages or PR description if requested.
- Minimal conflict fixes across packages after subagents complete.

### Responsibilities

1. Before starting implementation, verify current git status and identify uncommitted files.
2. Assign packages in waves, not all at once.
3. Tell each worker they are not alone in the codebase and must not revert others' edits.
4. Review each package for:
   - Write scope violations.
   - Missing tests.
   - Migration ordering conflicts.
   - Public response shape changes.
   - New dependencies.
5. Run focused tests after each wave.
6. Run final checks:
   - `pytest backend/tests/services/test_gtfs_feed_importer.py`
   - `pytest backend/tests/services/test_gtfs_schedule.py`
   - `pytest backend/tests/services/test_heatmap_service.py`
   - `pytest backend/tests/services/test_daily_aggregation_service.py`
   - `pytest backend/tests/services/test_gtfs_realtime_harvester.py`
   - `pytest backend/tests/core/test_config.py`
   - `pytest backend/tests/core/test_metrics.py`
   - `pytest backend/tests/api/test_metrics.py`
   - `pytest backend/tests`
   - `mypy --config-file backend/mypy.ini backend/app`

### Coordinator Merge Gates

Do not start Wave 3 until:

- Agent 5 confirms imports no longer cascade-delete realtime history.
- Agent 2's GTFS config names are merged.
- Alembic revision ordering is known.

Do not start Wave 4 until:

- Stop-time schema naming is final.
- Agent 4's audit has identified all `arrival_time` and `departure_time` references.

Do not start Wave 6 until:

- Realtime historical retention policy is explicit.
- Heatmap work knows whether daily route-type data is JSONB-only, normalized, or hybrid for this implementation pass.

## Agent 1: Request Timing Observability

### Objective

Add global API request timing metrics and `Server-Timing` response headers without changing endpoint behavior.

### Write Scope

Allowed:

- `backend/app/core/metrics.py`
- `backend/app/main.py`
- `backend/tests/core/test_metrics.py`
- `backend/tests/api/test_metrics.py`
- `backend/tests/app/test_main_lifecycle.py` only if needed for middleware tests.

Not allowed:

- Heatmap endpoint logic.
- Cache service logic.
- Database models or migrations.

### Implementation Steps

1. Inspect existing metrics in `backend/app/core/metrics.py`.
2. Add a Prometheus histogram named `bahnvision_api_request_duration_seconds`.
3. Use low-cardinality labels only:
   - HTTP method.
   - Route template or normalized path.
   - Status class or status code.
4. Add a helper function such as `observe_api_request(method, route, status_code, duration_seconds)`.
5. In `backend/app/main.py`, add middleware that:
   - Starts a monotonic timer before `call_next`.
   - Calls the next handler.
   - Records duration even for error responses where possible.
   - Appends `Server-Timing: app;dur=<milliseconds>` to the response.
   - Preserves existing `X-Request-Id` behavior.
6. Ensure route labels avoid raw high-cardinality paths. Prefer `request.scope["route"].path` after routing. If unavailable, use a bounded fallback such as `"unmatched"`.
7. Do not remove existing heatmap-specific `Server-Timing` headers. If a response already has `Server-Timing`, append the `app` entry instead of replacing it.

### Tests To Add Or Update

- Metrics helper increments/observes without raising.
- A test request receives a `Server-Timing` header containing `app;dur=`.
- `/metrics` includes `bahnvision_api_request_duration_seconds`.
- Existing request ID middleware still echoes `X-Request-Id`.
- Error responses still include request timing where practical.

### Acceptance Criteria

- No public endpoint payload changes.
- No high-cardinality raw URL labels.
- Focused tests pass:
  - `pytest backend/tests/core/test_metrics.py backend/tests/api/test_metrics.py backend/tests/app/test_main_lifecycle.py`

## Agent 2: Low-Risk Importer Cleanup

### Objective

Add low-risk importer improvements before the larger staged-import rewrite:

- Configurable `stop_times` batch size.
- GTFS archive retention cleanup.
- Post-import `ANALYZE`.
- Avoid unnecessary logging-mode `ALTER TABLE` calls when possible.

### Write Scope

Allowed:

- `backend/app/core/config.py`
- `backend/app/services/gtfs_feed.py`
- `backend/tests/core/test_config.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/docs/README.md` only if documenting new env vars.

Not allowed:

- Database models.
- Alembic migrations.
- Heatmap service.

### Implementation Steps

1. Add settings:
   - `gtfs_stop_times_batch_size`, env `GTFS_STOP_TIMES_BATCH_SIZE`, default `500_000`, must be positive.
   - `gtfs_feed_archive_retention_count`, env `GTFS_FEED_ARCHIVE_RETENTION_COUNT`, default `2`, must be non-negative.
2. Thread `gtfs_stop_times_batch_size` into all import paths currently defaulting `batch_size=500_000`.
3. Log the chosen stop-times batch size once per import.
4. Add archive cleanup after a successful import only:
   - Keep newest N `.zip` files under `GTFS_STORAGE_PATH`.
   - Delete stale `.part` files.
   - If retention count is `0`, delete all old archives after successful import except any file still being used by the current import.
5. Add an `_analyze_gtfs_tables()` helper called after successful final GTFS load and index recreation.
6. Make logging-mode changes conditional where feasible:
   - Query current `relpersistence` for target tables.
   - Run `ALTER TABLE ... SET UNLOGGED/LOGGED` only for tables not already in desired mode.
   - If this becomes too invasive, isolate it behind a helper and add tests for command selection.
7. Keep existing truncate behavior for now. Agent 5 owns import safety and cascade removal.

### Tests To Add Or Update

- Config parses the new env vars and rejects invalid values.
- Import path passes configured batch size to `_copy_stop_times_from_zip` or `_copy_stop_times_from_directory`.
- Archive cleanup keeps the configured number of newest ZIPs.
- Archive cleanup deletes stale `.part` files.
- Archive cleanup does not run if import fails.
- `_analyze_gtfs_tables()` emits `ANALYZE` for the expected GTFS tables.
- Persistence helper skips `ALTER TABLE` when already in desired mode.

### Acceptance Criteria

- No schema changes.
- No import behavior changes except cleanup, batch size, analyze, and reduced redundant alters.
- Focused tests pass:
  - `pytest backend/tests/core/test_config.py backend/tests/services/test_gtfs_feed_importer.py`

## Agent 3: Cache Memory Bounds And Valkey Pin

### Objective

Prevent unbounded fallback cache memory growth and make Valkey image version reproducible.

### Write Scope

Allowed:

- `backend/app/core/config.py`
- `backend/app/services/cache.py`
- `backend/tests/core/test_config.py`
- `backend/tests/services/test_cache_primitives.py`
- `backend/tests/services/test_cache_metrics.py`
- `docker-compose.yml`
- Root or backend docs if documenting env vars.

Not allowed:

- Transit service cache key behavior.
- Harvester cache behavior.
- Heatmap cache warmup logic.

### Implementation Steps

1. Add settings:
   - `fallback_cache_max_entries`, env `FALLBACK_CACHE_MAX_ENTRIES`, default a conservative number such as `1024`.
   - Optional `fallback_cache_max_bytes` only if the existing fallback cache can track payload size cheaply. If not, do not add byte accounting.
2. Inspect `FallbackCache` in `backend/app/services/cache.py`.
3. Add approximate LRU eviction:
   - Track insertion/update order.
   - On set, evict expired entries first.
   - If still over max entries, evict oldest entries.
4. Keep TTL cleanup behavior.
5. Add tests that:
   - Insert more than the max entry count.
   - Confirm oldest entries are evicted.
   - Confirm unexpired retained entries are still readable.
   - Confirm expired cleanup still works.
6. Pin Valkey in `docker-compose.yml` to a specific stable version. If unsure, use the current major version already expected by dependencies and document the choice in the PR notes. Do not change Valkey command flags.

### Acceptance Criteria

- Fallback cache cannot grow without bound by entry count.
- Existing cache API signatures remain compatible.
- Valkey is no longer `latest`.
- Focused tests pass:
  - `pytest backend/tests/services/test_cache_primitives.py backend/tests/services/test_cache_metrics.py backend/tests/core/test_config.py`

## Agent 4: Query And Migration Audit

### Objective

Prepare a concrete audit for schema and query packages so later agents do not guess at references.

### Write Scope

Allowed:

- `docs/plans/efficiency-optimizations/implementation-audit-2026-04-28.md`

Not allowed:

- Application code.
- Tests.
- Migrations.

### Implementation Steps

1. Search for every reference to:
   - `GTFSStopTime.id`
   - `arrival_time`
   - `departure_time`
   - `feed_id`
   - `RealtimeStationStats.id`
   - `RealtimeStationStatsDaily.id`
   - `by_route_type`
   - `route_type`
2. Document each reference with:
   - File path.
   - Function/class.
   - Whether it is a read, write, filter, join, serialization, test fixture, or migration.
   - Which later agent must handle it.
3. Search for existing Alembic revision ids and produce a proposed migration order:
   - Import safety FK/cascade migration.
   - Stop-time seconds migration.
   - Static metadata compaction migration.
   - Query/index migration.
   - Historical retention migration if needed.
4. Identify tests likely to fail from schema changes.

### Acceptance Criteria

- Produces a plain Markdown audit document.
- Does not change code.
- Gives Agent 7 and Agent 8 a checklist of files to update.

## Agent 5: Import Safety And Realtime-History Preservation

### Objective

Make GTFS static imports safe so failed imports do not destroy the previous feed and static refreshes do not cascade-delete realtime history.

This is a high-risk package. It must run after Agent 2 and before schema-compaction packages.

### Write Scope

Allowed:

- `backend/app/services/gtfs_feed.py`
- `backend/app/persistence/models.py`
- `backend/alembic/versions/*` for one migration.
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_gtfs_feed.py`
- `backend/tests/models/test_gtfs.py` only if needed.

Not allowed:

- Stop-time seconds migration.
- Removing static `feed_id`.
- Heatmap query rewrites.

### Design Requirements

The minimum acceptable fix is:

- Remove `TRUNCATE ... CASCADE`.
- Remove or alter the realtime stats FK cascade from `gtfs_stops`.
- Ensure failed import does not leave final tables empty when a previous feed existed.

Preferred design:

- Load into staging tables first.
- Validate staging data.
- Swap or truncate-and-insert final tables only after staging succeeds.

### Implementation Steps

1. Add an Alembic migration that removes `ondelete="cascade"` from `realtime_station_stats.stop_id`.
   - If preserving FK is still desired, recreate it without cascade.
   - If FK blocks static refresh semantics, drop the FK and document explicit orphan cleanup.
2. Update `RealtimeStationStats.stop_id` model definition to match the migration.
3. Replace the existing truncate-before-load flow with a safer flow:
   - Do not truncate final tables until source feed has been read and minimally validated.
   - If full staging is too large for this package, implement a temporary import validation phase before final truncate and document remaining risk.
4. If implementing staging:
   - Create staging table names that cannot collide with final tables.
   - Drop stale staging tables at the start of a new import.
   - COPY into staging tables.
   - Validate row counts and required relationships.
   - In one final transaction, replace final static tables from staging.
   - Drop staging tables after success.
5. Add explicit orphan cleanup after successful static import:
   - Delete or mark realtime stats whose `stop_id` no longer exists only according to a documented retention rule.
   - If no retention rule is final, do not delete realtime stats automatically.
6. Ensure `_analyze_gtfs_tables()` from Agent 2 runs only after a successful final load.

### Tests To Add Or Update

- No SQL command contains `TRUNCATE ... CASCADE`.
- Failed import after reading invalid feed leaves old static data untouched.
- Failed import leaves `realtime_station_stats` and `realtime_station_stats_daily` untouched.
- Successful import does not implicitly delete realtime rows.
- Migration changes FK cascade behavior.

### Acceptance Criteria

- Static import is no longer able to cascade-delete realtime history.
- Failed imports are materially safer than current truncate-first behavior.
- Focused tests pass:
  - `pytest backend/tests/services/test_gtfs_feed_importer.py backend/tests/services/test_gtfs_feed.py`

## Agent 6: Historical Retention And Rollup Validation

### Objective

Add an explicit retention and rollup framework for historical realtime data so detailed hourly rows can eventually be purged after validated daily summaries exist.

### Write Scope

Allowed:

- `backend/app/core/config.py`
- `backend/app/services/daily_aggregation_service.py`
- New service file under `backend/app/services/`, e.g. `realtime_retention_service.py`
- New job file under `backend/app/jobs/` only if scheduler integration is required.
- `backend/tests/services/test_daily_aggregation_service.py`
- New tests such as `backend/tests/services/test_realtime_retention_service.py`
- Docs under `docs/plans/efficiency-optimizations/`

Not allowed:

- Heatmap query rewrite.
- `RealtimeStationStats` schema changes, unless coordinator approves a retention metadata column.
- Static GTFS importer changes.

### Implementation Steps

1. Add settings:
   - `gtfs_rt_hourly_retention_days`, default `90` or reuse/rename existing `gtfs_rt_stats_retention_days` if it already represents this.
   - `gtfs_rt_retention_enabled`, default `False` for safety unless there is already a retention job.
2. Create a service that can:
   - Determine eligible hourly date ranges older than the retention window.
   - Verify each eligible date has a daily summary.
   - Compare source hourly totals to daily summary totals before deletion.
   - Delete hourly rows only for fully validated dates.
3. Validation must compare at least:
   - `trip_count`
   - `delayed_count`
   - `cancelled_count`
   - `on_time_count`
   - `total_delay_seconds`
   - station/date coverage
4. Do not implement monthly summaries unless the coordinator explicitly requests them. Document a placeholder extension point.
5. Ensure historical queries can still use daily data after hourly deletion. If existing heatmap service already switches to daily summaries for long ranges, add tests around that behavior.

### Tests To Add

- Retention service refuses to delete a date with no daily summary.
- Retention service refuses to delete a date where totals differ.
- Retention service deletes hourly rows for a fully validated old date.
- Retention service does not delete rows newer than retention cutoff.
- Daily aggregation tests include route-type breakdown parity.

### Acceptance Criteria

- Retention deletion is opt-in or explicitly safe by default.
- Detailed rows are deleted only after validation.
- Focused tests pass:
  - `pytest backend/tests/services/test_daily_aggregation_service.py backend/tests/services/test_realtime_retention_service.py`

## Agent 7: GTFS Stop-Time Seconds Migration

### Objective

Replace interval-based stop times with integer seconds since service midnight while preserving API behavior.

This package has a broad blast radius. It must run alone for schema-related files.

### Write Scope

Allowed:

- `backend/app/models/gtfs.py`
- `backend/app/services/gtfs_feed.py`
- `backend/app/services/gtfs_schedule.py`
- `backend/alembic/versions/*` for one migration.
- `backend/tests/models/test_gtfs.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/fixtures/gtfs_data.py`

Not allowed:

- Removing `feed_id`.
- Composite primary key changes.
- Heatmap service changes unless required by schedule query tests.

### Implementation Steps

1. Add `arrival_seconds` and `departure_seconds` integer columns to `GTFSStopTime`.
2. Keep old `arrival_time` and `departure_time` temporarily only if needed for a safe migration. Prefer one migration that:
   - Adds seconds columns.
   - Backfills from existing intervals.
   - Updates indexes.
   - Drops interval columns after code no longer uses them.
3. Add a parsing helper:
   - Input: GTFS time string such as `"26:30:00"`.
   - Output: integer seconds, e.g. `95400`.
   - Invalid or blank input returns `None`.
4. Update import shaping so COPY writes seconds columns.
5. Update schedule departure queries:
   - Compare against integer seconds.
   - Preserve handling of trips beyond midnight.
   - Convert seconds back into the existing response time representation.
6. Replace index `idx_gtfs_stop_times_departure_lookup` with one based on `(stop_id, departure_seconds)`.

### Tests To Add Or Update

- Time parser handles:
  - `"00:00:00"`
  - `"23:59:59"`
  - `"24:00:00"`
  - `"26:30:00"`
  - blank values
  - invalid values
- Import COPY shaping writes `arrival_seconds` and `departure_seconds`.
- Departure query returns same ordering as before.
- API-visible scheduled arrival/departure values are unchanged.
- Migration backfill converts intervals correctly.

### Acceptance Criteria

- No code references dropped interval columns after migration.
- Departure behavior stays stable.
- Focused tests pass:
  - `pytest backend/tests/models/test_gtfs.py backend/tests/services/test_gtfs_feed_importer.py backend/tests/services/test_gtfs_schedule.py`

## Agent 8: Static Schema Compaction

### Objective

Remove unused static GTFS metadata and replace safe surrogate keys with composite keys after Agent 7's stop-time seconds migration lands.

### Write Scope

Allowed:

- `backend/app/models/gtfs.py`
- `backend/app/persistence/models.py`
- `backend/app/services/gtfs_feed.py`
- `backend/app/services/daily_aggregation_service.py` only if daily stats key changes require it.
- `backend/alembic/versions/*` for one or more migrations.
- `backend/tests/models/test_gtfs.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_daily_aggregation_service.py`
- `backend/tests/fixtures/gtfs_data.py`

Not allowed:

- Heatmap query rewrite.
- Stop-time seconds migration.
- Runtime caching changes.

### Implementation Steps

1. Remove `feed_id` from `gtfs_stop_times` first.
2. Search for row-level static `feed_id` usage. If no usage exists, remove `feed_id` from:
   - `gtfs_stops`
   - `gtfs_routes`
   - `gtfs_trips`
   - `gtfs_calendar`
   - `gtfs_calendar_dates`
3. Remove static table timestamps that have no operational value:
   - `created_at`
   - `updated_at`
4. Convert `gtfs_stops.stop_lat` and `gtfs_stops.stop_lon` to `Float` / PostgreSQL `double precision`.
5. Replace `gtfs_stop_times.id` with composite primary key `(trip_id, stop_sequence)`.
6. For `realtime_station_stats_daily`, replace surrogate `id` with composite primary key `(stop_id, date)` only if code audit confirms no active references to the id.
7. Do not change `realtime_station_stats` primary key unless coordinator approves a concrete route-type sentinel design. It has nullable `route_type` semantics that need care.
8. Update importer COPY column lists and test fixtures.

### Tests To Add Or Update

- GTFS model tests reflect removed columns and new primary keys.
- Importer no longer attempts to COPY removed columns.
- Daily aggregation still inserts/upserts summaries correctly.
- Coordinate precision is preserved within tolerance.
- Migration preserves row counts.

### Acceptance Criteria

- Static GTFS import succeeds without removed columns.
- No code references removed columns.
- Focused tests pass:
  - `pytest backend/tests/models/test_gtfs.py backend/tests/services/test_gtfs_feed_importer.py backend/tests/services/test_daily_aggregation_service.py`

## Agent 9: Heatmap Query Consolidation And Indexes

### Objective

Reduce heatmap query round trips and add indexes aligned with the final schema.

### Write Scope

Allowed:

- `backend/app/services/heatmap_service.py`
- `backend/app/persistence/models.py` only for index metadata if needed.
- `backend/alembic/versions/*` for heatmap indexes.
- `backend/tests/services/test_heatmap_service.py`
- `backend/tests/api/v1/test_heatmap.py`
- `backend/tests/api/test_heatmap_overview_endpoint.py`

Not allowed:

- Static GTFS schema.
- Daily aggregation retention.
- Runtime caching outside heatmap.

### Implementation Steps

1. Inspect current `_aggregate_station_data_from_db` and `_aggregate_from_daily_stats`.
2. Preserve response shape exactly.
3. Replace selected-station second-pass breakdown queries with one SQL query where feasible.
   - For hourly stats, aggregate route-type breakdowns in SQL.
   - For daily stats, either aggregate JSONB in SQL or keep existing Python aggregation if SQL becomes too risky.
4. Add heatmap indexes through migration:
   - Start with `(bucket_start, bucket_width_minutes, route_type)`.
   - Consider including `stop_id` only if query plan evidence supports it.
5. Do not normalize daily route-type summaries in this package. That decision belongs after retention/query measurements.

### Tests To Add Or Update

- Heatmap totals match old expected values.
- Route-type filter totals match old expected values.
- Daily summary path returns same breakdowns.
- `max_points` behavior is unchanged.
- Empty DB behavior is unchanged.

### Acceptance Criteria

- No endpoint response shape changes.
- Query consolidation is covered by tests.
- Focused tests pass:
  - `pytest backend/tests/services/test_heatmap_service.py backend/tests/api/v1/test_heatmap.py backend/tests/api/test_heatmap_overview_endpoint.py`

## Agent 10: Runtime Static Metadata Caching

### Objective

Reduce repeated DB work for static GTFS-derived data at runtime.

### Write Scope

Allowed:

- `backend/app/services/gtfs_realtime_harvester.py`
- `backend/app/services/gtfs_schedule.py`
- `backend/app/services/transit_data.py`
- `backend/app/services/cache.py` only for interface typing if absolutely required.
- `backend/tests/services/test_gtfs_realtime_harvester.py`
- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/services/test_transit_data.py`
- `backend/tests/services/test_departures_cache.py`

Not allowed:

- Config changes if Agent 2/3 are active. Ask coordinator first.
- Importer changes.
- Schema migrations.

### Implementation Steps

1. Cache `route_id -> route_type` for harvester:
   - Prefer in-process cache with active feed identity if available.
   - If using Valkey, use a versioned key and tolerate cache failure.
   - Add explicit invalidation hook only if a clean import event exists. Otherwise document that cache TTL bounds staleness.
2. Replace brittle private cache capability checks where touched:
   - Avoid `hasattr(self._cache, "set_json")` if a clearer protocol/interface is practical.
   - Do not refactor all cache code broadly.
3. Cache active service IDs in `GTFSScheduleService.get_active_service_ids`.
   - Key includes query date.
   - TTL expires after end of service date or a conservative fixed TTL.
   - If cache unavailable, fall back to DB.
4. Round departure cache keys in `TransitDataService`.
   - Use one-minute buckets initially.
   - Preserve `from_time=None` behavior.
   - Do not alter departure result filtering logic.

### Tests To Add Or Update

- Harvester route-type map is fetched once and reused.
- Harvester handles cache miss/failure.
- Active service IDs are cached by date.
- Departure calls within the same minute share a cache key.
- Departure calls in different minutes do not share a cache key.

### Acceptance Criteria

- Runtime behavior remains correct when cache is unavailable.
- No API payload changes.
- Focused tests pass:
  - `pytest backend/tests/services/test_gtfs_realtime_harvester.py backend/tests/services/test_gtfs_schedule.py backend/tests/services/test_transit_data.py backend/tests/services/test_departures_cache.py`

## Agent 11: Stop Search And Departure Indexes

### Objective

Add user-facing query indexes after schema changes settle.

### Write Scope

Allowed:

- `backend/app/models/gtfs.py` only for index metadata if desired.
- `backend/alembic/versions/*` for one migration.
- `backend/app/services/gtfs_schedule.py` only if query code needs minor index-friendly tweaks.
- `backend/tests/services/test_gtfs_schedule.py`
- Migration tests if the repo has a pattern for them.

Not allowed:

- Stop-time seconds migration.
- Heatmap query rewrite.
- `earthdistance`.

### Implementation Steps

1. Add migration:
   - `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
   - GIN trigram index on `gtfs_stops.stop_name`.
   - Index on `gtfs_stops(parent_station)`.
   - Departure lookup index matching final schema:
     - If Agent 7 landed seconds columns: `(stop_id, departure_seconds)`.
     - Include `trip_id` and `arrival_seconds` only if PostgreSQL version and query plan justify it.
2. Keep `search_stops()` behavior unchanged unless needed to use the index.
3. Do not add `earthdistance`.

### Tests To Add Or Update

- Search still uses substring semantics.
- Parent station lookup behavior remains unchanged.
- Migration contains expected extension and indexes.

### Acceptance Criteria

- Migration applies after Agent 7/8 migrations.
- Focused tests pass:
  - `pytest backend/tests/services/test_gtfs_schedule.py`

## Recommended Worker Prompts

Use these prompts when assigning work. Replace bracketed text with branch/worktree details.

### Prompt For Agent 1

You are not alone in the codebase. Do not revert others' edits. Implement Agent 1 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 1 write scope. Add global API request timing metrics and `Server-Timing` middleware. Preserve response payloads and existing request-id behavior. Run the focused tests listed in Agent 1 and report files changed, tests run, and any blockers.

### Prompt For Agent 2

You are not alone in the codebase. Do not revert others' edits. Implement Agent 2 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 2 write scope. Add GTFS stop-times batch-size config, archive cleanup, post-import `ANALYZE`, and conditional table persistence changes. Do not remove `CASCADE`; Agent 5 owns import safety. Run the focused tests listed in Agent 2 and report files changed, tests run, and any blockers.

### Prompt For Agent 3

You are not alone in the codebase. Do not revert others' edits. Implement Agent 3 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 3 write scope. Bound fallback cache memory by entry count and pin the Valkey Docker image. Do not change transit cache key behavior. Run the focused tests listed in Agent 3 and report files changed, tests run, and any blockers.

### Prompt For Agent 4

You are not alone in the codebase. Do not revert others' edits. Implement Agent 4 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. This is a documentation-only audit. Do not edit application code, tests, or migrations. Produce the audit document requested by Agent 4 and report the file changed.

### Prompt For Agent 5

You are not alone in the codebase. Do not revert others' edits. Implement Agent 5 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 5 write scope. Your goal is import safety and realtime-history preservation. Do not implement stop-time seconds or remove `feed_id`. Add migration and tests proving GTFS imports cannot cascade-delete realtime history. Run the focused tests listed in Agent 5 and report files changed, tests run, and any blockers.

### Prompt For Agent 6

You are not alone in the codebase. Do not revert others' edits. Implement Agent 6 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 6 write scope. Add historical realtime retention and rollup validation. Keep deletion safe by default and do not change heatmap query shape. Run the focused tests listed in Agent 6 and report files changed, tests run, and any blockers.

### Prompt For Agent 7

You are not alone in the codebase. Do not revert others' edits. Implement Agent 7 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 7 write scope. Replace GTFS stop-time intervals with integer seconds while preserving API behavior. Do not remove `feed_id` or change composite keys beyond what is required for the seconds migration. Run the focused tests listed in Agent 7 and report files changed, tests run, and any blockers.

### Prompt For Agent 8

You are not alone in the codebase. Do not revert others' edits. Implement Agent 8 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 8 write scope. Remove unused static GTFS metadata, convert coordinates to float, and apply safe composite keys after Agent 7 has landed. Do not rewrite heatmap queries. Run the focused tests listed in Agent 8 and report files changed, tests run, and any blockers.

### Prompt For Agent 9

You are not alone in the codebase. Do not revert others' edits. Implement Agent 9 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 9 write scope. Consolidate heatmap aggregation queries and add heatmap indexes. Preserve response shapes exactly. Run the focused tests listed in Agent 9 and report files changed, tests run, and any blockers.

### Prompt For Agent 10

You are not alone in the codebase. Do not revert others' edits. Implement Agent 10 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 10 write scope. Cache route-type maps, active service IDs, and normalize departure cache key timestamps. Cache failures must fall back to existing DB behavior. Run the focused tests listed in Agent 10 and report files changed, tests run, and any blockers.

### Prompt For Agent 11

You are not alone in the codebase. Do not revert others' edits. Implement Agent 11 from `docs/plans/efficiency-optimizations/efficiency-optimizations-subagent-implementation-plan-2026-04-28.md`. Stay within the Agent 11 write scope. Add stop-search and departure lookup indexes after schema changes settle. Do not implement `earthdistance`. Run the focused tests listed in Agent 11 and report files changed, tests run, and any blockers.

## Final Integration Checklist

Agent 0 should run this checklist after all packages are merged:

- Confirm no package added a deferred feature.
- Confirm no package changed frontend API response shapes.
- Confirm Alembic revisions form a single linear chain.
- Run `alembic -c backend/alembic.ini upgrade head`.
- Run `alembic -c backend/alembic.ini downgrade -1` at least for the latest migration, if downgrade is intended to be supported.
- Run focused backend tests listed in each package.
- Run `pytest backend/tests`.
- Run `mypy --config-file backend/mypy.ini backend/app`.
- Search for stale references:
  - `rg -n "arrival_time|departure_time|GTFSStopTime\\.id|feed_id|TRUNCATE TABLE .*CASCADE" backend/app backend/tests`
- Confirm docs mention new environment variables:
  - `GTFS_STOP_TIMES_BATCH_SIZE`
  - `GTFS_FEED_ARCHIVE_RETENTION_COUNT`
  - Any retention or fallback-cache settings added by agents.

## Known Decisions For The Coordinator

The coordinator must decide these before assigning affected packages:

- Whether Agent 5 must implement full staging or whether pre-validation plus no cascade is acceptable as an intermediate step.
- Whether historical hourly retention should default to enabled or disabled.
- Whether daily route-type summaries remain JSONB-only for now.
- Whether `realtime_station_stats_daily.id` can be removed safely in the first compaction pass.
- Whether multi-feed static GTFS support is intentionally out of scope.

## Recommended Implementation Order

1. Agent 0 establishes baseline.
2. Run Agents 1, 2, 3, and 4 in parallel.
3. Merge Agent 1 first because it is low conflict.
4. Merge Agent 3 next because cache/Docker changes are isolated.
5. Merge Agent 2 after reviewing config names.
6. Use Agent 4's audit to refine Agent 5, 7, and 8 prompts if needed.
7. Run Agent 5 alone.
8. Run Agents 6 and 10 after Agent 5, unless the coordinator decides retention must wait for schema compaction.
9. Run Agent 7 alone.
10. Run Agent 8 alone.
11. Run Agents 9 and 11 after schema changes settle.
12. Agent 0 performs final integration.
