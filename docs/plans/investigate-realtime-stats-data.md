# Investigation: Realtime Station Stats Database Data

## Problem Statement

The `realtime_station_stats` database table appears to have no data, causing all historical time range queries (1h, 6h, 24h, 7d, 30d) to return zeros for station statistics. This investigation aims to determine why data isn't being written to the database and how to fix it.

---

## Background

### Expected Data Flow

The GTFS-RT harvester should:

1. Fetch real-time trip updates from the GTFS-RT feed
2. Aggregate updates by stop and route type
3. **Write to database** via `_upsert_stats()` method
4. **Cache live snapshot** via `_cache_live_snapshot()` method

Currently, step 4 is working (live snapshot cache has data), but step 3 appears to not be populating the database.

### Relevant Code

| File                         | Function                         | Purpose                                                   |
| ---------------------------- | -------------------------------- | --------------------------------------------------------- |
| `gtfs_realtime_harvester.py` | `_upsert_stats()`                | Writes aggregated stats to `realtime_station_stats` table |
| `gtfs_realtime_harvester.py` | `_aggregate_by_stop_and_route()` | Aggregates trip updates for database storage              |
| `gtfs_realtime_harvester.py` | `harvest()`                      | Main entry point called by scheduler                      |
| `station_stats_service.py`   | `get_station_stats()`            | Queries `realtime_station_stats` table                    |

---

## Investigation Steps

### Step 1: Check if Harvester is Running

**Goal:** Verify the GTFS-RT harvester is scheduled and executing.

```bash
# Check docker logs for harvester activity
docker compose logs backend 2>&1 | grep -i "harvest\|gtfs-rt" | tail -50
```

Look for:

- "Fetching GTFS-RT data" messages
- "Upserted X station stats" messages
- Any error messages during harvesting

### Step 2: Verify Database Table Exists and Has Data

**Goal:** Check if `realtime_station_stats` table exists and inspect its contents.

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d bahnvision

# Check table exists
\dt realtime_station_stats

# Check row count
SELECT COUNT(*) FROM realtime_station_stats;

# Check recent data
SELECT stop_id, bucket_start, trip_count, cancelled_count, delayed_count
FROM realtime_station_stats
ORDER BY bucket_start DESC
LIMIT 20;

# Check data for a specific station (e.g., Essen Hbf)
SELECT * FROM realtime_station_stats
WHERE stop_id = '66563'
ORDER BY bucket_start DESC
LIMIT 10;
```

### Step 3: Check Harvester Configuration

**Goal:** Verify harvester settings in configuration.

```python
# Check these settings in app/core/config.py or environment variables:
# - GTFS_RT_FEED_URL: Must be set to valid GTFS-RT endpoint
# - GTFS_RT_HARVEST_INTERVAL_SECONDS: Default 300 (5 minutes)
# - GTFS_RT_STATS_RETENTION_DAYS: How long data is kept
```

```bash
# Check environment variables
docker compose exec backend env | grep -i gtfs
```

### Step 4: Trace the Harvest Execution Path

**Goal:** Understand if `_upsert_stats()` is being called.

Add temporary logging to `gtfs_realtime_harvester.py` around line 947:

```python
async def _upsert_stats(
    self,
    session: AsyncSession,
    bucket_start: datetime,
    stop_stats: dict[tuple[str, int], dict],
) -> None:
    logger.info(f"_upsert_stats called with {len(stop_stats)} stop stats")  # ADD THIS
    if not stop_stats:
        return
    # ... rest of function
```

Then rebuild and check logs:

```bash
docker compose up -d --build
docker compose logs -f backend | grep "_upsert_stats"
```

### Step 5: Check for Deadlock or Transaction Issues

**Goal:** The harvester has deadlock retry logic; check if it's failing silently.

Look for these in logs:

```bash
docker compose logs backend 2>&1 | grep -i "deadlock\|transaction\|rollback" | tail -20
```

### Step 6: Test Manual Database Insert

**Goal:** Verify database is writable.

```sql
-- In PostgreSQL console
INSERT INTO realtime_station_stats (
    stop_id, bucket_start, bucket_width_minutes,
    observation_count, trip_count, total_delay_seconds,
    delayed_count, on_time_count, cancelled_count, route_type
) VALUES (
    'TEST_STOP', NOW(), 60,
    1, 10, 0,
    2, 7, 1, 3
);

-- Verify it was inserted
SELECT * FROM realtime_station_stats WHERE stop_id = 'TEST_STOP';

-- Clean up
DELETE FROM realtime_station_stats WHERE stop_id = 'TEST_STOP';
```

---

## Potential Causes

### Cause 1: Harvester Not Scheduled

The harvester may not be running on a schedule. Check:

- `app/main.py` or scheduler configuration
- APScheduler or background task setup

### Cause 2: Empty Trip Updates

The GTFS-RT feed may be returning empty or filtered data. Check:

- `_fetch_trip_updates()` return value
- Feed URL accessibility
- Feed format compatibility

### Cause 3: Aggregation Returns Empty Dict

The aggregation step may be filtering out all stations. Check:

- `_aggregate_by_stop_and_route()` logic
- Route type mapping issues

### Cause 4: Upsert Silently Failing

The PostgreSQL COPY or upsert may be failing. Check:

- Unique constraint conflicts
- Table permissions
- Connection pool exhaustion

### Cause 5: Database Reset or Migration

The database may have been reset without re-populating. Check:

- Recent migrations
- Container volume state

---

## Resolution Steps (Once Cause Identified)

### If Harvester Not Running

1. Check scheduler configuration in `app/main.py`
2. Verify APScheduler is set up correctly
3. Manually trigger: `POST http://localhost:8000/api/v1/heatmap/aggregate-daily`

### If Data Being Filtered

1. Review route_type mapping in `GTFS_ROUTE_TYPES`
2. Check if stop_ids match between GTFS-RT and GTFS static data
3. Verify feed URL is returning expected data format

### If Upsert Failing

1. Check PostgreSQL constraint definitions
2. Review `uq_realtime_stats_unique` constraint
3. Add explicit error logging in `_upsert_stats()`

---

## Monitoring Recommendations

After fixing, add these observability improvements:

1. **Metrics counter** for successful DB writes:

   ```python
   from prometheus_client import Counter
   STATS_UPSERTED = Counter('gtfs_rt_stats_upserted', 'Station stats upserted to DB')
   ```

2. **Health check** that verifies recent data exists:

   ```sql
   SELECT COUNT(*) > 0 FROM realtime_station_stats
   WHERE bucket_start > NOW() - INTERVAL '1 hour';
   ```

3. **Alert** if no data written in last hour

---

## Related Files

- [gtfs_realtime_harvester.py](file:///home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend/app/services/gtfs_realtime_harvester.py)
- [station_stats_service.py](file:///home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend/app/services/station_stats_service.py)
- [heatmap.py (endpoint)](file:///home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend/app/api/v1/endpoints/heatmap.py)
- [Database models](file:///home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend/app/persistence/models.py)
