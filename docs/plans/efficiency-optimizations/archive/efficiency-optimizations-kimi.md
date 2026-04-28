# Optimization Plan: Efficiency, Space Saving, and GTFS Imports

## Objective

Implement structural and algorithmic optimizations across the codebase to significantly reduce database storage footprint, speed up massive GTFS data imports, and decrease response times for real-time heatmap and harvester services.

## Key Files & Context

- **Database Models:** `backend/app/models/gtfs.py`, `backend/app/persistence/models.py`
- **Import Service:** `backend/app/services/gtfs_feed.py`
- **Realtime Harvester:** `backend/app/services/gtfs_realtime_harvester.py`
- **Heatmap Service:** `backend/app/services/heatmap_service.py`
- **Database Migrations:** `backend/alembic/versions/`

---

## What's Already Well-Optimized

The codebase already has a **strong performance foundation**:

- **GTFS import** uses Polars batched CSV reader + PostgreSQL `COPY` protocol, parallel independent table loads, `UNLOGGED` tables, and index/FK drop-rebuild (`gtfs_feed.py`).
- **GTFS-RT harvester** uses streaming aggregation (~250x storage reduction), Lua-based deduplication in Valkey, and `COPY`-to-temp-table + `INSERT...ON CONFLICT` bulk upserts (`gtfs_realtime_harvester.py`).
- **Heatmap queries** switch to pre-aggregated daily summaries for ranges >=3 days, giving 6-24x speedup on large ranges (`heatmap_service.py`, `daily_aggregation_service.py`).
- **Caching** has circuit breakers, stale-while-revalidate, single-flight locks, and batched pipeline operations (`cache.py`).
- **Departures queries** pre-resolve active `service_id`s and avoid joining `gtfs_stops` on the hot path (`gtfs_schedule.py`).

---

## 1. GTFS Import Speed

### 1a. Add `ANALYZE` after import (high impact, trivial cost)

After truncating and reloading millions of rows, PostgreSQL's query planner has **stale statistics**. Currently there are **no `ANALYZE` or `VACUUM` calls** in the Python codebase.

**Recommendation:** Run `ANALYZE gtfs_stop_times, gtfs_trips, gtfs_stops, gtfs_routes, gtfs_calendar, gtfs_calendar_dates` after `_recreate_stop_times_indexes_and_fks()`. This typically improves departure and heatmap query plans immediately after import.

### 1b. Reduce temp-file I/O for smaller tables (medium impact)

`_copy_polars_df` writes every DataFrame to a **disk-based temp CSV**, then reads it back for `copy_to_table`. For `stops`, `routes`, `calendar`, and `trips` (relatively small), stream directly from memory via `io.BytesIO` to avoid disk I/O entirely.

**Tradeoff:** For `stop_times` (millions of rows), disk buffering may still be necessary to control memory usage within the Docker `mem_limit: 768m`.

### 1c. Increase `stop_times` batch size with a memory guard (medium impact)

Currently `batch_size=500_000`. Raising this to `1_500_000` or `2_000_000` generally improves PostgreSQL `COPY` throughput. However, the backend container is capped at **768 MB RAM** in `docker-compose.yml`. Polars holding 2M rows of `stop_times` can consume **200-400 MB**.

**Recommendation:** Make the batch size configurable via an env var (e.g., `GTFS_STOP_TIMES_BATCH_SIZE`) so production can tune it based on available memory, rather than hardcoding a larger value.

### 1d. Drop more indexes during import (small-medium impact)

Currently only `stop_times` indexes/FKs are dropped. For very large feeds, dropping indexes on `gtfs_trips(service_id)` and `gtfs_stops(stop_name)` before import and recreating them after can also shave time. This is low-risk because the tables are truncated anyway.

---

## 2. Database Storage / Space Saving

### 2a. Remove surrogate IDs and use composite primary keys (high impact)

The savings are significant at scale:

| Table                          | Current Surrogate PK | Composite PK Candidate                 | Estimated Saving                                                      |
| ------------------------------ | -------------------- | -------------------------------------- | --------------------------------------------------------------------- |
| `gtfs_stop_times`              | `id` (Integer)       | `(trip_id, stop_sequence)`             | ~4 bytes/row + index overhead. On 10M rows = **~40 MB+**              |
| `realtime_station_stats`       | `id` (BigInteger)    | `(stop_id, bucket_start, route_type*)` | ~8 bytes/row + index. On millions of hourly buckets = **substantial** |
| `realtime_station_stats_daily` | `id` (BigInteger)    | `(stop_id, date)`                      | ~8 bytes/row + index                                                  |

\*For `realtime_station_stats`, `route_type` is currently nullable. To use it in a composite PK, default it to `0` (or another sentinel) instead of `NULL`. This aligns with the existing `postgresql_nulls_not_distinct=True` workaround on the unique constraint.

**Tradeoff:** ORM code that assumes a single `id` column (e.g., `RealtimeStationStatsDaily.id`) would need updating. Direct references are few, so the blast radius is small.

### 2b. Change `gtfs_stops` lat/lon from `Numeric(9,6)` to `Float` (medium impact)

`Numeric(9,6)` uses arbitrary-precision storage and is slower for spatial calculations. `Float` (PostgreSQL `double precision`) provides ~15 decimal digits of precision - more than enough for 6-decimal-place coordinates - and uses **8 bytes vs ~12+ bytes** per `Numeric`. Every heatmap query does `func.floor(GTFSStop.stop_lon / GRID_CELL_SIZE)`, which benefits from native floating-point speed.

### 2c. Remove `created_at`/`updated_at` from static GTFS tables (small impact)

`gtfs_stops`, `gtfs_routes`, `gtfs_trips`, and `gtfs_stop_times` all carry `created_at`/`updated_at` (or `created_at` alone). For static GTFS data that is fully replaced on every import, these timestamps add **8-16 bytes/row** with no operational value. Removing them from GTFS models saves space and simplifies the COPY pipeline.

---

## 3. Query / Runtime Efficiency

### 3a. Combine heatmap two-pass queries into one (medium impact)

Both `_aggregate_station_data_from_db` and `_aggregate_from_daily_stats` execute:

1. A CTE/tiered query to select top stations.
2. A second query with `.in_(station_ids)` to fetch per-route-type breakdowns.

**Recommendation:** Replace the second query with PostgreSQL **JSON aggregation** inside the first query:

```sql
SELECT stop_id, stop_name, stop_lat, stop_lon,
       SUM(trip_count) AS total_departures,
       jsonb_object_agg(
         COALESCE(route_type::text, '0'),
         jsonb_build_object('trips', trip_count, ...)
       ) AS by_transport
FROM ...
GROUP BY stop_id, stop_name, stop_lat, stop_lon
```

This reduces **two network round-trips + two query plans** to one. For the daily stats path, this is especially valuable because the second query currently fetches all `RealtimeStationStatsDaily` rows for selected stations and aggregates `by_route_type` in Python.

### 3b. Add a composite index on `realtime_station_stats` for heatmap filtering (medium impact)

The heatmap queries filter on `bucket_start`, `bucket_width_minutes`, and `route_type`. Current indexes:

- `ix_realtime_stats_stop_bucket` on `(stop_id, bucket_start)`
- `ix_realtime_stats_bucket` on `(bucket_start)`

A covering index like:

```sql
CREATE INDEX idx_realtime_stats_bucket_route ON realtime_station_stats(bucket_start, bucket_width_minutes, route_type);
```

would allow PostgreSQL to satisfy the `WHERE` clause and aggregation more efficiently for short-range heatmap queries that don't use daily summaries.

### 3c. Cache the route_type map in the harvester (medium impact)

`GTFSRTDataHarvester._get_route_type_map(session)` queries the database every harvest cycle (every 5 minutes). Route types are static for the lifetime of a GTFS feed. Caching this in Valkey (e.g., `gtfs:route_type_map` as JSON) with a 24h TTL would eliminate a DB query per cycle.

### 3d. Add API request latency metrics + `Server-Timing` middleware (high observability impact)

The `end-to-end-performance-profiling-plan.md` details this well, but **none of it is implemented**. Adding a FastAPI middleware that records `bahnvision_api_request_duration_seconds` (Prometheus histogram) and appends `Server-Timing: app;dur=...` to responses is the foundation for identifying which endpoints are actually slow. This has near-zero runtime overhead.

---

## 4. Caching & Memory Efficiency

### 4a. Bound the in-memory fallback cache (medium impact)

`FallbackCache` stores all entries in a plain `dict` with TTL-based cleanup every 60 seconds. Under cache stampede or Valkey outage, large JSON heatmap responses (thousands of data points) could accumulate unbounded memory.

**Recommendation:** Add a max-size limit (e.g., LRU eviction via `functools.lru_cache` pattern or a bounded deque) to the fallback cache.

### 4b. Consider `orjson` for JSON serialization (small-medium impact)

`cache.py` uses `json.dumps` with `jsonable_encoder` fallback. For large heatmap payloads, `orjson` is **5-10x faster** and uses less temporary memory. It's a drop-in replacement if you're willing to add a dependency.

---

## 5. Docker / Infrastructure

### 5a. Postgres container memory is tight for large imports

`docker-compose.yml` gives Postgres only **512 MB RAM**. Germany-wide GTFS imports with `COPY`, index creation, and `UNLOGGED` tables can push this limit, causing disk spilling and slowdowns.

**Recommendation:** For the import job specifically, consider allowing a higher Postgres memory limit or adding `shm_size` to the Postgres service to prevent `copy_to_table` from failing or spilling on large temp tables.

### 5b. `valkey` uses `latest` tag

The `valkey` service pins to `valkey/valkey:latest`. This is a reproducibility risk. Pinning to a specific version (e.g., `valkey/valkey:8.0`) avoids unexpected cache behavior changes.

---

## Summary of Priorities

| Priority | Change                                                                                                               | Expected Impact                                            |
| -------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **P0**   | Run `ANALYZE` after GTFS import                                                                                      | Immediate query planner improvements; trivial to implement |
| **P0**   | Add API request metrics + `Server-Timing` middleware                                                                 | Unlocks data-driven optimization; foundation for profiling |
| **P1**   | Remove surrogate IDs -> composite PKs on `gtfs_stop_times`, `realtime_station_stats`, `realtime_station_stats_daily` | Significant space savings on largest tables                |
| **P1**   | Combine heatmap two-pass queries into one JSON-aggregating query                                                     | Fewer round-trips, lower latency                           |
| **P1**   | Change `gtfs_stops` lat/lon to `Float`                                                                               | Space + spatial query speed                                |
| **P2**   | Cache route_type map in harvester                                                                                    | Eliminates repetitive DB query                             |
| **P2**   | Add heatmap-covering index `(bucket_start, bucket_width_minutes, route_type)`                                        | Faster short-range heatmap queries                         |
| **P2**   | Memory-stream small tables during COPY; make stop_times batch size configurable                                      | Faster imports without blowing memory                      |
| **P3**   | Bound fallback cache / evaluate `orjson`                                                                             | Resilience + serialization speed                           |

---

## Existing Plan vs. This Analysis

The repo already contains `docs/plans/efficiency-optimizations.md`, which correctly identifies composite PKs, batch size tuning, heatmap query consolidation, and harvester metadata caching. This plan **extends** that with:

- **Critical missing pieces**: `ANALYZE`/`VACUUM` after import, API request metrics (the profiling plan exists but is unimplemented), memory constraints with larger batch sizes, and index additions.
- **Risks**: Hardcoding 2M batches without memory guards, the `NULL` route_type issue for composite PKs on `realtime_station_stats`.
- **Additional quick wins**: `Float` lat/lon, removing `created_at` from static GTFS tables, bounding fallback cache.

---

## Verification & Testing

1. **Test Suite**: Run `pytest backend/tests` to ensure no regressions in endpoint logic or model interactions.
2. **Schema Validation**: Run `alembic upgrade head` and `alembic downgrade -1` locally to verify migration logic is idempotent and correct.
3. **Import Benchmark**: Execute `python scripts/import_gtfs.py` and observe log timings to confirm optimizations improve total ingestion time.
4. **Heatmap Benchmark**: Test heatmap API endpoints (`/api/v1/endpoints/heatmap`) to verify faster execution times for large date ranges and ensure data parity with old queries.
5. **Harvester Benchmark**: Monitor logs for the realtime harvester task to ensure snapshot caching completes without excessive DB queries.
