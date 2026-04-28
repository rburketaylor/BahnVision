# BahnVision GTFS Efficiency Optimization Plan

## Summary

- Target the full GTFS pipeline with migrations included.
- Fix the highest-risk issue first: static import currently truncates GTFS tables with `CASCADE`, while realtime stats cascade from `gtfs_stops`, so refreshes can erase retained heatmap history.
- Reduce import time, temp disk usage, Docker build context size, static table footprint, and repeated GTFS-RT/heatmap query work.

## Key Changes

### Build And Storage Cleanup

- Expand `.dockerignore` to exclude `frontend/node_modules`, `frontend/dist`, `backend/mutants`, coverage files, reports, and local caches from backend image build context.
- Add `GTFS_FEED_ARCHIVE_RETENTION_COUNT`, defaulting to `2`.
- After a successful import, delete older downloaded GTFS ZIPs and stale `.part` files under `GTFS_STORAGE_PATH`.

### Static GTFS Import

- Replace truncate-before-load with staging-table import:
  - Download and parse into unlogged staging tables.
  - Validate staging contents.
  - Swap or truncate-and-insert final GTFS tables only after staging succeeds.
- Remove `CASCADE` from GTFS truncation.
- Drop the realtime-stats-to-`gtfs_stops` foreign key and replace it with post-import orphan cleanup so static refreshes preserve realtime history.
- Avoid repeated `ALTER TABLE ... SET UNLOGGED/LOGGED`; set desired persistence in migrations and only alter when the current DB setting differs.
- Stream `stop_times.txt` into staging instead of extracting it plus writing per-batch temp CSVs.

### Schema And Index Efficiency

- Store GTFS stop times as integer seconds since service midnight instead of PostgreSQL `INTERVAL`.
- Index stop-time lookups with `(stop_id, departure_seconds)`.
- Remove unused static GTFS per-row `feed_id`, `created_at`, and `updated_at` columns from high-volume tables; keep feed metadata in `gtfs_feed_info`.
- Drop the unused surrogate `gtfs_stop_times.id`; use `(trip_id, stop_sequence)` as the primary key.
- Add `ix_gtfs_stops_parent_station` for child-stop departure lookup.
- Add a `pg_trgm` GIN index on `gtfs_stops.stop_name` for `%query%` station search.
- Add heatmap-oriented indexes on realtime stats covering `bucket_width_minutes`, `bucket_start`, `route_type`, and `stop_id`.

### GTFS-RT And Heatmap

- Cache `route_id -> route_type` in the harvester and invalidate it when the active feed changes instead of selecting all routes every harvest.
- Batch or pipeline trip-marker Lua updates to reduce per-trip Valkey round trips.
- Normalize daily route-type summaries into a queryable table for filtered `7d` and `30d` heatmap views.
- Keep existing frontend API response shapes unchanged.

## Public Interfaces

- New environment variable: `GTFS_FEED_ARCHIVE_RETENTION_COUNT`, default `2`.
- No frontend API response-shape changes.
- Internal ORM and schema changes for GTFS static tables and realtime aggregation tables require Alembic migrations and corresponding test fixture updates.

## Test Plan

- Add importer integration tests proving failed imports leave the old GTFS data and realtime stats intact.
- Add migration tests for FK removal, new indexes, stop-time seconds conversion, and dropped unused columns.
- Add importer unit tests for ZIP retention cleanup, stale `.part` cleanup, nested GTFS ZIP paths, optional columns, and no `TRUNCATE ... CASCADE`.
- Add query tests for station search, parent-station departures, heatmap filters, and daily route-type summaries.
- Add a benchmark script comparing old vs new import phases:
  - Download.
  - Staging load.
  - Final swap.
  - Index/analyze.
  - Total time.
  - Peak temp disk.
  - Final table size.

## Assumptions

- BahnVision needs one active static GTFS feed at a time; historical static feeds do not need row-level `feed_id`.
- Realtime heatmap history is more valuable than strict FK cascade cleanup during static feed refresh.
- PostgreSQL can enable `pg_trgm` in the target environments.
