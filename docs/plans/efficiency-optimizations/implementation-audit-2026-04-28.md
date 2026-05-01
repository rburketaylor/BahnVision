# Efficiency Optimizations Implementation Audit

Date: 2026-04-28

This audit is read-only. It maps the schema and query references that later
agents need to touch so they do not have to infer blast radius from the
roadmap alone.

## Current Baseline

The current Alembic chain relevant to this work is:

1. `backend/alembic/versions/add_gtfs_tables.py`
2. `backend/alembic/versions/add_gtfs_rt_observations.py`
3. `backend/alembic/versions/redesign_gtfs_rt_storage.py`
4. `backend/alembic/versions/add_daily_station_stats.py`
5. `backend/alembic/versions/fix_heatmap_duplication.py`
6. `backend/alembic/versions/add_trip_route_idx_and_rt_stop_fk.py`
7. `backend/alembic/versions/add_gtfs_parent_station_fk.py`

Two existing choices matter for the later migration sequence:

- `gtfs_stop_times` still uses `arrival_time` and `departure_time` as
  PostgreSQL `INTERVAL` columns and still has a surrogate `id`.
- `realtime_station_stats.stop_id` currently has `ondelete="CASCADE"` in both
  the ORM model and migration history, so GTFS static refreshes can delete
  realtime history unless the import path is changed first.

## Reference Inventory

### 1. `GTFSStopTime.id`

References found:

- `backend/app/models/gtfs.py`, `GTFSStopTime`
- `backend/tests/models/test_gtfs.py`, `TestGTFSStopTimeModel`
- `backend/tests/fixtures/gtfs_data.py`, `create_test_gtfs_stop_time`

What it does today:

- Schema definition only in the model.
- Test fixtures and model tests construct stop-time rows, but no direct
  `.id` access was found in application code.
- Import code in `backend/app/services/gtfs_feed.py` writes stop-time rows and
  recreates stop-time indexes/FKs, so it will feel the key change indirectly.

Role type:

- Schema definition
- Test fixture / model instantiation
- Import shape

Later owner:

- Agent 7 for the stop-time seconds migration.
- Agent 8 if the composite-key cleanup removes the surrogate `id` in the same
  pass or a follow-up pass.

### 2. `arrival_time` and `departure_time`

References found:

- `backend/app/models/gtfs.py`, `GTFSStopTime`
- `backend/app/services/gtfs_feed.py`, `GTFSFeedImporter._copy_stop_times_batch`
  and `_read_csv_batched`
- `backend/app/services/gtfs_schedule.py`, `ScheduledDeparture` and
  `GTFSScheduleService.get_stop_departures`
- `backend/app/services/transit_data.py`, schedule-to-API mapping
- `backend/tests/fixtures/gtfs_data.py`
- `backend/tests/models/test_gtfs.py`
- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_transit_data.py`

What it does today:

- Stored as `INTERVAL` in the GTFS stop-time table.
- Imported from GTFS CSV text as strings and normalized in the importer.
- Converted back to datetimes in schedule queries.
- Propagated into transit response models as scheduled arrival/departure times.

Role type:

- Write path
- Read path
- Serialization boundary
- Test fixture / regression coverage

Later owner:

- Agent 7.

### 3. `feed_id`

References found:

- `backend/app/models/gtfs.py`, every static GTFS table plus `GTFSFeedInfo`
- `backend/app/services/gtfs_feed.py`, feed import and record-keeping methods
- `backend/app/jobs/gtfs_scheduler.py`, import success logging
- `backend/app/api/v1/endpoints/ingestion.py`, status response assembly
- `backend/app/models/ingestion.py`, API status model
- `backend/tests/fixtures/gtfs_data.py`
- `backend/tests/models/test_gtfs.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/api/v1/test_ingestion.py`
- `backend/tests/jobs/test_gtfs_scheduler.py`

What it does today:

- Row-level `feed_id` is still written to the static GTFS tables.
- `GTFSFeedInfo.feed_id` remains the feed-level source of truth and should not
  be removed.
- The importer truncates and repopulates static tables, so row-level feed IDs
  are currently redundant but still part of the persisted shape.

Role type:

- Write path
- Status/API serialization
- Fixture / regression coverage

Later owner:

- Agent 5 for import safety around feed replacement.
- Agent 8 for static GTFS metadata compaction if row-level `feed_id` is dropped.

### 4. `RealtimeStationStats.id`

References found:

- `backend/app/persistence/models.py`, `RealtimeStationStats`
- `backend/app/services/daily_aggregation_service.py`, `aggregate_day`
- `backend/app/api/v1/endpoints/ingestion.py`, realtime row-count fallback

What it does today:

- Surrogate primary key on the hourly realtime stats table.
- Used as a cheap row-count anchor in the ingestion status endpoint.
- Used by daily aggregation for counting hourly observations.

Role type:

- Schema definition
- Count/probe helper

Later owner:

- No dedicated removal agent is assigned in the current plan.
- Keep this column unless the coordinator explicitly approves a separate hourly
  surrogate-key redesign.

### 5. `RealtimeStationStatsDaily.id`

References found:

- `backend/app/persistence/models.py`, `RealtimeStationStatsDaily`
- `backend/app/services/station_stats_service.py`, daily-range probe query
- `backend/tests/services/test_daily_aggregation_service.py`

What it does today:

- Surrogate primary key on the daily summary table.
- Used only as a presence probe before falling back to hourly data.

Role type:

- Schema definition
- Query probe

Later owner:

- Agent 8 if the daily surrogate key is removed as part of the compaction pass.

### 6. `by_route_type`

References found:

- `backend/app/persistence/models.py`, `RealtimeStationStatsDaily.by_route_type`
- `backend/app/services/daily_aggregation_service.py`, daily summary writer
- `backend/app/services/heatmap_service.py`, daily summary reader and filter
- `backend/tests/services/test_daily_aggregation_service.py`
- `backend/tests/services/test_heatmap_service.py`

What it does today:

- Stores daily route breakdowns as JSONB keyed by transport type name.
- Written by the daily aggregation service.
- Read by the heatmap service when large ranges use daily summaries.

Role type:

- JSONB write path
- JSONB read path
- Query-shape dependency

Later owner:

- Agent 9 for heatmap query consolidation.
- Agent 6 / Agent 0 for the storage-shape decision if the project later moves
  away from JSONB-only daily summaries.

### 7. `route_type` in the static GTFS schema and schedule path

References found:

- `backend/app/models/gtfs.py`, `GTFSRoute.route_type`
- `backend/app/services/gtfs_feed.py`, `_copy_routes`
- `backend/app/services/gtfs_schedule.py`, `ScheduledDeparture` and
  `GTFSScheduleService.get_stop_departures`
- `backend/app/services/transit_data.py`, route serialization
- `backend/app/models/transit.py`, API response model
- `backend/tests/models/test_gtfs.py`
- `backend/tests/models/test_transit.py`
- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_transit_data.py`

What it does today:

- Static GTFS route type is still part of the imported feed and of the schedule
  API response shape.
- This field is not a removal target in the current plan.

Role type:

- Import path
- Query path
- API serialization
- Test coverage

Later owner:

- No removal agent.
- Agent 10 owns the route-type cache optimization.

### 8. `route_type` in realtime stats and heatmap queries

References found:

- `backend/app/persistence/models.py`, `RealtimeStationStats.route_type`
- `backend/app/persistence/models.py`, `RealtimeStationStatsDaily.by_route_type`
- `backend/app/services/daily_aggregation_service.py`
- `backend/app/services/heatmap_service.py`
- `backend/app/services/station_stats_service.py`
- `backend/app/services/gtfs_realtime_harvester.py`
- `backend/tests/services/test_daily_aggregation_service.py`
- `backend/tests/services/test_heatmap_service.py`
- `backend/tests/services/test_station_stats_service.py`
- `backend/tests/services/test_station_stats_cache.py`
- `backend/tests/services/test_gtfs_realtime_harvester.py`

What it does today:

- Used as the grouping key for hourly realtime stats.
- Used in daily rollups and heatmap/station statistics filters.
- Cached route-type maps in the harvester will still need to align with this
  storage shape.

Role type:

- Read/write grouping key
- Filter key
- Cache key input

Later owner:

- Agent 6 for retention/rollup policy decisions.
- Agent 9 for heatmap query consolidation.
- Agent 10 for route-type map caching.
- Agent 11 for stop/departure index follow-up work after schema changes settle.

## Proposed Migration Order

The existing head is the `add_gtfs_parent_station_fk` revision. The next
migrations should be ordered as follows:

1. Import safety FK/cascade migration

   - Change the realtime history path so static GTFS refreshes cannot delete
     historical realtime rows.
   - This is the prerequisite for any compaction that assumes imports are
     non-destructive.

2. Stop-time seconds migration

   - Add the integer-second representation for `gtfs_stop_times`.
   - Backfill existing data.
   - Update schedule query code and importer conversion paths.

3. Static GTFS metadata compaction migration

   - Drop row-level `feed_id` from `gtfs_stop_times` first.
   - Then evaluate the other static GTFS tables only if no row-level filter
     remains.
   - Apply surrogate-key cleanup only after the stop-time seconds migration is
     stable.

4. Query/index migration

   - Refresh stop-search and departure-lookup indexes after the schema settles.
   - Revisit heatmap-oriented indexes after Agent 9 has consolidated the query
     shape.

5. Historical retention migration, if needed
   - Add the hourly-retention policy only after daily summaries and validation
     are proven stable.
   - Keep the retention policy separate unless it can be merged without changing
     the query shape again.

## Tests Most Likely To Break

### Agent 7 impact

- `backend/tests/models/test_gtfs.py`
- `backend/tests/fixtures/gtfs_data.py`
- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_transit_data.py`

Why:

- These files assert `arrival_time` / `departure_time` behavior, including
  values beyond 24 hours and the importer's CSV shaping.

### Agent 8 impact

- `backend/tests/models/test_gtfs.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/api/v1/test_ingestion.py`
- `backend/tests/jobs/test_gtfs_scheduler.py`
- `backend/tests/fixtures/gtfs_data.py`

Why:

- These files hard-code row-level `feed_id` expectations and feed-info status
  output.

### Composite-key / surrogate-key impact

- `backend/tests/services/test_daily_aggregation_service.py`
- `backend/tests/services/test_heatmap_service.py`
- `backend/tests/services/test_station_stats_service.py`

Why:

- These tests probe surrogate ids or assume current daily-summary and realtime
  grouping behavior.

### Query/index follow-up impact

- `backend/tests/services/test_gtfs_schedule.py`
- `backend/tests/services/test_gtfs_feed_importer.py`
- `backend/tests/services/test_heatmap_service.py`

Why:

- These tests are the most sensitive to departure lookup indexes and route-type
  query shape changes.

## Checklist For Later Agents

### Agent 7

- Update `backend/app/services/gtfs_feed.py` to import seconds instead of
  intervals.
- Update `backend/app/services/gtfs_schedule.py` to query seconds and convert
  back to datetimes at the service boundary.
- Keep API payloads unchanged.
- Preserve the existing handling of times beyond 24:00:00.

### Agent 8

- Remove row-level `feed_id` only after import safety is solved.
- Decide whether `GTFSStopTime.id` and `RealtimeStationStatsDaily.id` stay or
  move to a composite key in the same pass.
- Keep `GTFSFeedInfo.feed_id` intact.
- Do not change `TransitRoute.route_type` API semantics.

### Agent 9

- Reconcile daily `by_route_type` reads with the final heatmap query shape.
- Preserve response shapes exactly.
- If the daily summary storage shape changes, update both the service and the
  tests in the same migration wave.

### Agent 10

- Keep the route-type cache aligned with the realtime grouping model.
- Invalidate cached route-type maps when the active GTFS feed changes.

### Agent 11

- Rebuild stop-search and departure lookup indexes only after the schema
  migrations settle.
- Make sure the index names and query predicates line up with the post-migration
  departure storage type.

## Bottom Line

- `arrival_time` / `departure_time` are Agent 7's problem.
- Row-level static `feed_id` is Agent 8's problem, but only after Agent 5 makes
  imports non-destructive.
- `by_route_type` is still a live query-shape decision and should not be
  dropped casually.
- `RealtimeStationStatsDaily.id` is the only surrogate key in this area with a
  clearly identified follow-up removal candidate.
