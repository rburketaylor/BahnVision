# Realtime Stats Data Investigation - Findings Report

**Date**: 2026-01-30
**Status**: Investigation Complete

---

## Executive Summary

The `realtime_station_stats` table appears to have no data, causing all historical time range queries (1h, 6h, 24h, 7d, 30d) to return zeros. This investigation analyzed the harvester code, scheduler configuration, and database layer to identify potential root causes.

---

## 1. Harvester Execution Analysis

### 1.1 Complete Execution Flow

```
harvest_once() [main entry point, lines 230-327]
    ├─> Check GTFS-RT bindings available
    ├─> Check import lock (skip if import in progress)
    ├─> _fetch_trip_updates() [lines 329-409]
    │   └─> HTTP GET to GTFS-RT feed URL
    │       └─> Parse protobuf response
    │           └─> Return list of trip update dictionaries
    ├─> Create hourly time bucket
    ├─> Fetch route type mapping from database
    ├─> _aggregate_by_stop_and_route() [lines 488-554]
    │   ├─> First pass: determine trip status per stop
    │   ├─> Second pass: aggregate by (stop_id, route_type)
    │   └─> Apply trip statuses with cache deduplication
    ├─> _aggregate_snapshot_by_stop_and_route() [for live cache]
    ├─> Cache live snapshot in Redis
    └─> _upsert_stats() [lines 962-1076]  <-- DATABASE WRITE
        ├─> Create temp table
        ├─> COPY data via binary protocol
        └─> INSERT ... ON CONFLICT upsert
```

### 1.2 Early Return Conditions (Data Won't Be Written)

| Condition                    | Location                                 | Log Message                                                    | Impact              |
| ---------------------------- | ---------------------------------------- | -------------------------------------------------------------- | ------------------- |
| GTFS-RT bindings unavailable | Line 237                                 | "GTFS-RT bindings not available, skipping harvest"             | Returns 0           |
| Import lock active           | Lines 240-242, 269-271, 289-291, 303-305 | "Skipping GTFS-RT harvest: GTFS feed import is in progress"    | Returns 0           |
| No trip updates from feed    | Line 256                                 | "No trip updates received - caching empty live snapshot"       | Returns 0           |
| Empty stop statistics        | Line 298                                 | "No stop statistics generated from trip updates" (debug level) | Returns 0           |
| Empty stop_stats dict        | Line 980-981                             | No log (silent return)                                         | Silent early return |

### 1.3 Silent Failure Points

1. **Cache Service Missing** (lines 637-643)

   - Only logs warning, continues processing
   - Trip deduplication may be incomplete

2. **Route Type Map Failure** (lines 424-430)

   - Returns empty dict
   - Routes get `UNKNOWN_ROUTE_TYPE` (-1)
   - Log: "Failed to fetch route type map"

3. **Cache Batch Operations Fail** (lines 938-949)

   - Falls back to non-cached processing
   - Logs debug message only

4. **Network/HTTP Failures** (lines 405-409)
   - Returns empty list on any exception
   - Logs exception but harvest continues

### 1.4 Key Logging Statements

| Log Message                                                        | Level | Indicates                     |
| ------------------------------------------------------------------ | ----- | ----------------------------- |
| "GTFS-RT harvester started with interval %ds"                      | INFO  | Harvester initialized         |
| "Starting GTFS-RT harvest cycle"                                   | INFO  | New harvest iteration begun   |
| "Fetching GTFS-RT data from %s"                                    | INFO  | Making HTTP request           |
| "GTFS-RT feed download complete: status=%s, size=%d bytes"         | INFO  | Response received             |
| "Received %d trip updates from GTFS-RT feed"                       | INFO  | Data parsed successfully      |
| "Processing data for bucket starting at %s"                        | INFO  | Starting aggregation          |
| "Caching live snapshot with %d stop-route combinations"            | INFO  | Live snapshot cached          |
| "Harvested and aggregated stats for %d station-route combinations" | INFO  | **Database write successful** |
| "Harvester iteration failed: %s"                                   | ERROR | Unhandled exception           |

---

## 2. Scheduler Configuration Analysis

### 2.1 Scheduling Mechanism

The harvester uses **asyncio-based polling**, NOT APScheduler or cron.

- **Implementation**: Background asyncio task created during FastAPI lifespan
- **Location**: `backend/app/main.py` lines 104-107
- **Pattern**: `while self._running: await asyncio.sleep(interval)`

### 2.2 Configuration Settings

| Setting                            | Default                                       | Purpose                            |
| ---------------------------------- | --------------------------------------------- | ---------------------------------- |
| `gtfs_rt_harvesting_enabled`       | `True`                                        | Master on/off switch for harvester |
| `gtfs_rt_harvest_interval_seconds` | `300` (5 min)                                 | Time between harvest cycles        |
| `gtfs_rt_stats_retention_days`     | `90`                                          | How long to keep historical data   |
| `gtfs_rt_feed_url`                 | `"https://realtime.gtfs.de/realtime-free.pb"` | GTFS-RT data source                |
| `gtfs_rt_timeout_seconds`          | `10`                                          | HTTP request timeout               |

### 2.3 Important Distinction

Two separate settings control GTFS-RT functionality:

| Setting                      | Default | Controls                              |
| ---------------------------- | ------- | ------------------------------------- |
| `gtfs_rt_enabled`            | `False` | Real-time API responses (live data)   |
| `gtfs_rt_harvesting_enabled` | `True`  | Background historical data collection |

These can run independently. The harvester can be disabled while live RT remains enabled, and vice versa.

### 2.4 Startup Sequence

```
FastAPI lifespan starts
    └─> Create CacheService
        └─> If gtfs_rt_harvesting_enabled == True:
            └─> Create GTFSRTDataHarvester
                └─> await harvester.start()
                    └─> Create asyncio task for _run_polling_loop()
                        └─> Log: "GTFS-RT harvester started with interval 300s"
```

### 2.5 Import Lock Mechanism

The harvester cooperates with GTFS feed imports:

```python
async def _check_import_lock(self) -> bool:
    """Check if GTFS feed import is in progress."""
    import_lock = get_import_lock()
    return await import_lock.is_import_in_progress()
```

If an import is in progress, the harvest cycle is skipped entirely. This prevents conflicts between static data updates and real-time processing.

---

## 3. Database Layer Analysis

### 3.1 Table Schema

```sql
CREATE TABLE realtime_station_stats (
    id BIGSERIAL PRIMARY KEY,
    stop_id VARCHAR(64) NOT NULL,
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_width_minutes INTEGER NOT NULL DEFAULT 60,
    observation_count INTEGER NOT NULL DEFAULT 0,
    trip_count INTEGER NOT NULL DEFAULT 0,
    total_delay_seconds BIGINT NOT NULL DEFAULT 0,
    delayed_count INTEGER NOT NULL DEFAULT 0,
    on_time_count INTEGER NOT NULL DEFAULT 0,
    cancelled_count INTEGER NOT NULL DEFAULT 0,
    route_type INTEGER,
    first_observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_realtime_stats_unique UNIQUE (stop_id, bucket_start, bucket_width_minutes, route_type)
);

CREATE INDEX ix_realtime_stats_stop_bucket ON realtime_station_stats (stop_id, bucket_start);
CREATE INDEX ix_realtime_stats_bucket ON realtime_station_stats (bucket_start);
```

### 3.2 Query Pattern

Both `station_stats_service.py` and `heatmap_service.py` use similar query patterns:

```sql
SELECT route_type,
       SUM(trip_count) AS total_departures,
       SUM(cancelled_count) AS cancelled_count,
       SUM(delayed_count) AS delayed_count
FROM realtime_station_stats
WHERE stop_id = ?
  AND bucket_start >= ?
  AND bucket_start < ?
  AND bucket_width_minutes = ?  -- EXACT MATCH REQUIRED
GROUP BY route_type;
```

### 3.3 Potential Query Issues

| Issue                     | Description                                          | Impact                                            |
| ------------------------- | ---------------------------------------------------- | ------------------------------------------------- |
| **Bucket width mismatch** | Query filters on exact `bucket_width_minutes` match  | If stored data has different width, returns empty |
| **Route type filtering**  | `route_type` can be NULL (combined) or specific type | Filtering on specific type excludes NULL data     |
| **HAVING clause**         | `HAVING total_departures >= 1`                       | Filters out stations with no trips                |
| **Time range gaps**       | Strict `bucket_start >= from AND bucket_start < to`  | Missing harvest cycles = zeros                    |
| **Cache staleness**       | 5-minute TTL on cached results                       | New data may not appear immediately               |

### 3.4 Upsert Mechanism

The harvester uses PostgreSQL's `INSERT ... ON CONFLICT`:

```sql
INSERT INTO realtime_station_stats (...)
VALUES (...)
ON CONFLICT ON CONSTRAINT uq_realtime_stats_unique
DO UPDATE SET
    observation_count = realtime_station_stats.observation_count + EXCLUDED.observation_count,
    trip_count = realtime_station_stats.trip_count + EXCLUDED.trip_count,
    ...
```

This aggregates counts for the same `(stop_id, bucket_start, bucket_width_minutes, route_type)` combination.

---

## 4. Ranked Root Cause Hypotheses

### Hypothesis 1: Import Lock Blocking (HIGH LIKELIHOOD)

The harvester checks the import lock before every operation. If:

- A GTFS feed import is currently running
- An import crashed without releasing the lock
- The lock TTL is too long

All harvest cycles would be skipped with the log message: _"Skipping GTFS-RT harvest: GTFS feed import is in progress"_

**Diagnostic Command**:

```bash
docker compose logs backend 2>&1 | grep -i "import.*in progress\|import.*lock" | tail -20
```

### Hypothesis 2: Empty Trip Updates from Feed (MEDIUM LIKELIHOOD)

The GTFS-RT feed at `https://realtime.gtfs.de/realtime-free.pb` may be:

- Returning empty responses
- Returning data in unexpected format
- Blocking or timing out

**Diagnostic Commands**:

```bash
# Check if trip updates are received
docker compose logs backend 2>&1 | grep "Received.*trip updates" | tail -20

# Check feed directly
curl -I https://realtime.gtfs.de/realtime-free.pb
```

### Hypothesis 3: Route Type Mapping Failure (MEDIUM LIKELIHOOD)

If the route type query fails, all routes get `UNKNOWN_ROUTE_TYPE` (-1). This could cause:

- Data to be written with `route_type = -1`
- Queries filtering on specific route types to miss this data

**Diagnostic Command**:

```bash
docker compose logs backend 2>&1 | grep -i "route type\|UNKNOWN_ROUTE_TYPE" | tail -20
```

### Hypothesis 4: Bucket Width Mismatch (MEDIUM LIKELIHOOD)

If the harvester writes data with a different `bucket_width_minutes` than what queries expect, all queries would return empty.

**Diagnostic Command**:

```bash
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT DISTINCT bucket_width_minutes, COUNT(*) FROM realtime_station_stats GROUP BY bucket_width_minutes;"
```

### Hypothesis 5: Silent Early Return in Upsert (LOW-MEDIUM LIKELIHOOD)

The `_upsert_stats()` method has a silent early return at line 980:

```python
if not stop_stats:
    return  # No logging!
```

If aggregation produces an empty dict, the function returns silently without writing to the database.

**Diagnostic Command**:

```bash
docker compose logs backend 2>&1 | grep "No stop statistics generated\|stop statistics" | tail -20
```

### Hypothesis 6: Database Never Had Data (LOW LIKELIHOOD)

The table may have been created but never populated, or data may have been cleaned up by retention policy.

**Diagnostic Command**:

```bash
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT COUNT(*), MAX(bucket_start), MIN(bucket_start) FROM realtime_station_stats;"
```

---

## 5. Diagnostic Commands Summary

### Check Harvester Activity

```bash
# Verify harvester started
docker compose logs backend 2>&1 | grep "GTFS-RT harvester started"

# Check for harvest cycles
docker compose logs backend 2>&1 | grep "Starting GTFS-RT harvest cycle" | tail -20

# Check if data was received
docker compose logs backend 2>&1 | grep "Received.*trip updates" | tail -20

# Check for successful writes
docker compose logs backend 2>&1 | grep "Harvested and aggregated stats" | tail -20

# Check for errors
docker compose logs backend 2>&1 | grep -E "Harvester iteration failed|GTFS-RT.*error" | tail -20
```

### Check Database State

```bash
# Total row count
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT COUNT(*) FROM realtime_station_stats;"

# Check time range of data
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT MIN(bucket_start), MAX(bucket_start), COUNT(*) FROM realtime_station_stats;"

# Check bucket widths
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT bucket_width_minutes, COUNT(*) FROM realtime_station_stats GROUP BY bucket_width_minutes;"

# Check for recent data
docker compose exec postgres psql -U postgres -d bahnvision -c \
  "SELECT stop_id, bucket_start, trip_count, cancelled_count, delayed_count
   FROM realtime_station_stats
   ORDER BY bucket_start DESC
   LIMIT 20;"
```

### Check Import Lock

```bash
# Check for import lock activity
docker compose logs backend 2>&1 | grep -i "import.*lock\|import.*progress" | tail -30
```

---

## 6. Resolution Steps

### If Import Lock is Blocking

1. Check if an import is actually running
2. Check lock TTL configuration
3. Manually clear lock if needed: `await import_lock.release()`
4. Consider reducing lock timeout

### If Feed is Empty

1. Verify feed URL is accessible: `curl -I https://realtime.gtfs.de/realtime-free.pb`
2. Check if API key or authentication is needed
3. Consider alternative feed sources

### If Route Type Mapping Fails

1. Check `gtfs_routes` table has data
2. Verify route_type column is populated
3. Check logs for database connection issues

### If Bucket Width Mismatch

1. Determine what bucket width is being written
2. Update query logic to match
3. Or add migration to standardize bucket widths

### If Upsert is Failing Silently

1. Add explicit logging before the early return at line 980
2. Check for unique constraint violations
3. Verify database connection pool is healthy

---

## 7. Monitoring Recommendations

After fixing, add these observability improvements:

### 7.1 Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

STATS_UPSERTED = Counter('gtfs_rt_stats_upserted_total', 'Station stats upserted to DB')
STATS_UPSERT_BYTES = Histogram('gtfs_rt_stats_upsert_bytes', 'Bytes written to DB')
HARVEST_CYCLES = Counter('gtfs_rt_harvest_cycles_total', 'Harvest cycles completed')
TRIP_UPDATES_RECEIVED = Gauge('gtfs_rt_trip_updates', 'Trip updates received from feed')
```

### 7.2 Health Check Query

```sql
SELECT COUNT(*) > 0 AS has_recent_data
FROM realtime_station_stats
WHERE bucket_start > NOW() - INTERVAL '1 hour';
```

### 7.3 Alerting Rules

- Alert if no data written in last hour
- Alert if harvest cycle fails > 3 consecutive times
- Alert if feed returns empty responses
- Alert if import lock held > 10 minutes

---

## 8. Related Files

| File                                              | Purpose                           |
| ------------------------------------------------- | --------------------------------- |
| `backend/app/services/gtfs_realtime_harvester.py` | Harvester implementation          |
| `backend/app/services/station_stats_service.py`   | Stats query service               |
| `backend/app/services/heatmap_service.py`         | Heatmap query service             |
| `backend/app/api/v1/endpoints/heatmap.py`         | Heatmap API endpoint              |
| `backend/app/persistence/models.py`               | Database models                   |
| `backend/app/core/config.py`                      | Configuration settings            |
| `backend/app/main.py`                             | Application startup and scheduler |

---

## 9. Next Actions

1. [ ] Run diagnostic commands to identify actual root cause
2. [ ] Add explicit logging for silent early returns
3. [ ] Implement health check endpoint
4. [ ] Add Prometheus metrics
5. [ ] Create alerting rules
6. [ ] Document monitoring dashboard
