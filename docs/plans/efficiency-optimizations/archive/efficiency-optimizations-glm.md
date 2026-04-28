# Optimization Plan: Efficiency, Space Saving, and GTFS Imports

**Analyst:** GLM (OpenCode)
**Date:** 2026-04-28
**Scope:** Full codebase analysis focusing on GTFS import pipeline, database storage, and query performance.

---

## Objective

Implement structural and algorithmic optimizations across the codebase to significantly reduce database storage footprint, speed up massive GTFS data imports, and decrease response times for real-time heatmap and harvester services.

---

## Key Files & Context

- **Database Models:** `backend/app/models/gtfs.py`, `backend/app/persistence/models.py`
- **Import Service:** `backend/app/services/gtfs_feed.py`
- **Schedule Service:** `backend/app/services/gtfs_schedule.py`
- **Realtime Harvester:** `backend/app/services/gtfs_realtime_harvester.py`
- **Transit Data Service:** `backend/app/services/transit_data.py`
- **Cache Service:** `backend/app/services/cache.py`
- **Heatmap Service:** `backend/app/services/heatmap_service.py`
- **Database Migrations:** `backend/alembic/versions/`
- **Config:** `backend/app/core/config.py`

---

## 1. GTFS Import Speed (HIGH IMPACT)

### 1.1 Eliminate Temp CSV Files for Small Tables

**File:** `backend/app/services/gtfs_feed.py` (`_copy_polars_df`, lines 372-406)

**Current:** Writes Polars DataFrame to disk, then opens the file for COPY. For stops (~900K), routes (~100K), and calendar tables, this disk round-trip is unnecessary.

**Proposed:** Use `io.BytesIO` to write CSV in-memory, avoiding disk I/O entirely:

```python
buf = io.BytesIO()
df.write_csv(buf, include_header=False)
buf.seek(0)
await asyncpg_conn.copy_to_table(table_name, source=buf, ...)
```

**Keep disk-based for stop_times** (too large for memory; 50M+ rows).

**Impact:** Saves ~3 temp file creates + reads per import; removes disk bottleneck for small tables.

---

### 1.2 Use Binary COPY Format

**File:** `backend/app/services/gtfs_feed.py` (lines 395-399)

**Current:** Uses `format="csv"` for all COPY operations.

**Proposed:** Switch to PostgreSQL binary COPY format, which avoids text parsing and is ~20-30% faster. Polars can serialize to Arrow IPC, which maps cleanly to PostgreSQL binary COPY.

**Impact:** Affects every `_copy_polars_df` and `_copy_stop_times_batch` call. Significant for 50M+ row stop_times.

---

### 1.3 Parallelize Index Recreation

**File:** `backend/app/services/gtfs_feed.py` (`_recreate_stop_times_indexes_and_fks`, lines 737-782)

**Current:** Three stop_times indexes (`idx_gtfs_stop_times_stop`, `idx_gtfs_stop_times_trip`, `idx_gtfs_stop_times_departure_lookup`) are created sequentially.

**Proposed:** Use `CREATE INDEX CONCURRENTLY` with separate asyncpg connections to build all three indexes in parallel.

**Impact:** Cuts index creation time by ~2/3 for 50M+ rows.

---

### 1.4 Increase stop_times Batch Size

**File:** `backend/app/services/gtfs_feed.py` (`_copy_stop_times_from_zip`, line 611)

**Current:** `batch_size=500_000` is conservative.

**Proposed:** Increase to `1_500_000` or `2_000_000` rows per batch. The semaphore(3) already caps concurrent memory usage; larger batches reduce per-batch overhead (connection setup, CSV write, COPY init).

**Impact:** Reduces overhead for ~50M rows by ~3x fewer batches.

---

### 1.5 Use `synchronous_commit = off` During Import

**File:** `backend/app/services/gtfs_feed.py` (`_truncate_all_tables`, lines 211-271)

**Current:** WAL flushes happen per transaction by default.

**Proposed:** `SET LOCAL synchronous_commit = off` before COPY operations. Since tables are UNLOGGED and data is fully rebuildable, a crash just means re-importing.

**Impact:** Reduces WAL flush waits during bulk COPY.

---

### 1.6 Increase Backpressure Threshold

**File:** `backend/app/services/gtfs_feed.py` (lines 672-677)

**Current:** Threshold of 6 pending tasks (2x semaphore of 3).

**Proposed:** Raise to 9-12 (3-4x semaphore). For batched stop_times, the bottleneck is COPY I/O, not memory. Keeping the pipeline fuller increases throughput.

---

## 2. Space Saving (HIGH IMPACT)

### 2.1 Remove `feed_id` Column from `gtfs_stop_times`

**File:** `backend/app/models/gtfs.py` (line 111)

**Current:** `feed_id: Mapped[str | None] = mapped_column(String(32))` on all GTFS tables.

**Issue:** The `feed_id` column (32 bytes/row) on `gtfs_stop_times` (~50M rows) wastes **~1.6 GB**. Data is always full-truncated-and-replaced -- only one feed exists at a time. `gtfs_feed_info` already tracks the feed.

**Proposed:** Drop `feed_id` from `GTFSStopTime`. Keep on smaller tables (stops, routes, trips, calendar, calendar_dates) if multi-feed support is planned.

**Impact:** **~1.6 GB saved** on stop_times alone.

---

### 2.2 Remove `feed_id` from Other GTFS Tables

**Files:** `backend/app/models/gtfs.py` (lines 36, 59, 81, 130, 139)

**Current:** `feed_id` exists on stops, routes, trips, calendar, calendar_dates.

**Proposed:** Drop `feed_id` from all GTFS static tables. Add it back via migration when multi-feed support is implemented.

**Impact:** **~200-300 MB additional savings** (combined with 2.1: **~2 GB total**).

---

### 2.3 Store Times as Integer Seconds Instead of Interval

**File:** `backend/app/models/gtfs.py` (lines 106-107)

**Current:** `arrival_time` and `departure_time` stored as PostgreSQL `Interval` (16-24 bytes per value).

**Proposed:** Use `INTEGER` (4 bytes) storing total seconds from midnight. GTFS times exceeding 24h are naturally handled as large integers (e.g., 26:30:00 = 95400 seconds). Convert to interval at query time: `departure_seconds * interval '1 second'`.

**Impact:** **~1.0-1.5 GB saved** (2 columns x 50M rows x ~16 bytes saved).

---

### 2.4 Remove `created_at`/`updated_at` from Static GTFS Tables

**Files:** `backend/app/models/gtfs.py` (lines 37-47 for stops, 82-86 for trips)

**Current:** `created_at` and `updated_at` timestamps on `gtfs_stops` and `gtfs_trips`.

**Issue:** These add no value for fully-replaced static data. `gtfs_feed_info.downloaded_at` already tracks import time.

**Proposed:** Remove `created_at` and `updated_at` from `GTFSStop`, `GTFSTrip`, and other GTFS tables. Keep on `gtfs_feed_info` only.

**Impact:** **~200 MB saved** (2 timestamptz columns x 16 bytes x ~6M rows).

---

### 2.5 Drop Old GTFS ZIP Files After Successful Import

**File:** `backend/app/services/gtfs_feed.py` (lines 887-933)

**Current:** Stores downloaded ZIP at `gtfs_storage_path` with no cleanup.

**Proposed:** Add post-import cleanup keeping only the N most recent ZIPs (e.g., 3).

**Impact:** Prevents unbounded disk growth. A Germany-wide feed ZIP is ~200-400 MB.

---

## 3. Query Efficiency (HIGH IMPACT)

### 3.1 Add `pg_trgm` GIN Index for Stop Search

**File:** `backend/app/services/gtfs_schedule.py` (lines 261-271)

**Current:** `search_stops()` uses `ILIKE '%query%'` causing a **full table scan** on ~900K stops.

**Proposed:**

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_gtfs_stops_name_trgm ON gtfs_stops USING GIN (stop_name gin_trgm_ops);
```

**Impact:** **100-1000x faster** substring searches.

---

### 3.2 Normalize Departure Cache Key Timestamps

**File:** `backend/app/services/transit_data.py` (line 364)

**Current:** Cache key includes `from_time.isoformat()` with full ISO precision. Every unique timestamp creates a new cache entry rarely reused.

**Proposed:** Bin `from_time` to nearest minute (or 5 minutes):

```python
rounded = from_time.replace(second=0, microsecond=0)
# Or for 5-min bins: from_time.replace(minute=(from_time.minute // 5) * 5, ...)
```

**Impact:** Dramatically improves cache hit rates for departure queries.

---

### 3.3 Cache Active Service IDs in Valkey

**File:** `backend/app/services/gtfs_schedule.py` (`get_active_service_ids`, lines 99-134)

**Current:** Runs two DB queries on every departure request. Calendar data is static for the entire day.

**Proposed:** Cache result in Valkey with a daily TTL (or until next GTFS import):

```python
cache_key = f"active_service_ids:{today.isoformat()}"
```

**Impact:** Eliminates 2 DB queries per departure request.

---

### 3.4 Add Covering Index for Departure Query

**File:** `backend/app/services/gtfs_schedule.py` (lines 188-211)

**Current:** Main departure query joins `stop_times -> trips -> routes`. `gtfs_stop_times` requires heap fetches for `trip_id` and `arrival_time`.

**Proposed:** Create covering index:

```sql
CREATE INDEX idx_gtfs_stop_times_departure_covering
ON gtfs_stop_times(stop_id, departure_time)
INCLUDE (trip_id, arrival_time);
```

**Impact:** Enables index-only scans on stop_times, avoiding heap fetches on ~50M rows.

---

### 3.5 Cache route_type Mapping in the Harvester

**File:** `backend/app/services/gtfs_realtime_harvester.py` (line 377)

**Current:** Fetches route_type mapping from `gtfs_routes` every 5-minute harvest cycle.

**Proposed:** Cache the mapping in Valkey with invalidation on GTFS import. The mapping only changes on import.

**Impact:** Saves one DB query per harvest cycle (~288 queries/day).

---

### 3.6 Use `earthdistance` Extension for Nearby Stops

**File:** `backend/app/services/gtfs_schedule.py` (lines 282-304)

**Current:** Bounding-box approximation misses results in corners and over-selects along axes.

**Proposed:** Use PostgreSQL `earthdistance` contrib extension for proper great-circle distance without PostGIS overhead.

**Impact:** More accurate results with better selectivity.

---

## Summary: Top 5 by Impact

| #         | Change                                | Category     | Est. Impact                 |
| --------- | ------------------------------------- | ------------ | --------------------------- |
| 2.1 + 2.2 | Remove `feed_id` from all GTFS tables | Space        | **~2 GB saved**             |
| 2.3       | Integer seconds instead of Interval   | Space        | **~1-1.5 GB saved**         |
| 3.1       | `pg_trgm` GIN index for stop search   | Speed        | **100-1000x faster search** |
| 1.2       | Binary COPY format                    | Import speed | **20-30% faster import**    |
| 1.3       | Parallel index recreation             | Import speed | **~60% faster post-import** |

**Total estimated space savings from schema changes: ~3-3.5 GB** on a Germany-wide feed.

---

## Verification & Testing

1. **Test Suite**: Run `pytest backend/tests` to ensure no regressions in endpoint logic or model interactions.
2. **Schema Validation**: Run `alembic upgrade head` and `alembic downgrade -1` locally to verify migration logic is idempotent and correct.
3. **Import Benchmark**: Execute a GTFS import and observe log timings for COPY phases and index recreation.
4. **Heatmap Benchmark**: Test heatmap API endpoints for large date ranges to verify data parity.
5. **Harvester Benchmark**: Monitor harvester logs to ensure snapshot caching completes without excessive DB queries.
6. **Disk Space Check**: Compare `pg_database_size()` before and after schema changes.
