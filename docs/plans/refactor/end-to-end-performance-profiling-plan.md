# End-to-End Performance Profiling Plan (Synthetic Runs + AI-Readable Artifacts)

**Date:** 2026-02-16  
**Goal:** Identify what most impacts user-perceived latency (frontend + backend + dependencies) and produce stable, machine-readable artifacts that an AI agent can ingest to propose optimizations with evidence.

---

## Verification Status (2026-02-17)

- [x] Baseline prerequisites are present: `/metrics` export (`backend/app/api/metrics.py`), request ID middleware (`backend/app/main.py`), and Playwright setup (`frontend/playwright.config.ts`).
- [x] `Server-Timing` support exists in heatmap endpoints (`backend/app/api/v1/endpoints/heatmap.py`), but not as global API middleware.
- [ ] Phase 0 scaffolding is not implemented (`perf/README.md` and `perf/schema/` are missing).
- [ ] Phase 1 request-level API metrics/middleware is not implemented (`backend/app/core/metrics.py` has no `bahnvision_api_request_*` metrics; `backend/app/main.py` has no request-timing middleware).
- [ ] Phase 2 frontend correlation/event buffer is not implemented (`frontend/src/services/httpClient.ts` does not generate outbound `X-Request-Id` values or emit `window.__bahnvisionPerf` NDJSON-ready events).
- [ ] Phase 3 perf Playwright pipeline is not implemented (existing E2E specs are mock-driven and no perf artifact writer exists under `perf/runs/`).
- [ ] Phase 4 Prometheus window exporter is not implemented (`scripts/perf/` is missing).
- [ ] Phase 5 bottleneck summarizer is not implemented (no `top_bottlenecks.json` generator exists).
- [ ] Phase 6 optional tracing export pipeline is not implemented (no run-window trace export artifacts/scripts found).

---

## Problem Statement

We want a repeatable way to answer, with data:

- Where does time go for a user completing core journeys (initial load, station search, departures, heatmap)?
- Is the bottleneck frontend render/JS work, backend processing, cache behavior, DB, or external upstream calls?
- What changes improve or regress those journeys across commits?

Key requirement: outputs must be easily accessible for AI processing. That means text artifacts (`.json`, `.ndjson`, `.csv`) with a stable schema and clear correlation keys.

---

## Current State (Verified in Repo)

Backend:

- Prometheus metrics exist and are exposed at `GET /metrics` via `backend/app/api/metrics.py`.
- Metric definitions live in `backend/app/core/metrics.py` (cache events, cache refresh latency, outbound Transit request latency).
- Optional OpenTelemetry wiring exists in `backend/app/core/telemetry.py` and is called from `backend/app/main.py` behind `OTEL_ENABLED` (`backend/app/core/config.py`).
- Backend injects and echoes `X-Request-Id` (middleware in `backend/app/main.py` reads request header or generates one).
- Some endpoints already append `Server-Timing` entries (currently only verified in heatmap code: `backend/app/api/v1/endpoints/heatmap.py`).

Frontend:

- Core API client exists at `frontend/src/services/httpClient.ts` and reads `X-Request-Id` and `X-Cache-Status` from responses.
- Frontend observability is explicitly not wired today (planned doc: `frontend/docs/operations/observability.md`).
- Playwright is present and configured (`frontend/playwright.config.ts`).
- A helper exists to launch Playwright Chromium with CDP enabled (`scripts/launch-playwright-chrome-cdp.sh`) for deeper browser profiling.

Infra:

- An observability compose file exists with Prometheus/Grafana/cAdvisor/postgres-exporter/redis-exporter: `docker-compose.observability.yml`.
- Prometheus scrape config includes `backend:8000/metrics`: `observability/prometheus/prometheus.yml`.

---

## Strategy Overview

We implement a synthetic profiling pipeline that:

1. Runs real user journeys via Playwright against a running stack (docker compose preferred).
2. Captures:
   - User-perceived timings (navigation + interaction-to-render).
   - Per-request network timings and response correlation headers (`X-Request-Id`, `X-Cache-Status`, `Server-Timing`).
   - Backend request timing metrics (Prometheus) for the same run window.
   - Optional traces (OTel) in later phase.
3. Writes artifacts into a per-run directory with a stable schema.
4. Produces an AI-ready summary (`top_bottlenecks.json`) that links each bottleneck to evidence.

This yields an optimization workflow:

- Compare `perf/runs/*/summary/top_bottlenecks.json` across commits.
- Drill into individual `journeys.ndjson` events and backend metrics for root cause.

---

## Artifact Contract (AI-Readable)

### Directory Layout

All outputs go under:

- `perf/runs/<run_id>/`

Where `run_id` is deterministic and sortable, e.g. `2026-02-16T10-30-00Z_<git_sha>_<scenario>`.

Required files:

- `perf/runs/<run_id>/manifest.json`
- `perf/runs/<run_id>/journeys/<journey_id>.ndjson`
- `perf/runs/<run_id>/summary/top_bottlenecks.json`
- `perf/runs/<run_id>/summary/run_summary.md`

Optional (depending on phases enabled):

- `perf/runs/<run_id>/playwright/trace.zip`
- `perf/runs/<run_id>/prometheus/query_range.json`
- `perf/runs/<run_id>/traces/*.json`
- `perf/runs/<run_id>/browser/cdp-trace.json`
- `perf/runs/<run_id>/browser/cpu-profile.json`

### Correlation Keys (Join Strategy)

The system should make it easy to join frontend timing -> backend work -> caches:

- `run_id`: ties all artifacts for one run together.
- `journey_id`: ties per-journey measures and request events together.
- `X-Request-Id`:
  - Frontend generates and sends per-request (Phase 2).
  - Backend preserves and echoes it (`backend/app/main.py`).
  - All request events should store it as `response.request_id`.
- `Server-Timing`:
  - Backend emits overall `app` timing for each response (Phase 1).
  - Frontend/runner parses it into `response.server_timing`.

### `manifest.json` Schema (v1)

```json
{
  "schema_version": 1,
  "run_id": "2026-02-16T10-30-00Z_abcd123_warm",
  "started_at": "2026-02-16T10:30:00.000Z",
  "ended_at": "2026-02-16T10:33:10.000Z",
  "git": {
    "sha": "abcd123",
    "branch": "main",
    "dirty": false
  },
  "environment": {
    "mode": "docker",
    "frontend_base_url": "http://localhost:3000",
    "api_base_url": "http://localhost:8000"
  },
  "scenario": {
    "name": "warm",
    "notes": "Cache warmed; steady-state"
  },
  "artifacts": {
    "journeys_dir": "journeys",
    "summary_dir": "summary",
    "prometheus_query_range": "prometheus/query_range.json",
    "playwright_trace": "playwright/trace.zip"
  }
}
```

### Journey Event Schema (`*.ndjson`, v1)

One JSON object per line (NDJSON). Each event includes a timestamp and correlation fields.

Common fields:

- `schema_version`: `1`
- `run_id`
- `journey_id`
- `ts_ms`: epoch milliseconds (UTC)
- `type`: one of `journey_start`, `journey_end`, `mark`, `measure`, `api_call`, `web_vital`

`api_call` event (minimum fields):

```json
{
  "schema_version": 1,
  "run_id": "…",
  "journey_id": "station_search_to_departures",
  "ts_ms": 0,
  "type": "api_call",
  "request": {
    "method": "GET",
    "path_template": "/api/v1/transit/departures",
    "url": "http://localhost:8000/api/v1/transit/departures?stop_id=…",
    "timeout_ms": 10000
  },
  "response": {
    "status": 200,
    "request_id": "…",
    "cache_status": "hit",
    "server_timing": { "app": 123.45, "cache": 2.1 }
  },
  "timing": {
    "start_ms": 0,
    "end_ms": 0,
    "duration_ms": 0
  }
}
```

Notes:

- `path_template` must avoid high-cardinality raw paths. Use route templates where possible (`/api/v1/transit/departures`, not `/api/v1/transit/stops/<id>`).
- `server_timing` is parsed from the `Server-Timing` response header when present.

### Summary Schema (`top_bottlenecks.json`, v1)

```json
{
  "schema_version": 1,
  "run_id": "…",
  "generated_at": "…",
  "bottlenecks": [
    {
      "rank": 1,
      "category": "backend",
      "name": "GET /api/v1/transit/departures p95",
      "estimate_ms": 820,
      "evidence": {
        "journey_id": "station_search_to_departures",
        "event_ref": "journeys/station_search_to_departures.ndjson:line=123",
        "request_ids_sample": ["…", "…"],
        "prometheus_metric": "bahnvision_api_request_duration_seconds"
      },
      "hypotheses": [
        "Cache misses triggering upstream fetch",
        "Slow DB query for stop times"
      ]
    }
  ]
}
```

---

## Journeys to Measure (Synthetic)

Use journeys that map to real UX flows in `frontend/docs/product/ux-flows.md`.

Minimum set (Phase 1):

1. `landing_heatmap_load`
2. `station_search_to_departures`
3. `station_page_tab_switch` (overview -> schedule -> trends)
4. `monitoring_page_load` (fetch `/metrics`)

Each journey defines:

- Start condition (URL + initial UI visible).
- Steps (user actions).
- End condition (UI stable + key data visible).
- “Ready” markers (specific DOM selectors) for consistent timing boundaries.

---

## Implementation Plan (Phased, Agent-Executable)

### Phase 0: Repo Scaffolding + Schemas

Deliverables:

- Create `perf/README.md` describing how to run profiling and where artifacts live.
- Create `perf/schema/` containing JSON schema docs for `manifest.json`, journey events, and summaries (human-readable markdown is acceptable initially).

Acceptance criteria:

- A new run directory format is documented and consistent with this plan.

### Phase 1: Backend Request-Level Metrics + Timing Headers

Goal: quantify backend latency by route/method/status without relying on external APM.

Tasks:

- Add API request metrics to `backend/app/core/metrics.py`:
  - Histogram: `bahnvision_api_request_duration_seconds` labeled by `{route, method, status_code}`.
  - Counter: `bahnvision_api_requests_total` labeled by `{route, method, status_code}`.
  - Optional counter for exceptions by `{route, method, exception_type}`.
- Add an ASGI middleware that:
  - Uses FastAPI route templates (not raw paths) to avoid high cardinality.
    - Implementation detail: record after routing has run (e.g., read `request.scope.get("route")` after `call_next` returns).
    - Fallback label when route is missing (404/unmatched): use a constant like `"<unmatched>"` (do not use raw `scope["path"]`).
  - Records duration in seconds in the histogram.
  - Optionally appends `Server-Timing: app;dur=<ms>` for all API responses.
- Ensure the middleware is installed in `backend/app/main.py` (similar placement to `_install_request_id_middleware`).

Evidence/correlation:

- Frontend can map a slow API call to a backend route and compare `duration_ms` to `Server-Timing app` when present.

Acceptance criteria:

- Hitting any endpoint increases `bahnvision_api_requests_total` and records `bahnvision_api_request_duration_seconds`.
- Prometheus shows stable label cardinality under normal traffic (route templates only).

### Phase 2: Frontend Correlation + Lightweight Perf Event Buffer

Goal: reliably correlate user actions with API calls and backend timings without adding a third-party RUM dependency.

Tasks:

- Generate and send `X-Request-Id` on each fetch from `frontend/src/services/httpClient.ts`.
  - Backend already preserves incoming request IDs (`backend/app/main.py`), enabling consistent correlation end-to-end.
- Extend `frontend/src/services/httpClient.ts` to record a local perf event per request:
  - Start/end timestamps (`performance.now()`), duration, method, endpoint, response status.
  - Include response `X-Request-Id`, `X-Cache-Status`, and parsed `Server-Timing` if present.
  - Default to low-cardinality fields:
    - Store `path_template` + method; avoid persisting full URLs with raw query strings unless the run is explicitly synthetic.
- Add a minimal event sink:
  - In production: no-op by default.
  - In profiling mode (env flag): store events in a ring buffer on `window.__bahnvisionPerf` and expose a method to download as NDJSON.

Acceptance criteria:

- In profiling mode, a user journey produces a stable, parseable NDJSON record of API calls and their correlation fields.

### Phase 3: Playwright Perf Runner (No Mocks)

Goal: run journeys against the real stack and emit artifacts automatically.

Tasks:

- Add a new Playwright “perf” test suite separate from existing mocked E2E tests:
  - Avoid `setupStationMocks` and related fixtures.
  - Use `PLAYWRIGHT_BASE_URL` to target docker compose (`http://localhost:3000`) or dev server (`http://localhost:5173`).
- Reduce noise for perf runs:
  - Run Chromium only by default.
  - Force `workers=1` when `PERF_E2E=1` (update `frontend/playwright.config.ts` accordingly) so timing variance from parallelism is minimized.
- Implement a custom reporter or post-run hook that:
  - Creates `perf/runs/<run_id>/`.
  - Writes `manifest.json`.
  - Writes `journeys/<journey_id>.ndjson` by:
    - Pulling browser-side buffered perf events (Phase 2), and/or
    - Collecting network request timings via Playwright request/response events.
  - Stores Playwright trace to `playwright/trace.zip` for debugging (optional per run).

Acceptance criteria:

- One command produces a complete run directory with required files.
- Running twice yields comparable structure (no missing keys), even if timings differ.

### Phase 4: Prometheus Export for Run Window

Goal: capture backend metrics for the same timeframe as the synthetic journeys.

Tasks:

- Add a script (Python or Node) under `scripts/perf/` that:
  - Reads `started_at`/`ended_at` from `manifest.json`.
  - Queries Prometheus HTTP API (`/api/v1/query_range`) for a small set of PromQL expressions:
    - p50/p95 for API request duration by route.
    - request rate by route.
    - cache hit/miss rate (existing `bahnvision_cache_events_total`).
    - outbound transit latency (existing `bahnvision_transit_request_seconds`).
  - Writes raw Prometheus responses to `perf/runs/<run_id>/prometheus/query_range.json`.

Initial PromQL set (assumes Phase 1 metrics exist; exporter should tolerate missing series):

- API request p95 by route:
  - `histogram_quantile(0.95, sum(rate(bahnvision_api_request_duration_seconds_bucket[5m])) by (le, route, method))`
- API request rate:
  - `sum(rate(bahnvision_api_requests_total[5m])) by (route, method, status_code)`
- Cache hit ratio:
  - `sum(rate(bahnvision_cache_events_total{event="hit"}[5m])) / sum(rate(bahnvision_cache_events_total[5m]))`
- Outbound transit p95 latency:
  - `histogram_quantile(0.95, sum(rate(bahnvision_transit_request_seconds_bucket[5m])) by (le, endpoint))`

Acceptance criteria:

- Exported Prometheus JSON includes the run window and can be ingested offline by another agent.

### Phase 5: Summarizer to `top_bottlenecks.json`

Goal: produce the “AI starting point” artifact.

Tasks:

- Add a summarizer under `scripts/perf/` that reads:
  - `journeys/*.ndjson`
  - `prometheus/query_range.json` (if present)
- Output:
  - `summary/top_bottlenecks.json` (ranked list with evidence pointers)
  - `summary/run_summary.md` (human-friendly narrative + links to artifacts)

Ranking heuristics (simple and explicit):

- Compute p95 and p99 for per-request durations grouped by `path_template`.
- Flag journeys where total `measure` time exceeds budget (e.g., >1500ms for `station_search_to_departures` warm).
- If `Server-Timing app` exists, estimate frontend vs backend split:
  - `frontend_overhead_ms = api_duration_ms - server_timing_app_ms` (bounded at >= 0).

Acceptance criteria:

- `top_bottlenecks.json` points to specific journey events and, when available, supporting backend metrics.

### Phase 6 (Optional): Tracing Stack + Span Export

Only after Phases 1-5 are useful and stable.

Tasks:

- Add a tracing backend (Jaeger all-in-one or an OTEL collector + Tempo) to compose.
- Enable `OTEL_ENABLED=true` and set a reachable OTLP endpoint.
- Add a “trace export” step that collects traces for the run window and stores them as JSON.

Acceptance criteria:

- A slow journey’s `X-Request-Id` can be linked to a trace and its slowest spans.

---

## Running the Pipeline (Target UX)

### Scenarios (Warm vs Cold)

We need at least two scenarios to avoid optimizing only for steady-state:

- `warm`: normal steady-state with caches populated.
- `cold`: intentionally flush cache and re-run a journey to capture worst-case.

Suggested cold-cache reset (docker):

1. Flush Valkey: `docker compose exec valkey valkey-cli FLUSHALL`
2. Restart backend (clears in-process fallback store): `docker compose restart backend`
3. Optional: wait for `/api/v1/ready` to return 200 before starting a run.

Notes:

- Heatmap endpoints may be warmed at backend startup (`backend/app/main.py` triggers cache warmup). A “cold” heatmap run may require disabling warmup or defining “cold” as “cold for a given key variant”.

Primary workflow (docker, production-like frontend):

1. `docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build`
2. `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:3000 npm run test:e2e -- --project=chromium --grep \"@perf\"`
3. Artifacts appear under `perf/runs/<run_id>/`

Secondary workflow (dev server):

1. `uvicorn app.main:app --reload --app-dir backend`
2. `cd frontend && npm run dev`
3. `cd frontend && PLAYWRIGHT_BASE_URL=http://localhost:5173 npm run test:e2e -- --project=chromium --grep \"@perf\"`

---

## Guardrails and Constraints

- Avoid label cardinality explosions in Prometheus metrics. Route templates only.
- Keep profiling overhead low and optional (feature-flagged in production builds).
- Do not capture PII:
  - For station search, do not log raw user queries outside synthetic runs.
  - Prefer hashing or bucketing (`query_length`) if ever exported from real users.
- Prefer existing dependencies and patterns:
  - Backend uses `prometheus_client` already (`backend/app/core/metrics.py`).
  - Frontend can use platform Performance APIs instead of adding a RUM SDK.

---

## Definition of Done (Project-Level)

This plan is “done” when:

- A single command produces a `perf/runs/<run_id>/` directory with `manifest.json`, journey NDJSON, and `top_bottlenecks.json`.
- The summary correctly identifies at least 3 real bottlenecks under:
  - warm cache scenario
  - cold cache scenario (intentional cache flush / first run)
- An AI agent can propose concrete optimizations and link each proposal to evidence from the run artifacts.
