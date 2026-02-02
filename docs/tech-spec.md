# BahnVision Technical Specification

> **Document purpose:** Provide a current, end-to-end view of the BahnVision platform so engineering, product, and ops teams share a single source of truth for goals, architecture, and delivery constraints. This supplements (not replaces) domain-specific docs under `backend/docs` and `frontend/docs`.

## 1. Product Overview

BahnVision delivers live and near-real-time German public transit insights. A FastAPI backend aggregates GTFS data, applies cache-first logic for predictable latency, and stores canonical transit data in PostgreSQL. A React + TypeScript frontend renders departures, station search, and heatmap visualization with responsive UX optimized for desktop and kiosk displays. The system emphasizes:

- **Predictable latency:** Cache-first reads with single-flight locks, stale fallbacks, and Valkey circuit breakers.
- **Operational visibility:** Prometheus-native cache/transit metrics; structured JSON logging and API-level metrics are planned.
- **Historical readiness:** Async SQLAlchemy models and the `TransitDataRepository` support persisting Transit Lines, Departure Observations, Weather Observations, and Ingestion Runs. The station catalog and static GTFS data are actively persisted today; broader historical storage is planned for analytics.

## 2. Goals & Non-Goals

| Goals                                                                                                                         | Non-Goals                                                          |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Serve departures, station search, routing, health, and metrics via versioned REST APIs.                                       | Authentication/authorization, account management, or paid tiers.   |
| Maintain >70% cache hit ratio and <750 ms P95 latency via Valkey caching strategies.                                          | Supporting other countries beyond Germany in MS1.                  |
| Provide a frontend that mirrors backend capabilities with resilient API integration and optimistic UI for slow paths.         | Complex UX experiments, brand-new design systems, or offline PWAs. |
| Persist canonical transit and weather data so forecasting work can start without schema churn (planned; stations only today). | ML forecasting pipelines (Phase 2).                                |
| Export Prometheus metrics and structured logs suitable for automation and alerting.                                           | Proprietary APM integrations beyond Prometheus/Grafana.            |

## 3. Personas & Key User Flows

- **Daily commuter:** Quickly checks departures and reroute suggestions with <2 clicks; expects stale-but-fresh data when GTFS feeds lag.
- **Transit ops analyst:** Pulls station metadata and historical departures via API for planning dashboards.
- **Frontend QA:** Uses mock data and MSW to validate UI states without hitting live GTFS feeds.
- **SRE/on-call:** Monitors cache efficiency, transit request health, and circuit-breaker events to keep SLAs intact.

Primary flows:

1. Station search → select station → view departures (with filters for transport type, limit, offset).
2. Heatmap visualization of cancellation rates and transit activity.
3. Health/metrics monitoring via `/api/v1/health` and `/metrics`.
4. GTFS feed scheduler hydrates station catalog before the API serves traffic.

## 4. Functional Scope

### Backend APIs (FastAPI, `/api/v1`)

| Endpoint                     | Description                                                | Cache TTL / Strategy                                                                                                           |
| ---------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `GET /transit/stops/search`  | Autocomplete stops by free-text query.                     | Configurable TTL (`TRANSIT_STATION_SEARCH_CACHE_TTL_SECONDS`) + stale TTL; single-flight lock avoids duplicate upstream calls. |
| `GET /transit/departures`    | Live departures for a stop with optional limit and offset. | TTL (`TRANSIT_DEPARTURES_CACHE_TTL_SECONDS`) + stale fallback + circuit breaker to in-process store.                           |
| `GET /heatmap/cancellations` | Heatmap activity data for visualization.                   | TTL-based caching with stale fallback.                                                                                         |
| `GET /heatmap/overview`      | Lightweight heatmap overview for initial render.           | TTL-based caching with stale fallback.                                                                                         |
| `GET /health`                | Lightweight uptime/version probe.                          | Non-cached; returns `200` with version + uptime.                                                                               |
| `GET /metrics`               | Prometheus metrics exported via `app.api.metrics`.         | N/A                                                                                                                            |

Notes:

- `GET /heatmap/overview` supports a `metrics` query param (`cancellations`, `delays`, `both`) to control overview intensity.

### Frontend Surface (React 19 + Vite)

- **Pages:** Landing dashboard (departures + quick search), station search results, heatmap, observability/devtools gates.
- **State/Data:** TanStack Query for API data, React Context for app config (locale, theme), Tailwind for styling.
- **Offline/Error UX:** Displays cached/stale banners using `X-Cache-Status` (heatmap endpoints today); MSW-backed fallback for dev/testing.

## 5. Non-Functional Requirements

- **Latency:** P95 API request latency <500 ms when GTFS data available, <900 ms with stale fallback.
- **Availability:** 99.5% for backend API; measured via `/health` checks and circuit-breaker failovers.
- **Data freshness:** Departures must be ≤60 s stale when GTFS-RT reachable; station catalog refresh nightly via scheduler or manual trigger.
- **Observability:** Cache and transit Prometheus metrics are emitted; API-level latency/exception metrics and structured JSON logging are planned. Request IDs are injected into responses for correlation.
- **Security:** Secrets via environment variables; TLS termination handled upstream (reverse proxy / platform).
- **Scalability:** Horizontal scaling via ASGI workers and shared Valkey/Postgres; single shared async SQLAlchemy engine per process.

## 6. Architecture Overview

```
React (Vite) SPA
    |
    | HTTPS (REST/JSON)
    v
FastAPI app.main
    |-- Routers (/api/v1) --> Services --> Repositories --> PostgreSQL
    |-- CacheService <--> Valkey (single-flight, stale, circuit breaker)
    |-- GTFSScheduleService --> GTFS Feed (Germany-wide)
    |-- /metrics exporter --> Prometheus/Grafana
    '-- Background jobs (GTFS updates, stale refresh)
```

**Key components**

- `app.main` bootstraps FastAPI with lifespan hooks to initialize Valkey, SQLAlchemy engine, and metrics.
- `services.cache.CacheService` abstracts cache access, stale reads, and fallback store.
- `services.gtfs_schedule.GTFSScheduleService` provides GTFS data access and departure queries.
- `persistence.repositories.TransitDataRepository` provides async CRUD with support for Transit Lines, Departure Observations, Weather Observations, and Ingestion Runs; currently station catalog and static GTFS data are actively persisted, with broader historical storage planned for analytics.
- GTFS feed scheduler populates Valkey/Postgres before traffic.
- Frontend consumes backend APIs through `frontend/src/services/httpClient.ts` and `frontend/src/services/endpoints/transitApi.ts`, with TanStack Query caching plus background updates.

## 7. Backend Design Notes

- **Dependency Injection:** FastAPI dependencies wire config, cache, GTFS service, and repositories per request to keep services stateless.
- **Caching Paths:** Cache keys include resource + params (e.g., `departure:{stop_id}:{transport}:{limit}:{offset}`) with `:stale` suffix for fallback copy. Single-flight locks use TTL (`CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`) and wait/retry knobs to prevent thundering herds.
- **Circuit Breaker:** When Valkey is unreachable, an in-process fallback store caches recent responses with opportunistic cleanup; breaker timeout controlled by `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`.
- **Persistence:** Async SQLAlchemy models map to tables such as `gtfs_stops`, `gtfs_routes`, `gtfs_stop_times`, `gtfs_rt_observations`, `weather_observations`, `gtfs_feed_status`. The `TransitDataRepository` supports persisting Transit Lines, Departure Observations, Weather Observations, and Ingestion Runs. The API currently persists and reads the GTFS catalog; deeper historical storage for analytics is planned (Phase 2).
- **GTFS Flow:** GTFS feed scheduler downloads and imports Germany-wide GTFS data on startup and periodically.
- **Error Handling:** Validation errors return 422, station not found returns 404 with descriptive payload, cache lock conflicts return 409 after >5 s wait, upstream outages return 503 with `Retry-After`.

## 8. Frontend Design Notes

- **Stack:** Vite + React 19 + TypeScript, Tailwind CSS, TanStack Query, React Router, Vitest + Testing Library.
- **API Service Layer:** `httpClient.ts` handles base URL (`VITE_API_BASE_URL`), timeout, and headers; `endpoints/transitApi.ts` wraps backend routes for health, stops, departures, heatmap, and metrics.
- **State Management:** Query keys align with backend cache semantics (station, transport, pagination). Stale-while-refetch keeps UI responsive during data delays.
- **Routing & Pages:** Current pages include `/` (heatmap landing), `/search`, `/station/:stationId`, and `/monitoring`. Map overlays are implemented via MapLibre.
- **Heatmap basemap styles:** MapLibre GL style URLs (not raster tile URLs) configured via `VITE_HEATMAP_BASEMAP_STYLE_LIGHT` and `VITE_HEATMAP_BASEMAP_STYLE_DARK`. Defaults use CARTO positron/dark-matter styles (no API key required).
- **Testing:** Vitest + RTL for components/hooks; MSW mocks backend endpoints. Playwright E2E tests validate key flows.

## 9. Data & Schema Highlights

| Table                  | Purpose                                           | Notes                                              |
| ---------------------- | ------------------------------------------------- | -------------------------------------------------- |
| `gtfs_stops`           | GTFS stop metadata for Germany.                   | PK is GTFS stop_id; spatial index for geo queries. |
| `gtfs_routes`          | Static route metadata (mode, operator, branding). | Avoids duplication in departures.                  |
| `gtfs_stop_times`      | Scheduled stop times for trips.                   | Links trips to stops with arrival/departure times. |
| `gtfs_rt_observations` | Real-time GTFS-RT observations.                   | Stores delays, cancellations, vehicle positions.   |
| `weather_observations` | Weather context per station/time bucket.          | Supports `weather_condition` enum for analytics.   |
| `gtfs_feed_status`     | Tracks GTFS feed updates.                         | Records last update, next check, feed health.      |

Valkey stores serialized Pydantic responses (JSON) using TTL + stale TTL pairs for each endpoint.

## 10. Infrastructure & Deployment

- **Local:** `docker compose up --build` runs Valkey, Postgres, backend, frontend, GTFS scheduler. Alternatively run backend via `uvicorn` and frontend via `npm run dev`.
- **Configuration:** Managed via env vars (`VALKEY_URL`, `DATABASE_URL`, `CACHE_*`, `TRANSIT_*_TTL_SECONDS`, `VITE_API_BASE_URL`). `.env.example` documents defaults; see `docs/runtime-configuration.md`.
- **Build/Test:** Backend uses `pytest`; frontend uses `npm run test` (Vitest) and `npm run lint`. CI should run both plus Playwright smoke tests.
- **Release Flow:** Build Docker images for backend/frontend; deploy with Compose or platform-specific pipelines. Ensure GTFS data is loaded before switching traffic.

## 11. Observability & Operations

### 11.1 Current Observability

**Metrics (Prometheus)**
Exposed at `/metrics` via `app.api.metrics`.

- **Cache Performance:**
  - `bahnvision_cache_events_total{cache,event}`: Counters for `hit`, `miss`, `stale_return`, `refresh_success`, `refresh_error`.
  - `bahnvision_cache_refresh_seconds{cache}`: Histogram of background refresh duration.
- **Transit Client:**
  - `bahnvision_transit_requests_total{endpoint,result}`: Counters for upstream calls (results: `success`, `http_error`, `timeout`, `parse_error`).
  - `bahnvision_transit_request_seconds{endpoint}`: Latency histogram for transit data calls.
- **Transport breakdown:**
  - `bahnvision_transit_transport_requests_total{endpoint,transport_type,result}`: Counters for transit calls by transport type.
- **API-level metrics:** Not yet emitted; instrument ASGI middleware before alerting on API latency or exception rates.

**Logging**
Default FastAPI/Uvicorn logging is used. Request IDs are injected and propagated via `X-Request-Id`; structured JSON logging is planned.

### 11.2 Planned Observability (Phase 2)

- **API instrumentation:** Add ASGI middleware for `bahnvision_api_request_duration_seconds` and `bahnvision_api_exceptions_total`.
- **Weather Ingestion:** `bahnvision_weather_ingest_duration_seconds`.
- **Tracing:** OTLP exporter is wired; enable with `OTEL_ENABLED=true` and a reachable Jaeger/OTLP endpoint.
- **Frontend Correlation:** Ingesting client-side metrics to correlate user-perceived latency with backend processing time.

### 11.3 Common Dashboards & PromQL

**Cache Hit Ratio (5m window)**

```promql
sum(rate(bahnvision_cache_events_total{event="hit"}[5m]))
/
sum(rate(bahnvision_cache_events_total[5m]))
```

**Transit P95 Latency**

```promql
histogram_quantile(0.95, sum(rate(bahnvision_transit_request_seconds_bucket[5m])) by (le, endpoint))
```

**API Error Rate (planned metric)**

```promql
sum(rate(bahnvision_api_exceptions_total[5m])) by (route)
```

### 11.4 Log Examples

Structured JSON logging is planned; current logs follow FastAPI/Uvicorn defaults. Example formats:

**Successful Cache Hit (planned format)**

```json
{
  "level": "info",
  "timestamp": "2024-05-20T10:00:01Z",
  "request_id": "req-123",
  "event": "api_request_handled",
  "route": "/api/v1/transit/departures",
  "cache_status": "hit",
  "latency_ms": 12,
  "status_code": 200
}
```

**Upstream Failure with Stale Fallback (planned format)**

```json
{
  "level": "warning",
  "timestamp": "2024-05-20T10:05:00Z",
  "request_id": "req-456",
  "event": "upstream_error_handled",
  "endpoint": "transit_departures",
  "error": "TimeoutError",
  "fallback_action": "served_stale",
  "cache_age_seconds": 125
}
```

**Circuit Breaker Open (planned format)**

```json
{
  "level": "error",
  "timestamp": "2024-05-20T10:10:00Z",
  "event": "circuit_breaker_state_change",
  "service": "valkey",
  "new_state": "open",
  "reason": "failure_threshold_exceeded"
}
```

### 11.5 Alerting Rules

1. **Cache Efficiency:** Hit ratio < 70% for > 5 min.
2. **Transit Health:** Request failure rate > 5/min OR `result=timeout` spikes.
3. **System Health:** `/health` latency > 1s OR error rate > 1%.
4. **Resilience:** Circuit breaker engaged > 2 min sustained.

## 12. Testing & Quality Strategy

- **Backend:** `pytest backend/tests` with FastAPI `TestClient`, dependency overrides for GTFS/Valkey doubles, and DB fixtures using async engine + transactions. Include regression tests for caching (hit, stale, lock timeout) and error mapping.
- **Frontend:** Vitest + React Testing Library for components, hooks, and service layer; MSW mocks API utilities. Snapshot/stylings limited to leaf components.
- **Integration:** Compose-based smoke tests hit real containers; Playwright suite interacts with running frontend + backend. Optional contract tests ensure API schema compatibility with frontend expectations.
- **Performance:** Use Locust or k6 to validate cache hit ratio and latency budgets before releases.

## 13. Security & Compliance

- Secrets/config stored in env vars; never commit credentials.
- Backend enforces FastAPI validation to prevent injection; SQLAlchemy uses bound parameters.
- Rate limiting uses circuit breaker patterns; consider API gateway quotas if public exposure increases.
- CORS defaults to frontend origin; configure `VITE_API_BASE_URL` accordingly.
- Future work: integrate request signing or API keys once third-party consumers onboard.

## 14. Risks & Open Questions

| Area                   | Risk / Question                                          | Mitigation                                                                      |
| ---------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------- |
| GTFS feed availability | Prolonged outages could exhaust stale cache.             | Increase stale TTL, precompute fallback departures, monitor feed health.        |
| PostgreSQL growth      | Historical departures + weather may balloon storage.     | Partition tables by day/week, implement TTL archival job once Phase 2 begins.   |
| Frontend data drift    | Backend schema changes may break frontend query typings. | Maintain shared OpenAPI schema + automated client generation or contract tests. |
| Warmup sequencing      | Cache-warmup failure could leave API cold.               | Fail fast in Compose/K8s if warmup exits non-zero; provide manual rerun docs.   |
| Structured logging     | Pending decision on log format & sink.                   | Align with platform logging stack (e.g., Loki) before GA.                       |

## 15. Change Log

| Date       | Revision | Notes                                                           |
| ---------- | -------- | --------------------------------------------------------------- |
| 2024-XX-XX | v0.1     | Initial consolidated tech spec drafted for collaborative edits. |

---

_Next steps:_ Review with backend/frontend leads, then link this document from `README.md` and area-specific hubs once approved.
