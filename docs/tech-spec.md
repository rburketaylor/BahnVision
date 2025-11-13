# BahnVision Technical Specification

> **Document purpose:** Provide a current, end-to-end view of the BahnVision platform so engineering, product, and ops teams share a single source of truth for goals, architecture, and delivery constraints. This supplements (not replaces) domain-specific docs under `backend/docs` and `frontend/docs`.

## 1. Product Overview

BahnVision delivers live and near-real-time Munich public transit insights. A FastAPI backend aggregates MVG data, applies cache-first logic for predictable latency, and stores canonical transit data in PostgreSQL. A React + TypeScript frontend renders departures, station search, and route planning with responsive UX optimized for desktop and kiosk displays. The system emphasizes:
- **Predictable latency:** Cache-first reads with single-flight locks, stale fallbacks, and Valkey circuit breakers.
- **Operational visibility:** Prometheus-native metrics plus structured JSON logging with correlation IDs.
- **Historical readiness:** Async SQLAlchemy persistence for departures, stations, weather context, and ingestion metadata enables future analytics (Phase 2).

## 2. Goals & Non-Goals

| Goals | Non-Goals |
| --- | --- |
| Serve departures, station search, routing, health, and metrics via versioned REST APIs. | Authentication/authorization, account management, or paid tiers. |
| Maintain >70% cache hit ratio and <750 ms MVG P95 latency via Valkey caching strategies. | Replacing MVG as the source of truth or supporting other cities in MS1. |
| Provide a frontend that mirrors backend capabilities with resilient API integration and optimistic UI for slow paths. | Complex UX experiments, brand-new design systems, or offline PWAs. |
| Persist canonical transit and weather data so forecasting work can start without schema churn. | Real-time GTFS streaming ingestion (deferred), ML forecasting pipelines (Phase 2). |
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
- **Observability:** Metrics coverage for cache, MVG, API request latency, and exceptions. Logs are structured JSON with `request_id`, `station_id`, `cache_status`, `mvg_status`.
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
- `persistence.repositories` provide async CRUD for stations, departures, routes, weather, and ingestion runs.
- `app.jobs.cache_warmup` populates Valkey/Postgres before traffic.
- Frontend consumes backend APIs through `frontend/src/services/api.ts`, with TanStack Query caching plus background updates.

## 7. Backend Design Notes

- **Dependency Injection:** FastAPI dependencies wire config, cache, MVG client, and repositories per request to keep services stateless.
- **Caching Paths:** Cache keys include resource + params (e.g., `departure:{station}:{transport}:{limit}:{offset}`) with `:stale` suffix for fallback copy. Single-flight locks use TTL (`CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`) and wait/retry knobs to prevent thundering herds.
- **Circuit Breaker:** When Valkey unreachable, an in-process LRU fallback store (bounded) caches recent successful responses; breaker timeout controlled by `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`.
- **Persistence:** Async SQLAlchemy models map to tables such as `stations`, `transit_lines`, `departure_observations`, `route_snapshots`, `weather_observations`, `ingestion_runs`. Alembic migrations track schema evolution (Phase 2).
- **Warmup Flow:** Docker Compose runs `cache-warmup` service first to hydrate station catalog (and optional departures) using env knobs `CACHE_WARMUP_DEPARTURE_*`.
- **Error Handling:** Validation errors return 422, MVG not found returns 404 with descriptive payload, cache lock conflicts return 409 after >5 s wait, upstream outages return 503 with `Retry-After`.

## 8. Frontend Design Notes

- **Stack:** Vite + React 19 + TypeScript, Tailwind CSS, TanStack Query, React Router, Vitest + Testing Library.
- **API Service Layer:** `fetchJSON` wrapper handles base URL (`VITE_API_BASE_URL`), attaches request IDs, inspects `X-Cache-Status`, and surfaces metadata for UI badges.
- **State Management:** Query keys align with backend cache semantics (station, transport, pagination). Stale-while-refetch keeps UI responsive during MVG slowdowns.
- **Routing & Pages:** Router groups include `/` (dashboard/search), `/stations/:id`, `/routes`. Suspense boundaries show skeletons while queries resolve.
- **Testing:** Vitest + RTL for components/hooks; MSW mocks backend endpoints. Playwright E2E leverages docker-compose stack or mocked API.

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
- **Release Flow:** Build Docker images for backend/frontend; deploy with Compose, Kubernetes (manifests in `k8s/`), or platform-specific pipelines. Ensure `cache-warmup` job runs before switching traffic.

## 11. Observability & Operations

- **Metrics:**  
  - `bahnvision_cache_events_total{cache,event}` (hit, miss, stale_return, refresh_*).  
  - `bahnvision_cache_refresh_seconds{cache}` histogram.  
  - `bahnvision_mvg_requests_total{endpoint,result}` and `bahnvision_mvg_request_seconds{endpoint}` histograms.  
  - `bahnvision_api_request_duration_seconds{route}` and `bahnvision_api_exceptions_total{route,type}`.  
  - Planned: `bahnvision_weather_ingest_duration_seconds`.
- **Logging:** Structured JSON (logger config TBD) with `request_id`, `station_id`, `cache_status`, `mvg_status`, latency, and error classification.
- **Alerting:**  
  1. Cache hit ratio <70% over 5 min.  
  2. MVG request failure rate >5/min or `result=timeout`.  
  3. `/health` latency >1 s or error rate >1%.  
  4. Circuit breaker engaged >2 min sustained.
- **Tracing (future):** Evaluate OTLP exporter once upstream stable.

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
