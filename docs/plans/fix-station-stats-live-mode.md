# Fix Station Stats Live Mode - Implementation Plan

## Problem Statement

When users click on a station in the heatmap with `time_range=live`, the popup shows all zeros for departures, cancellations, and delays, even though the heatmap overview shows that station as impacted.

### Root Cause

The heatmap overview (`/api/v1/heatmap/overview?time_range=live`) uses a **live snapshot cache** populated directly from GTFS-RT data, but the station stats endpoint (`/api/v1/transit/stops/{stop_id}/stats`) queries the **`realtime_station_stats` database table**, which may not have corresponding data.

### Data Flow Mismatch

```
┌─────────────────────────────────────────────────────────────────┐
│ GTFS-RT Harvester                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Fetches GTFS-RT feed data                                     │
│            │                                                    │
│            ├───────────────────────────────┐                    │
│            │                               │                    │
│            ▼                               ▼                    │
│   _cache_live_snapshot()          _upsert_stats()               │
│   (Cache: live snapshot)          (DB: realtime_station_stats)  │
│            │                               │                    │
│            ▼                               ▼                    │
│   /heatmap/overview?live       /transit/stops/{id}/stats        │
│   ✅ Has data                   ❌ No data (or stale)            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Proposed Changes

### Backend Changes

#### [MODIFY] [stops.py](file:///home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend/app/api/v1/endpoints/transit/stops.py)

Add live snapshot fallback to the `get_station_stats` endpoint:

1. Import the live cache key function:

   ```python
   from app.services.heatmap_cache import heatmap_live_snapshot_cache_key
   from app.models.heatmap import HeatmapResponse
   ```

2. Modify `get_station_stats` function (around line 230) to:
   - Check if `time_range == "live"`
   - If live, attempt to fetch the live snapshot from cache
   - Extract the specific station's data from the snapshot
   - Convert to `StationStats` format and return
   - Fall back to database query if cache miss

**Implementation detail - add new helper function:**

```python
async def _get_station_stats_from_live_snapshot(
    stop_id: str,
    cache: CacheService,
) -> StationStats | None:
    """Extract station stats from the live snapshot cache."""
    cache_key = heatmap_live_snapshot_cache_key()
    cached_data = await cache.get_json(cache_key)
    if not cached_data:
        cached_data = await cache.get_stale_json(cache_key)

    if not cached_data:
        return None

    snapshot = HeatmapResponse.model_validate(cached_data)

    # Find the station in the snapshot
    for point in snapshot.data_points:
        if point.station_id == stop_id:
            # Convert by_transport dict to TransportBreakdown list
            by_transport = [
                TransportBreakdown(
                    transport_type=transport_type,
                    display_name=TRANSPORT_TYPE_NAMES.get(transport_type, transport_type),
                    total_departures=stats.total,
                    cancelled_count=stats.cancelled,
                    cancellation_rate=min(stats.cancelled / stats.total, 1.0) if stats.total > 0 else 0,
                    delayed_count=stats.delayed,
                    delay_rate=min(stats.delayed / stats.total, 1.0) if stats.total > 0 else 0,
                )
                for transport_type, stats in point.by_transport.items()
            ]

            return StationStats(
                station_id=stop_id,
                station_name=point.station_name,
                time_range="live",
                total_departures=point.total_departures,
                cancelled_count=point.cancelled_count,
                cancellation_rate=point.cancellation_rate,
                delayed_count=point.delayed_count,
                delay_rate=point.delay_rate,
                network_avg_cancellation_rate=snapshot.summary.overall_cancellation_rate if snapshot.summary else None,
                network_avg_delay_rate=snapshot.summary.overall_delay_rate if snapshot.summary else None,
                performance_score=None,  # Not calculated for live
                by_transport=by_transport,
                data_from=snapshot.time_range.from_ if snapshot.time_range else None,
                data_to=snapshot.time_range.to if snapshot.time_range else None,
            )

    return None
```

**Modify the endpoint:**

```python
@router.get(
    "/stops/{stop_id}/stats",
    ...
)
async def get_station_stats(
    request: Request,
    stop_id: str,
    response: Response,
    time_range: Annotated[...] = "24h",
    stats_service: StationStatsService = Depends(get_station_stats_service),
    cache: CacheService = Depends(get_cache_service),  # ADD THIS
) -> StationStats:
    """Get station statistics including cancellation and delay rates."""

    # Handle live mode - use snapshot cache
    if time_range == "live":
        stats = await _get_station_stats_from_live_snapshot(stop_id, cache)
        if stats:
            set_stats_cache_header(response)
            return stats
        # Fall through to database query with "1h" as fallback
        time_range = "1h"

    stats = await stats_service.get_station_stats(stop_id, time_range)
    ...
```

#### Required Imports to Add

```python
from app.services.heatmap_cache import heatmap_live_snapshot_cache_key
from app.models.heatmap import HeatmapResponse
from app.services.heatmap_service import TRANSPORT_TYPE_NAMES
from app.models.station_stats import TransportBreakdown
```

---

## Verification Plan

### Automated Tests

Run existing backend tests to ensure no regressions:

```bash
cd /home/burket/Git/BahnVision/.worktrees/ui-design-upgrade/backend
pytest tests/api/v1/test_transit_stops.py -v
```

### Manual Verification

1. **Build and start containers:**

   ```bash
   cd /home/burket/Git/BahnVision/.worktrees/ui-design-upgrade
   docker compose up -d --build
   ```

2. **Test the live snapshot endpoint:**

   - Open browser to `http://localhost:8000/api/v1/heatmap/overview?time_range=live`
   - Note a station ID that has impact (e.g., `66563` for Essen Hbf)

3. **Test the station stats endpoint with live:**

   - Open `http://localhost:8000/api/v1/transit/stops/66563/stats?time_range=live`
   - Verify it returns **non-zero** data matching the overview

4. **Test the frontend popup:**

   - Open `http://localhost:3000` (or `http://localhost:5173` for dev)
   - Click on a station marker on the heatmap
   - Verify the popup shows actual cancellation/delay data instead of zeros

5. **Verify fallback still works:**
   - Test with `time_range=24h` to ensure database queries still work
   - `http://localhost:8000/api/v1/transit/stops/66563/stats?time_range=24h`

---

## Files Changed Summary

| File                                            | Change                           |
| ----------------------------------------------- | -------------------------------- |
| `backend/app/api/v1/endpoints/transit/stops.py` | Add live snapshot cache fallback |

---

## Notes

- This fix only addresses the `time_range=live` case
- Historical time ranges (1h, 6h, 24h, 7d, 30d) still query the database
- A separate investigation is needed for why the database has no data (see `investigate-realtime-stats-data.md`)
