# BahnVision Backend Technical Specification

## Overview
- Deliver a production-ready FastAPI backend that serves MVG departures, station search, route planning, health, and Prometheus metrics with predictable latency and high cache efficiency.
- Persist departures, stations, weather context, and ingestion metadata so historical insights and Phase 2 predictive work can start without rework.
- Preserve clear operational boundaries by instrumenting cache efficiency, MVG latency, and stale fallbacks to uphold SLAs and inform alerting.

## Goals & Non-Goals
- Goals: harden caching and fallback behavior, ensure persistence layer readiness, document and expose operational signals, and prepare interfaces for frontend consumption.
- Non-Goals: frontend UX, AI recommendation features, authentication, or integrations beyond MVG and weather enrichment.

## Assumptions & Dependencies
- MVG API availability and rate limits remain the primary external dependency; circuit breaker and stale reads mitigate outages.
- Valkey and PostgreSQL 18 are provisioned via Docker Compose locally and by platform teams in higher environments.
- Weather enrichment credentials arrive before Phase 2; until then, ingestion jobs remain disabled but table schemas exist.
- Synthetic load testing and uptime monitors will be set up during QA; metrics naming follows existing `bahnvision_*` conventions.
- PostgreSQL 18 provides up to 3× I/O performance improvements, skip scan optimization for indexes, and page checksums by default.

## Architecture
```
                        +-------------------+
                        |   Prometheus/Graf |
                        | scrape /metrics   |
                        +---------+---------+
                                  |
                       /metrics   |
                                  v
      +--------------+    ASGI   +----------------------+
      | React/Leaflet|<--------->| FastAPI (app.main)   |
      | Frontend     |           |  Routes: departures, |
      +------+-------+           |  stations, routes,   |
             |                   |  health, metrics     |
   REST/JSON |                   +----+-----------+-----+
             |                        |           |
             |                        |           |
             |         Cache lookup   |           | asyncio tasks
             v                        v           v
      +------+-------+         +------+----+   +----------------+
      | Valkey Cache |<------->| Cache svc |   | Background     |
      +------+-------+         +-----------+   | refresh /      |
             ^                                  | single-flight |
             |                                  +-------+-------+
             |                                          |
   Stale/live data                                     |
             |                               MVG API polling/requests
             v                                          v
      +------+-------+                             +-----------+
      | PostgreSQL   |<----------------------------| MVG APIs  |
      | (stations,   |   Persist departures,       +-----------+
      | departures,  |   weather, ingestion runs    ^
      | weather)     |                              |
      +--------------+                        Weather Provider (Phase 2)
```

## Component Responsibilities
- `FastAPI app`: exposes REST endpoints, orchestrates cache + service calls, enforces validation via Pydantic models.
- `services/mvg_client.py`: wraps MVG API requests, handles rate limiting metadata, and captures timings for metrics.
- `services/cache_service.py`: mediates Valkey access, implements single-flight locking, stale responses, and circuit breaker.
- `services/departure_service.py`, `route_service.py`, `station_service.py`: aggregate MVG, cache, and persistence logic per domain.
- `services/weather_ingestor.py` (Phase 2 stub): orchestrates weather fetch and persistence.
- `models/`: request/response schemas shared with frontend; to be extended for persistence DTOs.
- PostgreSQL schema: stores canonical stations, historical departures, weather snapshots, and ingestion run state.
- Prometheus exporter: served under `/metrics`, sourced from instrumented caches, MVG calls, and route planning.

## Data Model
### PostgreSQL Tables
- `stations`
  - `station_id` (PK, String(64)), `name` (String(255)), `place` (String(255)), `latitude` (FLOAT), `longitude` (FLOAT), `transport_modes` (ARRAY(String(32))), `timezone` (String(64), default 'Europe/Berlin'), `created_at` (TIMESTAMP), `updated_at` (TIMESTAMP).
  - Primary key uses MVG station ID directly for simpler joins.
  - Indexed on `station_id` (PK), `name` (GIN trigram) for type-ahead search.
- `transit_lines`
  - `line_id` (PK, String(32)), `transport_mode` (ENUM transport_mode), `operator` (String(64), default 'MVG'), `description` (String(255)), `color_hex` (String(7)), `created_at` (TIMESTAMP).
  - Normalized line metadata to avoid duplication across departures.
- `departure_observations`
  - `id` (PK, BigInteger autoincrement), `station_id` (FK stations.station_id), `line_id` (FK transit_lines.line_id), `ingestion_run_id` (FK ingestion_runs.id, nullable), `direction` (String(255)), `destination` (String(255)), `planned_departure` (TIMESTAMP), `observed_departure` (TIMESTAMP, nullable), `delay_seconds` (INT, nullable), `platform` (String(16)), `transport_mode` (ENUM transport_mode), `status` (ENUM departure_status, default UNKNOWN), `cancellation_reason` (TEXT, nullable), `remarks` (ARRAY(String(255))), `crowding_level` (INT, nullable), `source` (String(64), default 'mvg'), `valid_from` (TIMESTAMP, nullable), `valid_to` (TIMESTAMP, nullable), `raw_payload` (JSONB, nullable), `created_at` (TIMESTAMP).
  - Indexes on `(station_id, planned_departure)` and `(line_id, planned_departure)` for efficient queries.
  - `raw_payload` preserves original MVG response for debugging and reprocessing.
  - Cache staleness tracked in Valkey, not as DB column.
- `route_snapshots`
  - `id` (PK, BigInteger autoincrement), `origin_station_id` (FK stations.station_id), `destination_station_id` (FK stations.station_id), `requested_filters` (JSONB), `itineraries` (JSONB), `requested_at` (TIMESTAMP), `mvg_status` (ENUM external_status), `created_at` (TIMESTAMP).
  - Partial index on `requested_at` for TTL clean-up tasks.
  - NOTE: Table currently missing in implementation, to be added in MS1-T2 migration.
- `weather_observations`
  - `id` (PK, BigInteger autoincrement), `station_id` (FK stations.station_id, nullable), `ingestion_run_id` (FK ingestion_runs.id, nullable), `provider` (String(64)), `observed_at` (TIMESTAMP), `latitude` (FLOAT), `longitude` (FLOAT), `temperature_c` (Numeric(5,2)), `feels_like_c` (Numeric(5,2)), `humidity_percent` (Numeric(5,2)), `wind_speed_mps` (Numeric(5,2)), `wind_gust_mps` (Numeric(5,2)), `wind_direction_deg` (INT), `pressure_hpa` (Numeric(6,2)), `visibility_km` (Numeric(5,2)), `precipitation_mm` (Numeric(5,2)), `precipitation_type` (String(32)), `condition` (ENUM weather_condition, default UNKNOWN), `alerts` (ARRAY(String(255))), `source_payload` (JSONB, nullable), `created_at` (TIMESTAMP).
  - Index on `(latitude, longitude, observed_at)` for geo-temporal matching.
  - Lat/lon stored directly to enable weather matching independent of station association.
- `ingestion_runs`
  - `id` (PK, BigInteger autoincrement), `job_name` (String(128)), `source` (ENUM ingestion_source), `started_at` (TIMESTAMP), `completed_at` (TIMESTAMP, nullable), `status` (ENUM ingestion_status, default RUNNING), `records_inserted` (INT, default 0), `notes` (TEXT, nullable), `context` (JSONB, nullable).
  - Index on `(job_name, started_at)` for monitoring queries.
  - `context` stores job-specific metadata (filters, batch IDs, etc.).
- `departure_weather_links`
  - `id` (PK, BigInteger autoincrement), `departure_id` (FK departure_observations.id), `weather_id` (FK weather_observations.id), `offset_minutes` (INT), `relationship_type` (String(32), default 'closest').
  - Unique constraint on `(departure_id, weather_id)`.
  - Enables Phase 2 weather enrichment with many-to-many relationships and temporal offsets.

### Valkey Keys
- `departures:{station_id}` → serialized `DepartureList` with metadata (`cache_status`, `ttl`, `last_refresh`).
- `stations:search:{prefix}` → list of station ids/names for type-ahead, with short TTL (e.g., 5 min).
- `routes:{origin}:{destination}:{filters_hash}` → itinerary payload + timestamp + `cache_status`.
- `notfound:{resource}:{key}` → marker entries with short TTL to de-duplicate downstream load.
- `locks:{resource}:{key}` → single-flight lock keys (set with short expiry).

## Interfaces (REST, v1)
- `GET /api/v1/health`  
  - Request: none.  
  - Response: `{ "status": "ok", "version": str, "uptime_seconds": int }`.  
  - Cache: none.
- `GET /api/v1/mvg/departures?station_id=uuid&limit=int&transport_modes=List[str]`  
  - Response: `{ "station": Station, "departures": List[Departure], "cache_status": CacheStatus, "generated_at": datetime }`.  
  - Behavior: prefer cache hit; on miss fetch MVG, persist, refresh cache; include `X-Cache-Status` header.
- `GET /api/v1/mvg/stations/search?q=str&limit=int`  
  - Response: `{ "results": List[StationSummary], "cache_status": CacheStatus }`.  
  - Behavior: read-through cache; 404 when no matches.
- `GET /api/v1/mvg/routes/plan?origin=uuid&destination=uuid&transport_modes=List[str]&departure_time=datetime&arrival_time=datetime`  
  - Response: `{ "origin": Station, "destination": Station, "itineraries": List[Itinerary], "cache_status": CacheStatus, "ttl_seconds": int }`.  
  - Validation: reject simultaneous departure+arrival times; respect MVG filters; 404 when MVG returns none.
- `GET /metrics`  
  - Response: Prometheus exposition format.  
  - Behavior: must be unauthenticated but protected via network-level controls when public.

### Internal/Background Interfaces
- `WeatherIngestor.run()` (Phase 2): triggered via scheduler, fetches weather API, stores in `weather_observations`.
- `CacheRefresher.enqueue(station_id)` invoked on stale reads to refresh asynchronously.

## Enums
- `transport_mode` (SQLAlchemy enum, implemented): `UBAHN`, `SBAHN`, `BUS`, `TRAM`, `REGIONAL`.
  - Used in `transit_lines.transport_mode` and `departure_observations.transport_mode`.
- `departure_status` (SQLAlchemy enum, implemented): `ON_TIME`, `DELAYED`, `CANCELLED`, `UNKNOWN`.
  - Used in `departure_observations.status`.
  - Note: BOARDING and ARRIVED states removed - MVG API doesn't consistently provide these.
- `weather_condition` (SQLAlchemy enum, implemented): `CLEAR`, `CLOUDY`, `RAIN`, `SNOW`, `STORM`, `FOG`, `MIXED`, `UNKNOWN`.
  - Used in `weather_observations.condition`.
- `cache_status` (application-level string, not DB enum): `hit`, `miss`, `stale`, `stale-refresh`.
  - Tracked in Valkey and returned in `X-Cache-Status` response header.
- `external_status` (to be implemented in MS1-T2): `SUCCESS`, `NOT_FOUND`, `RATE_LIMITED`, `DOWNSTREAM_ERROR`, `TIMEOUT`.
  - Will be used in `route_snapshots.mvg_status` to track MVG API response type.
- `ingestion_status` (to be implemented in MS1-T2): `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `RETRYING`.
  - Will replace String type in `ingestion_runs.status`.
- `ingestion_source` (to be implemented in MS1-T2): `MVG_DEPARTURES`, `MVG_STATIONS`, `WEATHER`.
  - Will replace String type in `ingestion_runs.source`.

## Error Cases
- 400 Bad Request: invalid UUIDs, conflicting route query params, unsupported transport modes.
- 422 Unprocessable Content: validation errors surfaced from FastAPI (RFC 9110 terminology, previously surfaced as Unprocessable Entity).
- 401/403: reserved for future auth integration; currently unused but documented for forward compatibility.
- 404 Not Found: unknown station in departures, no station matches in search, MVG route absence, missing cached resource markers.
- 409 Conflict: cache lock acquisition timeout exceeding 5 s while stale refresh already pending.
- 429 Too Many Requests: MVG rate limit reached; respond with cached stale data when possible, otherwise propagate 503 with retry header.
- 500 Internal Server Error: unhandled MVG errors, Valkey outages without stale fallback, serialization issues; log correlation id and emit `bahnvision_errors_total`.
- 503 Service Unavailable: MVG dependency unavailable and stale cache exhausted; include `Retry-After`.

## Observability
- Metrics (Prometheus):  
  - `bahnvision_cache_events_total{event="hit|miss|stale|refresh"}`  
  - `bahnvision_cache_refresh_duration_seconds` histogram (labels: `resource`, `status`).  
  - `bahnvision_mvg_requests_total{endpoint, status}` counter and `bahnvision_mvg_request_duration_seconds` histogram.  
  - `bahnvision_api_request_duration_seconds{route}` histogram from ASGI middleware.  
  - `bahnvision_api_exceptions_total{route, type}` counter.  
  - `bahnvision_weather_ingest_duration_seconds` (Phase 2).  
  - `process_cpu_seconds_total`, `process_resident_memory_bytes` via Prometheus client defaults.
- Logging: structured JSON logs with `request_id`, `station_id`, `cache_status`, `mvg_status`, `duration_ms`. Ensure log level separation for info, warning (stale fallback), error (dependency failure).
- Tracing: optional OpenTelemetry exporter hook; propagate `traceparent` header to MVG when provided.
- Alerts:  
  - Cache hit ratio <70% over 1 hr (warning), <55% (critical).  
  - MVG P95 latency >750 ms sustained 15 min.  
  - `bahnvision_api_exceptions_total` rate >5/min.  
  - Valkey connection errors >0 for 5 min (critical).  
  - `ingestion_runs` stuck in `RUNNING` >30 min.

## Rollout Plan
1. Development: implement schema migrations, caching adjustments, and instrumentation locally with Docker Compose; confirm endpoints via pytest + TestClient.
2. QA/Staging: deploy to staging cluster, replay synthetic load (20 rps) and verify cache hit ratio, latency, and metrics coverage; record baseline dashboards.
3. Pre-Production: enable Prometheus scraping, configure alert rules, validate fallback behavior by simulating MVG downtime.
4. Production Launch: perform canary rollout (10% traffic) with automated rollback on SLA violations; monitor for 24 hrs before full rollout.
5. Post-Launch: capture learnings, update dashboards, and schedule Phase 2 ingestion backlog grooming.

## Risks & Mitigations
- MVG API instability (rate limits/outages). Mitigation: aggressive caching, single-flight, fallback to stale data, alert on sustained failures.
- Valkey saturation or connection loss. Mitigation: connection pooling, circuit breaker to bypass cache with degraded warnings, readiness probes.
- Data growth in PostgreSQL due to historical departures. Mitigation: implement retention policy (e.g., 18-month partition pruning) and partitions by month.
- Weather ingestion dependency timing (RISK). Mitigation: treat as optional until credentials ready; feature-flag ingestion jobs.
- Observability gaps if metrics naming diverges. Mitigation: enforce instrumentation review, align dashboards with spec.
- Configuration drift between environments. Mitigation: centralize env var defaults in `core/config.py`, document overrides.

## Task DAG
```
[A] Finalize DB schema & migrations
  └─>[B] Update services to read/write persistence layer
       ├─>[C] Enhance cache layer (single-flight, stale headers)
       │    └─>[D] Expose cache/mvg metrics & alerts
       └─>[E] Persist route snapshots & weather stubs
             └─>[F] Document readiness & rollout procedures
```

## Numbered Backlog & Definition of Done
1. Implement Alembic migrations for stations, departures, routes, weather, ingestion tables. DoD: migrations run locally/staging; rollback tested; schema documented in README.
2. Extend service layer to write departures and routes to PostgreSQL after MVG fetch. DoD: unit tests for persistence paths; manual verification via sqlite/psql; cache headers unaffected.
3. Harden Valkey cache with single-flight locks and stale-refresh metadata headers. DoD: integration tests simulate concurrent hits; `X-Cache-Status` covers new paths; metrics reflect refresh outcomes.
4. Instrument Prometheus metrics for MVG latency, cache events, and API timings. DoD: `/metrics` exposes counters/histograms under load; dashboard queries return data; alert rules committed.
5. Add structured logging & correlation IDs across services. DoD: log format documented; request/response correlation validated; sensitive data scrubbed.
6. Persist not-found markers and enforce 15 s TTL for empty route results. DoD: functional test verifies caching suppression of duplicate misses; metrics mark `NOT_FOUND`.
7. RISK Build retention job to prune departures older than 18 months. DoD: job dry-run logged; safe-guards for production; monitoring for row counts.
8. ? Define MVG latency SLA thresholds and alerting with product/ops. DoD: agreement recorded in design-doc; alert config updated; runbook linked.
9. Create QA load test suite hitting departures, search, route endpoints at 20 rps. DoD: script checked into `backend/tests/load`; baseline latency captured; failure thresholds scripted.
10. Craft rollout playbook covering canary, rollback, and dashboard checklist. DoD: playbook stored in `backend/docs/ops/`; reviewed with ops; links to dashboards and alert definitions.
