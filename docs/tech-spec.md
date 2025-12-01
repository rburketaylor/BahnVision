# BahnVision Technical Specification

> **Document purpose:** Provide a current, end-to-end view of the BahnVision platform so engineering, product, and ops teams share a single source of truth for goals, architecture, and delivery constraints. This supplements (not replaces) domain-specific docs under `backend/docs` and `frontend/docs`.

## 1. Product Overview

BahnVision delivers live and near-real-time Munich public transit insights. A FastAPI backend aggregates MVG data, applies cache-first logic for predictable latency, and stores canonical transit data in PostgreSQL. A React + TypeScript frontend renders departures, station search, and route planning with responsive UX optimized for desktop and kiosk displays. The system emphasizes:
- **Predictable latency:** Cache-first reads with single-flight locks, stale fallbacks, and Valkey circuit breakers.
- **Operational visibility:** Prometheus-native cache/MVG metrics; structured JSON logging and API-level metrics are planned.
- **Historical readiness (planned):** Async SQLAlchemy models exist for departures, weather, and ingestion metadata, but only the station catalog is persisted today; broader analytics storage is planned.

## 2. Goals & Non-Goals

| Goals | Non-Goals |
| --- | --- |
| Serve departures, station search, routing, health, and metrics via versioned REST APIs. | Authentication/authorization, account management, or paid tiers. |
| Maintain >70% cache hit ratio and <750 ms MVG P95 latency via Valkey caching strategies. | Replacing MVG as the source of truth or supporting other cities in MS1. |
| Provide a frontend that mirrors backend capabilities with resilient API integration and optimistic UI for slow paths. | Complex UX experiments, brand-new design systems, or offline PWAs. |
| Persist canonical transit and weather data so forecasting work can start without schema churn (planned; stations only today). | Real-time GTFS streaming ingestion (deferred), ML forecasting pipelines (Phase 2). |
| Export Prometheus metrics and structured logs suitable for automation and alerting. | Proprietary APM integrations beyond Prometheus/Grafana. |

## 3. Personas & Key User Flows

- **Daily commuter:** Quickly checks departures and reroute suggestions with <2 clicks; expects stale-but-fresh data when MVG lags.
- **Transit ops analyst:** Pulls station metadata and historical departures via API for planning dashboards.
- **Frontend QA:** Uses mock data and MSW to validate UI states without hitting MVG.
- **SRE/on-call:** Monitors cache efficiency, MVG request health, and circuit-breaker events to keep SLAs intact.

Primary flows:
1. Station search → select station → view departures (with filters for transport type, limit, offset).
2. Route planning between station pairs → display top options with ETA deltas and fallback notes.
3. Health/metrics monitoring via `/api/v1/health` and `/metrics`.
4. Cache warmup job hydrates MVG station catalog before the API serves traffic.

## 4. Functional Scope

### Backend APIs (FastAPI, `/api/v1`)

| Endpoint | Description | Cache TTL / Strategy |
| --- | --- | --- |
| `GET /mvg/stations/search` | Autocomplete stations by free-text query. | Configurable TTL (`MVG_STATION_SEARCH_CACHE_TTL_SECONDS`) + stale TTL; single-flight lock avoids duplicate upstream calls. |
| `GET /mvg/stations/list` | Get all MVG stations. | Heavily cached with long TTL (`MVG_STATION_LIST_CACHE_TTL_SECONDS`) and stale fallback. |
| `GET /mvg/departures` | Live departures for a station with optional transport filter, limit, and offset. | TTL (`MVG_DEPARTURES_CACHE_TTL_SECONDS`) + stale fallback + circuit breaker to in-process store. |
| `GET /mvg/routes/plan` | Simple route planning; includes MVG route fallback metadata. | TTL (`MVG_ROUTE_CACHE_TTL_SECONDS`); refresh in background when stale served. |
| `GET /health` | Readiness and dependency probes (Valkey, Postgres, MVG reachability). | Non-cached; returns `503` when critical dependencies down. |
| `GET /metrics` | Prometheus metrics exported via `app.api.metrics`. | N/A |

### Frontend Surface (React 19 + Vite)

- **Pages:** Landing dashboard (departures + quick search), station search results, route planner, observability/devtools gates.
- **State/Data:** TanStack Query for API data, React Context for app config (locale, theme), Tailwind for styling.
- **Offline/Error UX:** Displays cached/stale banners using `X-Cache-Status`; MSW-backed fallback for dev/testing.

## 5. Non-Functional Requirements

- **Latency:** P95 API request latency <500 ms when MVG healthy, <900 ms with stale fallback.
- **Availability:** 99.5% for backend API; measured via `/health` checks and circuit-breaker failovers.
- **Data freshness:** Departures must be ≤60 s stale when MVG reachable; station catalog refresh nightly via warmup job or manual trigger.
- **Observability:** Cache and MVG Prometheus metrics are emitted; API-level latency/exception metrics and structured JSON logging are planned. Request IDs are injected into responses for correlation.
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
    |-- MVGClient --> MVG API (retry/backoff, metrics)
    |-- /metrics exporter --> Prometheus/Grafana
    '-- Background jobs (cache warmup, stale refresh)
```

**Key components**
- `app.main` bootstraps FastAPI with lifespan hooks to initialize Valkey, SQLAlchemy engine, and metrics.
- `services.cache.CacheService` abstracts cache access, stale reads, and fallback store.
- `services.mvg_client.MVGClient` encapsulates MVG API calls, instrumentation, and error mapping.
- `persistence.repositories` provide async CRUD; currently the station catalog is persisted, with departures/weather/routing persistence planned.
- `app.jobs.cache_warmup` populates Valkey/Postgres before traffic.
- Frontend consumes backend APIs through `frontend/src/services/httpClient.ts` and `frontend/src/services/endpoints/mvgApi.ts`, with TanStack Query caching plus background updates.

## 7. Backend Design Notes

- **Dependency Injection:** FastAPI dependencies wire config, cache, MVG client, and repositories per request to keep services stateless.
- **Caching Paths:** Cache keys include resource + params (e.g., `departure:{station}:{transport}:{limit}:{offset}`) with `:stale` suffix for fallback copy. Single-flight locks use TTL (`CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`) and wait/retry knobs to prevent thundering herds.
- **Circuit Breaker:** When Valkey is unreachable, an in-process fallback store caches recent responses with opportunistic cleanup; breaker timeout controlled by `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`.
- **Persistence:** Async SQLAlchemy models map to tables such as `stations`, `transit_lines`, `departure_observations`, `route_snapshots`, `weather_observations`, `ingestion_runs`. The API currently persists and reads the station catalog; deeper historical storage is planned (Phase 2).
- **Warmup Flow:** Docker Compose runs `cache-warmup` service first to hydrate station catalog (and optional departures) using env knobs `CACHE_WARMUP_DEPARTURE_*`.
- **Error Handling:** Validation errors return 422, MVG not found returns 404 with descriptive payload, cache lock conflicts return 409 after >5 s wait, upstream outages return 503 with `Retry-After`.

## 8. Frontend Design Notes

- **Stack:** Vite + React 19 + TypeScript, Tailwind CSS, TanStack Query, React Router, Vitest + Testing Library.
- **API Service Layer:** `httpClient.ts` handles base URL (`VITE_API_BASE_URL`), timeout, and headers; `endpoints/mvgApi.ts` wraps backend routes for health, stations, departures, routes, and metrics.
- **State Management:** Query keys align with backend cache semantics (station, transport, pagination). Stale-while-refetch keeps UI responsive during MVG slowdowns.
- **Routing & Pages:** Current pages include `/` (landing/search), `/departures/:stationId`, `/planner`, and `/insights`. Map overlays are planned but not yet implemented.
- **Testing:** Vitest + RTL for components/hooks; MSW mocks backend endpoints. Playwright E2E is planned once flows are stabilized.

## 9. Data & Schema Highlights

| Table | Purpose | Notes |
| --- | --- | --- |
| `stations` | Canonical MVG station metadata. | PK is MVG station ID; trigram index on `name` for lookup. |
| `transit_lines` | Static line metadata (mode, operator, branding). | Avoids duplication in departures. |
| `departure_observations` | Historical departures with schedule vs. realtime deltas. | Stores `planned_departure`, `actual_departure`, `delay_seconds`, `transport_mode`. |
| `route_snapshots` | Cached route planner responses with MVG status, legs, and fares. | Future fields: `external_status` enum for MVG outcomes. |
| `weather_observations` | Weather context per station/time bucket. | Supports `weather_condition` enum for analytics. |
| `ingestion_runs` | Tracks batch jobs (stations, departures, weather). | Will adopt enums `ingestion_status`/`ingestion_source`. |

Valkey stores serialized Pydantic responses (JSON) using TTL + stale TTL pairs for each endpoint.

## 10. Infrastructure & Deployment

- **Local:** `docker compose up --build` runs Valkey, Postgres, backend, frontend, cache warmup. Alternatively run backend via `uvicorn` and frontend via `npm run dev`.
- **Configuration:** Managed via env vars (`VALKEY_URL`, `DATABASE_URL`, `CACHE_*`, `MVG_*_TTL_SECONDS`, `VITE_API_BASE_URL`). `.env.example` documents defaults; see `docs/runtime-configuration.md`.
- **Build/Test:** Backend uses `pytest`; frontend uses `npm run test` (Vitest) and `npm run lint`. CI should run both plus Playwright smoke if containerized MVG stubs available.
- **Release Flow:** Build Docker images for backend/frontend; deploy with Compose, Kubernetes (example manifests in `examples/k8s/`), or platform-specific pipelines. Ensure `cache-warmup` job runs before switching traffic.

## 11. Observability & Operations

### 11.1 Current Observability

**Metrics (Prometheus)**
Exposed at `/metrics` via `app.api.metrics`.
- **Cache Performance:**
  - `bahnvision_cache_events_total{cache,event}`: Counters for `hit`, `miss`, `stale_return`, `refresh_success`, `refresh_error`.
  - `bahnvision_cache_refresh_seconds{cache}`: Histogram of background refresh duration.
- **MVG Client:**
  - `bahnvision_mvg_requests_total{endpoint,result}`: Counters for upstream calls (results: `success`, `http_error`, `timeout`, `parse_error`).
  - `bahnvision_mvg_request_seconds{endpoint}`: Latency histogram for MVG calls.
- **Transport breakdown:**
  - `bahnvision_mvg_transport_requests_total{endpoint,transport_type,result}`: Counters for MVG calls by transport type.
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

**MVG P95 Latency**
```promql
histogram_quantile(0.95, sum(rate(bahnvision_mvg_request_seconds_bucket[5m])) by (le, endpoint))
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
  "route": "/api/v1/mvg/departures",
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
  "endpoint": "mvg_departures",
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
2. **MVG Health:** Request failure rate > 5/min OR `result=timeout` spikes.
3. **System Health:** `/health` latency > 1s OR error rate > 1%.
4. **Resilience:** Circuit breaker engaged > 2 min sustained.

## 12. Testing & Quality Strategy

- **Backend:** `pytest backend/tests` with FastAPI `TestClient`, dependency overrides for MVG/Valkey doubles, and DB fixtures using async engine + transactions. Include regression tests for caching (hit, stale, lock timeout) and MVG error mapping.
- **Frontend:** Vitest + React Testing Library for components, hooks, and service layer; MSW mocks API utilities. Snapshot/stylings limited to leaf components.
- **Integration:** Compose-based smoke tests hit real containers; Playwright suite interacts with running frontend + backend. Optional contract tests ensure API schema compatibility with frontend expectations.
- **Performance:** Use Locust or k6 to validate cache hit ratio and MVG latency budgets before releases.

## 13. Security & Compliance

- Secrets/config stored in env vars; never commit credentials.  
- Backend enforces FastAPI validation to prevent injection; SQLAlchemy uses bound parameters.  
- Rate limiting relies on MVG policies plus circuit breaker; consider API gateway quotas if public exposure increases.  
- CORS defaults to frontend origin; configure `VITE_API_BASE_URL` accordingly.  
- Future work: integrate request signing or API keys once third-party consumers onboard.

## 14. Risks & Open Questions

| Area | Risk / Question | Mitigation |
| --- | --- | --- |
| MVG API stability | Prolonged outages could exhaust stale cache. | Increase stale TTL, precompute fallback departures, coordinate with MVG SLA contacts. |
| PostgreSQL growth | Historical departures + weather may balloon storage. | Partition tables by day/week, implement TTL archival job once Phase 2 begins. |
| Frontend data drift | Backend schema changes may break frontend query typings. | Maintain shared OpenAPI schema + automated client generation or contract tests. |
| Warmup sequencing | Cache-warmup failure could leave API cold. | Fail fast in Compose/K8s if warmup exits non-zero; provide manual rerun docs. |
| Structured logging | Pending decision on log format & sink. | Align with platform logging stack (e.g., Loki) before GA. |

## 15. Change Log

| Date | Revision | Notes |
| --- | --- | --- |
| 2024-XX-XX | v0.1 | Initial consolidated tech spec drafted for collaborative edits. |

---

_Next steps:_ Review with backend/frontend leads, then link this document from `README.md` and area-specific hubs once approved.
