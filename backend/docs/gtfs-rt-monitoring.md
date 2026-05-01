# GTFS-RT Monitoring Dashboard Documentation

This document describes the monitoring infrastructure for GTFS-RT (realtime) data ingestion and provides guidance for interpreting harvester status, adding metrics, and configuring alerts.

## Overview

BahnVision monitors GTFS-RT data ingestion through a combination of:

- **Status Endpoints**: REST API endpoints for health and ingestion status
- **Prometheus Metrics**: Application-level metrics exposed at `/metrics`
- **Grafana Dashboard**: Visual monitoring dashboard for operators

The GTFS-RT harvester (`backend/app/services/gtfs_realtime_harvester.py`) runs as a background service, polling the Deutsche Bahn GTFS-RT feed and aggregating trip updates into station-level statistics.

## Existing Status Endpoints

### `/api/v1/health`

Lightweight liveness probe with uptime and version info.

**Response (200 OK):**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 3600.5
}
```

**Use case:** Kubernetes liveness probe to verify the application process is running.

### `/api/v1/ready`

Dependency readiness probe for database and cache.

**Response (200 OK):**

```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "cache": "ok"
  },
  "errors": {}
}
```

**Response (503 Service Unavailable):**

```json
{
  "status": "not_ready",
  "checks": {
    "database": "error",
    "cache": "ok"
  },
  "errors": {
    "database": "connection refused"
  }
}
```

**Use case:** Kubernetes readiness probe to verify the application can serve requests.

### `/api/v1/system/ingestion-status`

Combined status for GTFS static feed imports and GTFS-RT harvester.

**Response (200 OK):**

```json
{
  "gtfs_feed": {
    "feed_id": "DE",
    "feed_url": "https://...",
    "downloaded_at": "2026-02-15T06:00:00Z",
    "feed_start_date": "2026-02-15",
    "feed_end_date": "2026-03-15",
    "stop_count": 42000,
    "route_count": 1500,
    "trip_count": 850000,
    "is_expired": false,
    "import_progress": {
      "state": "running",
      "phase": "copy_stop_times",
      "message": "Copying stop_times.txt",
      "percent": 72.4,
      "rows_processed": 36200000,
      "rows_total": 50000000,
      "started_at": "2026-02-15T06:00:00Z",
      "updated_at": "2026-02-15T06:12:00Z",
      "finished_at": null,
      "error_type": null,
      "error_message": null
    }
  },
  "gtfs_rt_harvester": {
    "is_running": true,
    "last_harvest_at": "2026-02-15T10:30:00Z",
    "stations_updated_last_harvest": 15420,
    "total_stats_records": 2500000
  }
}
```

**Use case:** Operational monitoring dashboard to verify data ingestion health.

The `gtfs_feed.import_progress` object reports the static GTFS importer state.
Poll `/api/v1/system/ingestion-status` while `state` is `running` to watch live
phase, percentage, and `stop_times.txt` row counts. `failed` and `succeeded`
records remain visible for 24 hours, or until the next import starts.

| Field            | Type              | Description                                                                  |
| ---------------- | ----------------- | ---------------------------------------------------------------------------- |
| `state`          | string            | `idle`, `running`, `succeeded`, or `failed`.                                 |
| `phase`          | string or null    | Current phase, such as `download`, `copy_stop_times`, `analyze`, `complete`. |
| `message`        | string or null    | Human-readable current importer activity.                                    |
| `percent`        | number or null    | Weighted import completion percentage.                                       |
| `rows_processed` | integer or null   | Rows copied for `stop_times.txt` when that phase is active.                  |
| `rows_total`     | integer or null   | Total `stop_times.txt` data rows when known.                                 |
| `started_at`     | timestamp or null | Import start time.                                                           |
| `updated_at`     | timestamp or null | Last progress update time.                                                   |
| `finished_at`    | timestamp or null | Completion or failure time.                                                  |
| `error_type`     | string or null    | Exception class name for failed imports.                                     |
| `error_message`  | string or null    | Exception message for failed imports, without traceback details.             |

## Existing Prometheus Metrics

Defined in `backend/app/core/metrics.py`:

| Metric                                        | Type      | Labels                                 | Description                                 |
| --------------------------------------------- | --------- | -------------------------------------- | ------------------------------------------- |
| `bahnvision_cache_events_total`               | Counter   | `cache`, `event`                       | Cache operations (hit, miss, refresh, etc.) |
| `bahnvision_cache_refresh_seconds`            | Histogram | `cache`                                | Cache refresh latency                       |
| `bahnvision_transit_requests_total`           | Counter   | `endpoint`, `result`                   | Outbound Transit API requests               |
| `bahnvision_transit_request_seconds`          | Histogram | `endpoint`                             | Transit API request latency                 |
| `bahnvision_transit_transport_requests_total` | Counter   | `endpoint`, `transport_type`, `result` | Transit requests per transport type         |

**Access:** All metrics are exposed at `/metrics` for Prometheus scraping.

## Existing Grafana Dashboard

Location: `observability/grafana/dashboards/bahnvision-observability.json`

### Current Panels

1. **Container CPU Usage** - CPU utilization per service (timeseries)
2. **Container Memory Working Set** - Memory usage per service (timeseries)
3. **Container Filesystem Usage** - Disk usage per service (timeseries)
4. **Container Network Throughput** - Network I/O per service (timeseries)
5. **Transit Request Rate (5m)** - Requests per second (stat gauge)
6. **Transit Request p95 Latency (5m)** - 95th percentile latency (stat gauge)
7. **JSON Cache Hit Rate (5m)** - Cache efficiency percentage (stat gauge)
8. **Backend Events and Request Outcomes** - Combined event rate timeseries

**Dashboard refresh:** 30 seconds
**Default time range:** Last 6 hours

## Interpreting GTFS-RT Harvester Status

The `gtfs_rt_harvester` object from `/api/v1/system/ingestion-status` contains:

| Field                           | Type                | Meaning                                                                                                                                                           |
| ------------------------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `is_running`                    | boolean             | Harvester background loop is active. If `false`, no realtime data is being collected.                                                                             |
| `last_harvest_at`               | datetime (ISO 8601) | Timestamp of the most recent harvest cycle completion. Stale values indicate the harvester may be stuck or the feed is unreachable.                               |
| `stations_updated_last_harvest` | integer             | Number of unique station-route combinations updated in the last cycle. Zero may indicate: (1) empty feed, (2) all trips filtered, or (3) GTFS import lock active. |
| `total_stats_records`           | integer             | Approximate row count in `realtime_station_stats` table. Used for storage monitoring.                                                                             |

### Status Interpretation Guide

| Scenario           | `is_running` | `last_harvest_at` | `stations_updated` | Action                                   |
| ------------------ | ------------ | ----------------- | ------------------ | ---------------------------------------- |
| Normal operation   | `true`       | Recent (< 10 min) | > 0                | None                                     |
| Harvester stopped  | `false`      | Stale             | Any                | Restart harvester, check logs            |
| Feed unreachable   | `true`       | Stale             | 0                  | Check network, feed URL, API credentials |
| Empty feed         | `true`       | Recent            | 0                  | Verify feed is publishing data           |
| Import lock active | `true`       | Recent            | 0                  | Wait for GTFS import to complete         |

## Recommended Metrics to Add for GTFS-RT

The following metrics would enhance GTFS-RT monitoring visibility:

### Harvest Cycle Metrics

| Metric Name                             | Type      | Labels                               | Purpose                         |
| --------------------------------------- | --------- | ------------------------------------ | ------------------------------- |
| `bahnvision_gtfs_rt_harvest_total`      | Counter   | `result` (success, failure, skipped) | Count of harvest cycle outcomes |
| `bahnvision_gtfs_rt_harvest_seconds`    | Histogram | -                                    | Duration of each harvest cycle  |
| `bahnvision_gtfs_rt_feed_fetch_seconds` | Histogram | `result` (success, error, timeout)   | Time to fetch GTFS-RT feed      |
| `bahnvision_gtfs_rt_feed_bytes`         | Histogram | -                                    | Size of GTFS-RT feed response   |

### Data Volume Metrics

| Metric Name                                 | Type    | Labels                        | Purpose                                  |
| ------------------------------------------- | ------- | ----------------------------- | ---------------------------------------- |
| `bahnvision_gtfs_rt_trip_updates_total`     | Counter | -                             | Total trip updates received              |
| `bahnvision_gtfs_rt_stations_updated_total` | Counter | -                             | Total station-route combinations updated |
| `bahnvision_gtfs_rt_stops_matched_total`    | Counter | `result` (matched, unmatched) | Stop ID lookup success rate              |

### Status Classification Metrics

| Metric Name                                 | Type    | Labels                                          | Purpose                  |
| ------------------------------------------- | ------- | ----------------------------------------------- | ------------------------ |
| `bahnvision_gtfs_rt_trips_classified_total` | Counter | `status` (on_time, delayed, cancelled, unknown) | Trip status distribution |

### Cache/Database Metrics

| Metric Name                                 | Type      | Labels                                                          | Purpose                      |
| ------------------------------------------- | --------- | --------------------------------------------------------------- | ---------------------------- |
| `bahnvision_gtfs_rt_cache_operations_total` | Counter   | `operation` (get, set, mget, mset), `result` (hit, miss, error) | Trip marker cache efficiency |
| `bahnvision_gtfs_rt_db_upsert_seconds`      | Histogram | -                                                               | Database upsert latency      |

## Recommended Dashboard Panels for GTFS-RT

Add the following panels to the Grafana dashboard for GTFS-RT visibility:

### Row 1: Harvest Health

1. **Harvester Status** (stat gauge)

   - Query: `bahnvision_gtfs_rt_harvest_total{result="success"} / bahnvision_gtfs_rt_harvest_total`
   - Display: Success rate percentage

2. **Harvest Cycle Duration** (timeseries)

   - Query: `rate(bahnvision_gtfs_rt_harvest_seconds_bucket[5m])`
   - Display: p50, p95, p99 latency

3. **Feed Fetch Latency** (timeseries)
   - Query: `rate(bahnvision_gtfs_rt_feed_fetch_seconds_bucket[5m])`
   - Display: p95 latency over time

### Row 2: Data Volume

4. **Trip Updates Rate** (timeseries)

   - Query: `rate(bahnvision_gtfs_rt_trip_updates_total[5m])`
   - Display: Updates per second

5. **Stations Updated Rate** (timeseries)

   - Query: `rate(bahnvision_gtfs_rt_stations_updated_total[5m])`
   - Display: Stations per harvest

6. **Feed Size** (timeseries)
   - Query: `rate(bahnvision_gtfs_rt_feed_bytes_bucket[5m])`
   - Display: Average feed size over time

### Row 3: Status Distribution

7. **Trip Status Breakdown** (pie chart)

   - Query: `sum by (status) (rate(bahnvision_gtfs_rt_trips_classified_total[5m]))`
   - Display: Proportion of on_time, delayed, cancelled, unknown

8. **Stop Match Rate** (stat gauge)
   - Query: `rate(bahnvision_gtfs_rt_stops_matched_total{result="matched"}[5m]) / rate(bahnvision_gtfs_rt_stops_matched_total[5m])`
   - Display: Percentage of matched stops

### Row 4: Cache & Database

9. **Trip Marker Cache Hit Rate** (stat gauge)

   - Query: `rate(bahnvision_gtfs_rt_cache_operations_total{operation="get",result="hit"}[5m]) / rate(bahnvision_gtfs_rt_cache_operations_total{operation="get"}[5m])`
   - Display: Cache efficiency percentage

10. **DB Upsert Latency** (timeseries)
    - Query: `rate(bahnvision_gtfs_rt_db_upsert_seconds_bucket[5m])`
    - Display: p95 database write latency

## Recommended Alerting Rules

Based on the alerting rules defined in `docs/tech-spec.md` section 11.5, the following GTFS-RT specific alerts are recommended:

### Critical Alerts

| Alert Name                  | Condition                                         | Severity | Description                                    |
| --------------------------- | ------------------------------------------------- | -------- | ---------------------------------------------- |
| `GTFSRTHarvesterNotRunning` | `is_running == false` for > 2 min                 | critical | Harvester process has stopped                  |
| `GTFSRTHarvesterStale`      | `last_harvest_at` > 15 min ago                    | critical | Harvester is running but not completing cycles |
| `GTFSRTFeedFetchFailures`   | `rate(harvest_total{result="failure"}[5m]) > 0.5` | critical | > 50% of harvest cycles are failing            |

### Warning Alerts

| Alert Name                | Condition                                           | Severity | Description                                   |
| ------------------------- | --------------------------------------------------- | -------- | --------------------------------------------- |
| `GTFSRTFeedFetchLatency`  | `p95(feed_fetch_seconds) > 120s`                    | warning  | Feed fetch taking > 2 minutes                 |
| `GTFSRTLowStationUpdates` | `stations_updated_last_harvest == 0` for > 3 cycles | warning  | No stations being updated (may be empty feed) |
| `GTFSRTCacheHitRateLow`   | Cache hit rate < 50% for > 5 min                    | warning  | Trip deduplication cache ineffective          |
| `GTFSRTUpsertLatencyHigh` | `p95(db_upsert_seconds) > 30s`                      | warning  | Database writes are slow                      |

### Integration with Existing Alerts

The existing tech spec alerts (section 11.5) should be extended with GTFS-RT context:

- **Cache Efficiency:** Add GTFS-RT trip marker cache to the hit ratio alert
- **System Health:** Add `/api/v1/system/ingestion-status` endpoint latency monitoring
- **Resilience:** Monitor GTFS-RT feed fetch timeout and retry behavior

### Alert Routing

- Critical alerts: Page on-call, immediate investigation required
- Warning alerts: Notify via Slack, investigate during business hours
- All alerts: Include `last_harvest_at` timestamp and `stations_updated` count in alert context

## Implementation Notes

1. **Metrics Collection**: Add instrumentation to `GTFSRTDataHarvester.harvest_once()` method to record harvest outcomes, durations, and data volumes.

2. **Status Endpoint Enhancement**: Consider adding Prometheus-compatible metrics to `/api/v1/system/ingestion-status` response for easier scraping.

3. **Dashboard Updates**: Extend `bahnvision-observability.json` with GTFS-RT panels once metrics are implemented.

4. **Alert Configuration**: Add alert rules to Prometheus alertmanager configuration (not currently in repository).

## References

- Tech Spec Alerting Rules: `docs/tech-spec.md` section 11.5
- Prometheus Metrics: `backend/app/core/metrics.py`
- GTFS-RT Harvester: `backend/app/services/gtfs_realtime_harvester.py`
- Health Endpoints: `backend/app/api/v1/endpoints/health.py`
- Ingestion Status: `backend/app/api/v1/endpoints/ingestion.py`
- Grafana Dashboard: `observability/grafana/dashboards/bahnvision-observability.json`
