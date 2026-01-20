# Synthesized Station/Heatmap Issues (Deduped)

This document synthesizes the findings from `station-issues-codex.md`, `station-issues-claude.md`, and `station-issues-gemini.md` into a single set of **unique** points. Overlapping observations are merged; unique details from each report are preserved.

---

## 1) Why only a portion of stations appear

### A. Historical modes (1h/6h/24h/7d/30d): the backend intentionally returns “top impacted” stations, not “all stations”

- **Zoom-based hard cap (`max_points`)**: `resolve_max_points()` defaults to:
  - zoom < 10 → 500
  - zoom < 12 → 1000
  - else → 2000  
    The effective value is clamped by `MAX_DATA_POINTS = 10000`.  
    Location: `backend/app/services/heatmap_service.py` (`resolve_max_points`, `MAX_DATA_POINTS`)
- **Backend aggregation query is limited and sorted for impact**:
  - The DB query is ordered by an impact score (and departures) and applies `.limit(max_points)`.
  - The service also performs a defensive **sort + cap again** to keep semantics stable:
    - `key=lambda x: (x.delay_rate + x.cancellation_rate) * x.total_departures`
    - then `data_points = data_points[:max_points_effective]`  
      Location: `backend/app/services/heatmap_service.py` (`_aggregate_station_data_from_db`, post-processing in `get_cancellation_heatmap`)

Net effect: the historical heatmap is designed to show a bounded number of **most impacted** stations rather than “all stations”.

### B. Live mode: the snapshot itself only includes “impacted” stations

- The harvester builds a live snapshot where `data_points` is constructed from `impacted_stop_ids` only (stops with `cancelled > 0 or delayed > 0`). Stops with “no issues” never enter the live `data_points`.  
  Location: `backend/app/services/gtfs_realtime_harvester.py` (`_cache_live_snapshot`)
- The live endpoint further filters and caps returned points (including re-sorting by impact score and truncating to `max_points`).  
  Location: `backend/app/api/v1/endpoints/heatmap.py` (`_filter_live_snapshot`)

### C. Frontend behavior: “no impact” points are filtered out client-side

- Even if the backend returned “healthy” stations, the frontend map layer filters out points with `cancellation_rate` / `delay_rate` of 0 based on which metrics are enabled (cancellations, delays, or both).  
  Location: `frontend/src/components/heatmap/MapLibreHeatmap.tsx` (`toGeoJSON`)

### D. Summary vs. data-points mismatch (can look confusing)

There are two related mismatches that can make the UI feel “partial” even when the network summary is “full”:

- **Historical modes**:
  - `data_points` is capped (zoom/`max_points`), but `summary` is computed using a separate network-wide query with no `max_points` cap.
  - So you can see “network totals” that don’t correspond to just the displayed points.  
    Location: `backend/app/services/heatmap_service.py` (`_calculate_network_summary_from_db` vs `_aggregate_station_data_from_db`)
- **Live mode**:
  - The snapshot summary is computed from `by_stop` (i.e., all stops with any observed totals in the interval), but the snapshot `data_points` contains only impacted stops.
  - Additionally, when filtering live data by `transport_modes`, the endpoint recomputes `summary` from the filtered points; otherwise it uses the snapshot summary as-is.  
    Location: `backend/app/services/gtfs_realtime_harvester.py` (`_cache_live_snapshot`), `backend/app/api/v1/endpoints/heatmap.py` (`_filter_live_snapshot`)

---

## 2) Why delay/cancellation counts can look “odd”

### A. The counters are “GTFS-RT observation” counters, not “real departures”

- The system counts “trips observed in GTFS-RT trip updates / stop time updates” rather than scheduled departures or completed departures.
- Aggregation logic is driven by GTFS-RT observations and status classification within time buckets.  
  Locations: `backend/app/services/gtfs_realtime_harvester.py` (trip update ingestion + aggregation), `backend/app/services/heatmap_service.py` / `backend/app/services/station_stats_service.py` (reading sums)

### B. Delay classification is strict, and “minor delays” become “unknown”

- A trip is counted as **delayed** only if `delay > DELAY_THRESHOLD_SECONDS`, where `DELAY_THRESHOLD_SECONDS = 300` (5 minutes).
- A trip is counted as **on time** only if `abs(delay) < ON_TIME_THRESHOLD_SECONDS`, where `ON_TIME_THRESHOLD_SECONDS = 60` (1 minute).
- Delays between 60 and 300 seconds fall into **`STATUS_UNKNOWN`** and do not contribute to the “delayed” count.  
  Location: `backend/app/services/gtfs_realtime_harvester.py` (`DELAY_THRESHOLD_SECONDS`, `ON_TIME_THRESHOLD_SECONDS`, `_classify_status`)

### C. “Ever delayed within the bucket” + monotonic worsening can inflate “delayed” vs “current”

- The dedupe logic is designed so each trip contributes at most once per bucket, while allowing upgrades to worse statuses (on_time → delayed → cancelled).
- Once a trip is observed as delayed in a bucket, later improvements do not “undo” the delayed count for that bucket.  
  Location: `backend/app/services/gtfs_realtime_harvester.py` (`_apply_trip_statuses`)

### D. Buckets are aligned to harvest time, not necessarily event time

- The persistence bucketing is based on the harvester’s bucket start time (rounded to the hour), which may not align with a user’s intuition of “departures in the last hour” by event time.  
  Location: `backend/app/services/gtfs_realtime_harvester.py` (`harvest_once` bucket assignment)

---

## 3) Why data can look stale or “not updated”

### A. Refresh cadence mismatch (expected for current design)

- Harvester default interval is 300 seconds (5 minutes).  
  Location: `backend/app/core/config.py` (`gtfs_rt_harvest_interval_seconds`)
- Frontend polling cadence:
  - live: 1 minute
  - non-live: 5 minutes  
    Location: `frontend/src/hooks/useHeatmap.ts`

So in live mode, the UI may refetch more often than the underlying snapshot changes.

### B. Cache + stale fallback behavior (can amplify “why didn’t it change?”)

- Historical responses are cached, and the endpoint can return a stale entry while triggering a background refresh (`X-Cache-Status: stale-refresh`).  
  Location: `backend/app/api/v1/endpoints/heatmap.py`
- Operational validation mentioned in the reports: watch `X-Cache-Status` and Prometheus metrics at `/metrics` when checking freshness/behavior.
- Cache keys are stabilized by normalizing transport modes and using the _effective_ `max_points` rather than raw zoom.  
  Location: `backend/app/services/heatmap_cache.py`
- Live snapshot TTLs are longer than the frontend polling cadence by default (live cache TTL 600s, stale 1800s).  
  Location: `backend/app/core/config.py` (`heatmap_live_cache_ttl_seconds`, `heatmap_live_cache_stale_ttl_seconds`)

---

## 4) Why “show all stations” is hard without defining terms

Even beyond performance limits, “all stations” is ambiguous:

- All GTFS stops (including platforms), vs parent stations, vs only stops with any RT observations in the range (GTFS also provides `location_type` / `parent_station` to distinguish these shapes).
- “Stats” could mean observation coverage (what the current pipeline provides) vs schedule-based performance (what users often expect).

Frontend also intentionally hides “all-zero” stations today, and backend intentionally limits payload size.

---

## 5) Options to improve clarity and usefulness (deduped)

### A. Make “impact vs coverage” explicit (recommended for UX clarity)

- Keep the heatmap as an “impact map”, but add coverage indicators such as:
  - distinct observed stops in range
  - impacted stops in range
  - percent of stops with any observations
- Existing data sources mentioned in the reports:
  - feed/network ingestion status endpoint: `/api/v1/system/ingestion-status` (used for GTFS stop count context)
  - observed-stop counts from `realtime_station_stats`-backed queries
    Implementation location for the ingestion status endpoint (as referenced in the reports): `backend/app/api/v1/endpoints/ingestion.py`

### B. Reduce confusion from summary vs points mismatch

- Separate “map rendering payload” (bounded `data_points`) from “network summary” as distinct concepts in the UI.
- Alternatively, add a dedicated stats endpoint whose results are always computed network-wide (no `max_points` coupling).
- For live mode specifically, decide whether the snapshot summary should reflect:
  - all observed stations, or
  - only impacted stations (matching `data_points`), or
  - both (two summaries).

### C. Include healthy stations when desired

- Add a query param / toggle like “include_zero_impact=true” and thread it end-to-end.
- Live mode: build the snapshot from all `by_stop` stations (not just `impacted_stop_ids`) when requested.
- Frontend: disable/adjust the `toGeoJSON()` filtering when the toggle is enabled.

### D. Make payload limits less surprising

- Allow the frontend to request a higher `max_points` at high zoom, or increase defaults. One concrete suggestion from the reports:
  - zoom < 10: 1000 (was 500)
  - zoom < 12: 2500 (was 1000)
  - else: 5000 (was 2000)
- Consider switching from global top-N to viewport/bbox-based queries (bounded by what’s visible), plus clustering/paging.

### E. Make “delay” more representative of what users care about

- Lower `DELAY_THRESHOLD_SECONDS`, or add a separate “minor delay” bucket (e.g., 60–300 seconds) so it isn’t hidden as `STATUS_UNKNOWN`.
- Consider adding explicit “on-time” counts/rates to responses for a complete network-health picture.

### F. Move toward schedule-based performance metrics (bigger change)

- Compute denominators from scheduled departures (GTFS schedule tables) and compare RT delays/cancellations against those totals, if the goal is “true performance” rather than “RT observation status”.

### G. Reduce cardinality via parent-station aggregation

- Aggregate by `parent_station` where applicable to reduce point count and align with user expectations of “station-level” stats.  
  Location mentioned in reports: `backend/app/models/gtfs.py` (`GTFSStop.parent_station`)

---

## 6) Key code locations referenced across reports

- Backend endpoint + caching: `backend/app/api/v1/endpoints/heatmap.py`
- Backend aggregation + limiting: `backend/app/services/heatmap_service.py`
- Cache key helpers: `backend/app/services/heatmap_cache.py`
- Cache warmup job (mentioned): `backend/app/jobs/heatmap_cache_warmup.py`
- Harvester + semantics (live snapshot, status classification, bucketing): `backend/app/services/gtfs_realtime_harvester.py`
- Station stats service (mentioned): `backend/app/services/station_stats_service.py`
- Station stats endpoint (mentioned): `backend/app/api/v1/endpoints/transit/stops.py` (e.g., `/transit/stops/{stop_id}/stats` is backed by the same underlying counters)
- Heatmap models (mentioned): `backend/app/models/heatmap.py`
- Persistence model/table (mentioned): `backend/app/persistence/models.py` (`RealtimeStationStats`)
- GTFS stop model (parent station support): `backend/app/models/gtfs.py`
- Ingestion status endpoint (mentioned): `backend/app/api/v1/endpoints/ingestion.py`
- Frontend map filtering: `frontend/src/components/heatmap/MapLibreHeatmap.tsx`
- Frontend polling: `frontend/src/hooks/useHeatmap.ts`
- Frontend heatmap page/stats components (mentioned): `frontend/src/pages/HeatmapPage.tsx`, `frontend/src/components/heatmap/HeatmapStats.tsx`
