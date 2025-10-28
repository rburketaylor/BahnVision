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
- Valkey and PostgreSQL are provisioned via Docker Compose locally and by platform teams in higher environments.
- Weather enrichment credentials arrive before Phase 2; until then, ingestion jobs remain disabled but table schemas exist.
- Synthetic load testing and uptime monitors will be set up during QA; metrics naming follows existing `bahnvision_*` conventions.

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
  - `id` (PK, UUID), `mvg_station_id` (TEXT, unique), `name` (TEXT), `latitude` (NUMERIC), `longitude` (NUMERIC), `zone` (TEXT), `last_seen_at` (TIMESTAMP).  
  - Indexed on `mvg_station_id`, `name` (GIN trigram) for search.
- `departures`  
  - `id` (PK, UUID), `station_id` (FK stations.id), `line` (TEXT), `destination` (TEXT), `planned_time` (TIMESTAMP), `real_time` (TIMESTAMP), `platform` (TEXT), `transport_mode` (ENUM transport_mode), `status` (ENUM departure_status), `delay_seconds` (INT), `captured_at` (TIMESTAMP), `is_stale` (BOOLEAN).  
  - Index on `(station_id, captured_at DESC)` for history queries.
- `route_snapshots`  
  - `id` (PK, UUID), `origin_station_id` (FK), `destination_station_id` (FK), `requested_filters` (JSONB), `itineraries` (JSONB), `requested_at` (TIMESTAMP), `mv_g_status` (ENUM external_status).  
  - Partial index on `requested_at` for TTL clean-up tasks.
- `weather_observations`  
  - `id` (PK, UUID), `station_id` (FK optional), `source` (TEXT), `observed_at` (TIMESTAMP), `temperature_c` (NUMERIC), `precip_mm` (NUMERIC), `wind_speed_kmh` (NUMERIC), `conditions` (ENUM weather_condition), `ingestion_run_id` (FK).
- `ingestion_runs`  
  - `id` (PK, UUID), `source` (ENUM ingestion_source), `started_at` (TIMESTAMP), `completed_at` (TIMESTAMP), `status` (ENUM ingestion_status), `error_message` (TEXT nullable).

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
- `transport_mode`: `U_BAHN`, `S_BAHN`, `BUS`, `TRAM`, `REGIONAL`, `UNKNOWN`.
- `departure_status`: `ON_TIME`, `DELAYED`, `CANCELLED`, `BOARDING`, `ARRIVED`, `UNKNOWN`.
- `cache_status`: `hit`, `miss`, `stale`, `stale-refresh`.
- `external_status`: `SUCCESS`, `NOT_FOUND`, `RATE_LIMITED`, `DOWNSTREAM_ERROR`, `TIMEOUT`.
- `weather_condition`: `CLEAR`, `CLOUDY`, `RAIN`, `SNOW`, `STORM`, `FOG`, `UNKNOWN`.
- `ingestion_status`: `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `RETRYING`.
- `ingestion_source`: `MVG_DEPARTURES`, `MVG_STATIONS`, `WEATHER`.

## Error Cases
- 400 Bad Request: invalid UUIDs, conflicting route query params, unsupported transport modes.
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
10. Craft rollout playbook covering canary, rollback, and dashboard checklist. DoD: playbook stored in `docs/ops/`; reviewed with ops; links to dashboards and alert definitions.

