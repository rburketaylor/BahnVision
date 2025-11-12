BahnVision Test Coverage Assessment Report (Corrected)

This document replaces earlier, estimate-based assessments with a precise, repo‑aware view and an actionable plan. It aligns with the repository’s testing strategy and CI setup.

—

Summary of Coverage

- Measurement source
  - Backend: CI generates coverage via `pytest --cov=app --cov-report=xml --cov-report=html` (see .github/workflows/ci.yml: test-backend). Retrieve exact numbers from Codecov artifact `backend-coverage` and `backend/htmlcov/` artifact.
  - Frontend: CI generates coverage via `npm test -- --coverage --run` (see .github/workflows/ci.yml: test-frontend). Retrieve exact numbers from Codecov artifact `frontend-coverage` and `frontend/coverage/` artifact.
  - Note: Prior reports listed rough percentages without data. Use CI artifacts for authoritative values.

- Backend (observed by suite contents)
  - Strong coverage: HTTP API for MVG endpoints (departures, routes, stations search), cache lifecycle paths (hit/miss/stale, lock timeout), parameter validation, transport filters, not-found caching.
    - Files: backend/tests/api/v1/test_mvg.py, backend/tests/test_mvg_endpoints.py
  - Cache service behavior covered: JSON set/get, stale TTLs, fallback store, circuit breaker, single‑flight lock, TTL edge cases, deletion.
    - File: backend/tests/services/test_cache_compatibility.py
  - Transport type parsing covered: deduplication, order preservation, synonyms, case/empty handling.
    - File: backend/tests/services/test_parse_transport_types.py
  - Metrics endpoint covered for basics (200, content-type, metric presence).
    - File: backend/tests/api/test_metrics.py
  - Light/missing: MVGClient data mapping and error handling, persistence repositories, background job StationsSyncJob, configuration validation, database engine wiring, metric recorder functions.

- Frontend (observed by suite contents)
  - Present: API client happy paths (health, stations search, departures) via MSW; StationSearch component interactions (success, 404, error+retry); useDepartures hook behavior; useDebouncedValue.
    - Files: frontend/src/tests/unit/api.test.ts, StationSearch.test.tsx, useDepartures.test.tsx, useDebouncedValue.test.ts
  - Missing: Hooks useHealth, useStationSearch, useRoutePlanner; components DeparturesBoard and Layout; pages MainPage/DeparturesPage/PlannerPage; Playwright E2E flows (config present, tests absent).

—

High‑Risk Uncovered Areas

Backend
- MVGClient mapping and fan‑out error handling
  - File: backend/app/services/mvg_client.py
  - Risk: Parsing upstream payloads; per‑transport fan‑out where any error raises MVGServiceError; correct suppression of 400 “bad request” to [] in `_fetch_departures`; route extraction across variant payload shapes.
- Persistence repositories
  - File: backend/app/persistence/repositories.py
  - Risk: Upsert batching for ~4.7k stations, asyncpg param limits, bulk return logic, idempotency of link tables.
- Background job (StationsSyncJob)
  - File: backend/app/jobs/stations_sync.py
  - Risk: Batch processing, partial failures per batch, final commit behavior, stats accounting.
- Configuration validation and database wiring
  - Files: backend/app/core/config.py, backend/app/core/database.py
  - Risk: CORS origin parsing (reject "*"), Valkey aliases, numeric bounds; engine/session lifecycle.
- Metric recorders
  - File: backend/app/core/metrics.py
  - Risk: Silent breakage of counters/histograms would degrade observability without obvious test failures.

Frontend
- DeparturesBoard component
  - File: frontend/src/components/DeparturesBoard.tsx
  - Risk: Sorting by realtime/planned time; hour grouping key correctness; canceled state styling; empty states.
- Hooks
  - Files: useHealth.ts, useStationSearch.ts, useRoutePlanner.ts
  - Risk: polling cadence and retry behavior; enabled gating; retry suppression on 4xx and 429; caching key stability.
- Pages and navigation
  - Files: frontend/src/pages/*.tsx, frontend/src/components/Layout.tsx
  - Risk: smoke coverage for primary flows and route wiring.
- E2E flows
  - Config present but no tests; CI currently continues on error.

—

Recommended Test Additions

Backend
1) MVGClient (unit; new file: backend/tests/services/test_mvg_client.py)
   - get_station
     - Success maps to Station DTO; MVG API error raises MVGServiceError; not found raises StationNotFoundError.
     - Example: simulate `MvgApi.station` returning None → StationNotFoundError.
   - _fetch_departures
     - 400/bad request returns [], other MvgApiError re‑raises; validate logging path optional.
     - Transport types argument passed through.
   - get_departures
     - No filters: one call path; returns mapped departures.
     - With filters: per‑type fan‑out; success merges and sorts; any type failing raises MVGServiceError; success records MVG transport metrics.
     - Example inputs: transport_types=[UBAHN, BUS], one mocked as timeout → MVGServiceError.
   - _extract_routes/_map_route_stop/_map_route_leg/_map_route
     - Validate extraction across payload variants: {routes}, {connections}, list payloads; missing nested keys handled; numeric/time conversions via DataMapper.
     - Example: payload with nested `line: {transportType, name}` and alternate "product"/"transportType" placement.
   - search_stations
     - Happy path with CachedStationSearchIndex present/absent; limit enforcement; empty results.

2) Config and Database (unit; new files under backend/tests/core/)
   - Settings parsing
     - CORS: comma‑separated inputs; rejection of "*" with helpful message.
     - Valkey aliasing: ensure VALKEY_* inputs are honored (and document current Redis alias support limits if any).
     - Bounds: single‑flight/circuit breaker values ≥ 0.
   - Database engine/session
     - Builds engine from env; AsyncSessionFactory yields sessions; no premature disposal in simple usage.

3) Repositories (integration; new files under backend/tests/persistence/)
   - StationRepository.upsert_stations
     - Chunking under asyncpg param limit; commit and retrieval of all stations; order/limit logic in `search_stations`.
   - TransitDataRepository
     - record_departure_observations/record_weather_observations return counts; link_departure_weather idempotent on conflicts.
   - Setup: reuse test-migrations job pattern (see .github/workflows/test-migrations.yml) with Postgres service, run alembic upgrade in test session.

4) StationsSyncJob (integration/unit; backend/tests/jobs/test_stations_sync.py)
   - Happy path: fake MVG client with N stations, batch_size small → stats: total=N, upserted=N, errors=0.
   - Batch error: inject exception for one batch → increments errors; continues subsequent batches; final commit.
   - get_sync_status: returns count and sample; handles repository failure returning error field.

5) Metrics recorders (unit; backend/tests/core/test_metrics.py)
   - Use prometheus_client registry to snapshot counter values, call observe/record functions, assert deltas; optionally assert /metrics contains expected series with labels using a minimal ASGI TestClient call around routes that increment metrics.

Frontend
1) API client (unit; frontend/src/tests/unit/api-client.test.ts)
   - ApiError mapping: 4xx/5xx with body; AbortError → 408; network failure → statusCode 0.
   - buildQueryString: arrays generate repeated keys; omit undefined/null; numeric/bool stringification.
   - planRoute: throws when both times provided.
   - getMetrics: returns text; non-200 throws.

2) Hooks (unit)
   - useHealth (frontend/src/tests/unit/useHealth.test.ts)
     - Polling every 60s (assert options); retry enabled; staleTime=0.
   - useStationSearch (frontend/src/tests/unit/useStationSearch.test.ts)
     - enabled gating on empty query; retry suppression for 4xx and 429; retryDelay backoff; cache timing (staleTime/gcTime) set.
   - useRoutePlanner (frontend/src/tests/unit/useRoutePlanner.test.ts)
     - enabled flag; staleTime set; queryKey stability.

3) Components and Pages (component/integration)
   - DeparturesBoard (frontend/src/tests/unit/DeparturesBoard.test.tsx)
     - Sorting priority: realtime_time over planned_time; grouping key correctness; canceled row styling; empty-state message.
     - Example inputs: mixed realtime/planned times; canceled=true row.
   - Layout + routing smoke tests (frontend/src/tests/unit/Layout.test.tsx)
     - Routes render shells without crashing; basic navigation links produce expected content.
   - Pages (frontend/src/tests/unit/pages/*.test.tsx)
     - MainPage/DeparturesPage/PlannerPage render and query hooks invoked; mock API responses.

4) E2E (Playwright; frontend/tests/e2e/*.spec.ts)
   - Flow: search → select Marienplatz → departures render → transport filter interaction → confirm contents.
   - Flow: route planning: origin/destination selection → route card appears.
   - Update CI to fail on E2E failures (remove continue-on-error once tests are stable).

—

Redundant or Low‑Value Tests

- backend/tests/api/v1/test_offset_validation.py
  - Accepts wide status ranges [200, 404, 502, 503] for “within limit” cases and prints to stdout. This is brittle and low-signal. Recommendation: fold precise offset conversion/422 upper-bound assertions into existing departures tests and remove this standalone script‑style test.

- Potential duplication across endpoint suites
  - backend/tests/test_mvg_endpoints.py and backend/tests/api/v1/test_mvg.py both exercise cache hit/miss/stale and lock timeout paths. Consider consolidating into the api/v1 suite to reduce drift and maintenance.

—

General Testing Recommendations

- Coverage thresholds
  - Backend: enforce `--cov-fail-under` (e.g., 80%) in CI. Frontend: enforce Vitest coverage thresholds (e.g., 75%) via config.

- CI tightening
  - Remove Playwright `continue-on-error` once initial e2e flows land. Parallelize backend tests (pytest-xdist). Keep Codecov uploads.

- Fixtures and doubles
  - Consolidate fakes in backend/tests/common/ to avoid duplicated FakeMVGClient/Cache across conftests; prefer dependency overrides via FastAPI for endpoints and direct fakes for service-unit tests.

- Integration DB tests
  - Reuse Postgres service + alembic upgrade like test-migrations workflow; add a tox/Make target for local dev parity.

- Observability assertions
  - Add targeted assertions for incremented counters/histograms in critical paths (e.g., per-transport departures fan-out). Validate presence and label sets via /metrics response in integration tests.

- Test data management
  - Centralize JSON fixtures mirroring backend models (backend/app/models/mvg.py) under backend/tests/fixtures and frontend/src/tests/mocks/fixtures to keep UI/HTTP in sync.

—

Appendix: Suggested File Skeletons

- Backend
  - backend/tests/services/test_mvg_client.py
  - backend/tests/core/test_config.py
  - backend/tests/core/test_database.py
  - backend/tests/core/test_metrics.py
  - backend/tests/persistence/test_station_repository.py
  - backend/tests/persistence/test_transit_data_repository.py
  - backend/tests/jobs/test_stations_sync.py

- Frontend
  - frontend/src/tests/unit/api-client.test.ts
  - frontend/src/tests/unit/useHealth.test.ts
  - frontend/src/tests/unit/useStationSearch.test.ts
  - frontend/src/tests/unit/useRoutePlanner.test.ts
  - frontend/src/tests/unit/DeparturesBoard.test.tsx
  - frontend/src/tests/unit/Layout.test.tsx
  - frontend/src/tests/unit/pages/MainPage.test.tsx
  - frontend/src/tests/unit/pages/DeparturesPage.test.tsx
  - frontend/src/tests/unit/pages/PlannerPage.test.tsx
  - frontend/tests/e2e/flows.spec.ts


Addendum: Additional Targets and Plan

- Additional backend gaps to call out explicitly
  - Shared caching patterns in `backend/app/api/v1/shared/caching.py` (handle_cache_lookup, handle_cache_errors, execute_cache_refresh, CacheManager) power most endpoint behavior and metrics but lack direct tests.
  - App lifecycle and telemetry in `backend/app/main.py` and `backend/app/core/telemetry.py`: engine disposal on shutdown, SQLAlchemy logging level configuration, and OTEL enable/disable instrumentation paths are untested.

- Additional frontend gaps to call out explicitly
  - Utilities and configuration used across the UI: `frontend/src/utils/time.ts`, `frontend/src/utils/transport.ts`, `frontend/src/lib/config.ts`, and `frontend/src/lib/query-client.ts` currently have no direct tests.

- New recommended tests (to append to the list above)
  - Backend: `backend/tests/api/shared/test_caching_module.py`
    - handle_cache_lookup: hit/miss/stale-refresh paths; 404 for not_found marker; header setting.
    - handle_cache_errors: TimeoutError → 503 and optional stale fallback; MVGServiceError → 502; NotFound errors → 404; cache event recording.
    - execute_cache_refresh: single-flight respect; not-found marker TTLs; events for refresh_success/error/not_found/skip_hit; observe latency histogram call.
    - CacheManager.get_cached_data: end-to-end miss→refresh→hit; miss+error→stale fallback; header propagation; event increments.
  - Backend: `backend/tests/app/test_main_lifecycle.py`
    - `_configure_sqlalchemy_logging` sets expected levels; request-id middleware echoes/generates header; lifespan disposes engine; telemetry functions invoked only when `OTEL_ENABLED=true`.
  - Frontend: utility/config units
    - time.ts: formatting edge cases (midnight, tz offsets, empty inputs).
    - transport.ts: icon/label mapping covers all products; unknown handling.
    - lib/config.ts: env overrides and debug flag behavior.
    - lib/query-client.ts: exported defaults for staleTime/retry/gcTime.

- Enhance existing minimal tests
  - backend/tests/api/test_metrics.py: after hitting a known API route, assert that labeled time series (e.g., `bahnvision_mvg_transport_requests_total`) appear and counters increment.

- Measurement plan and gates (practical steps)
  - Local: `cd backend && pytest --cov=app --cov-report=term --cov-report=html`; `cd frontend && npm test -- --coverage --run`.
  - CI artifacts: Backend `backend-coverage` (coverage.xml) and `backend/htmlcov/` artifacts; Frontend `frontend-coverage` (lcov.info) artifact; both uploaded to Codecov.
  - Gates: add `--cov-fail-under=80` to backend; configure Vitest coverage thresholds to ≥75% for frontend; consider raising module‑level thresholds for new tests (e.g., MVGClient and caching targets to ≥90%).

- Execution milestones (who/when guidance)
  - Milestone 1 (P0; 1–2 days): MVGClient unit suite; caching module tests; metrics recorder tests; DeparturesBoard component tests; API client error/timeout tests.
  - Milestone 2 (P0/P1; 2–3 days): Repository integration tests with Postgres; StationsSyncJob tests; hooks (useHealth/useStationSearch/useRoutePlanner); Layout/Pages smoke tests.
  - Milestone 3 (P1; 1–2 days): App lifecycle/telemetry tests; initial Playwright flow; remove `continue-on-error` for E2E in CI; consolidate duplicate endpoint tests.
