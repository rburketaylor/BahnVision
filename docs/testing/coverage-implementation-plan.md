# BahnVision Test Coverage Implementation Plan

Purpose
- Convert the assessment into a clear, step-by-step backlog an agent can execute safely.
- Each task lists files to add/change, what to implement, acceptance criteria, and validation commands.

How To Use
- Work milestone-by-milestone. For each task, implement exactly the listed files and assertions.
- After each task (or milestone), run the validation commands and tick the checkbox.
- Keep PRs small: 1–3 tasks per PR unless tasks are trivial.

Pre‑requisites
- Backend
  - Python 3.11+, FastAPI stack installed: `pip install -r backend/requirements.txt`
  - Local Postgres available for integration tasks (Milestone 2):
    - Use `docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d postgres`
    - `DATABASE_URL=postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`
  - Valkey only needed for end-to-end; unit tests use fakes.
- Frontend
  - Node 24+, `cd frontend && npm ci`

Conventions
- New back-end test files under `backend/tests/**` mirror source tree where practical.
- New front-end unit tests under `frontend/src/tests/unit/**`; E2E under `frontend/tests/e2e/**`.
- Prefer fakes over real network; do not add networked tests.

Validation Commands
- Backend unit/integration: `cd backend && pytest --maxfail=1 -q`
- Backend with coverage: `cd backend && pytest --cov=app --cov-report=term`
- Frontend unit with coverage: `cd frontend && npm test -- --coverage --run`

Milestone 1 (P0): Core correctness and fast wins

- [ ] M1-T1 Backend: MVGClient unit tests
  - Files: `backend/tests/services/test_mvg_client.py`
  - Implement:
    - get_station: success → Station DTO; MvgApiError → MVGServiceError; None → StationNotFoundError.
    - _fetch_departures: “400/bad request” returns []; other MvgApiError re-raises.
    - get_departures: no filters path; with filters fan‑out merges; any transport failure → MVGServiceError; ordering + limit applied.
    - _extract_routes/_map_route_stop/_map_route_leg/_map_route: cover alt payload shapes and missing fields.
  - Notes: monkeypatch `mvg.MvgApi.station/stations/route` and `MvgApi(...).departures` to avoid network.
  - Acceptance: All tests green; covers success + error branches; no flakiness.
  - Validate: `cd backend && pytest tests/services/test_mvg_client.py -q`

- [ ] M1-T2 Backend: Shared caching module tests
  - Files: `backend/tests/api/shared/test_caching_module.py`
  - Implement:
    - handle_cache_lookup: fresh hit (with/without not_found marker) and stale‑refresh path sets headers + schedules bg task.
    - handle_cache_errors: TimeoutError → 503 (optionally stale fallback); MVGServiceError → 502; *NotFound → 404; events recorded.
    - execute_cache_refresh: respects single‑flight; on not‑found writes compact marker with `valkey_cache_ttl_not_found_seconds`; records refresh_* events; calls observe_cache_refresh.
    - CacheManager.get_cached_data: miss→refresh→hit; miss+error→stale fallback; headers/metrics propagated.
  - Notes: Use simple fakes for CacheService and protocol; do not import Valkey.
  - Acceptance: Assertions on returned models, headers, and event invocations.
  - Validate: `cd backend && pytest tests/api/shared/test_caching_module.py -q`

- [ ] M1-T3 Backend: Metrics recorder unit tests
  - Files: `backend/tests/core/test_metrics.py`
  - Implement: snapshot counters; call recorders (record_cache_event, observe_cache_refresh, observe_mvg_request, record_mvg_transport_request); assert deltas.
  - Acceptance: Histogram/counter increments as expected.
  - Validate: `cd backend && pytest tests/core/test_metrics.py -q`

- [ ] M1-T4 Frontend: API client error/timeout tests
  - Files: `frontend/src/tests/unit/api-client.test.ts`
  - Implement: ApiError mapping for 4xx/5xx; AbortError→408; network failure statusCode 0; buildQueryString arrays and null/undefined handling; planRoute double time params throws.
  - Acceptance: All new tests green; no mutation of prod API code required.
  - Validate: `cd frontend && npm test -- src/tests/unit/api-client.test.ts --run`

- [ ] M1-T5 Frontend: DeparturesBoard component tests
  - Files: `frontend/src/tests/unit/DeparturesBoard.test.tsx`
  - Implement: sorting by realtime/planned; hour grouping key; canceled styling; empty state.
  - Acceptance: Rendered table order and labels match assertions.
  - Validate: `cd frontend && npm test -- src/tests/unit/DeparturesBoard.test.tsx --run`

Milestone 2 (P0/P1): Persistence + jobs + hooks + pages

- [ ] M2-T1 Backend: StationRepository + TransitDataRepository integration tests
  - Files: `backend/tests/persistence/test_station_repository.py`, `backend/tests/persistence/test_transit_data_repository.py`
  - Implement:
    - upsert_stations chunking; search ordering; count_stations; delete_station returns booleans.
    - record_departure_observations/record_weather_observations return counts; link_departure_weather idempotent.
  - Notes: Start Postgres; run alembic upgrade in test session if needed; use DATABASE_URL env.
  - Acceptance: Tests green against local Postgres; no data leakage between tests.
  - Validate: `cd backend && pytest tests/persistence -q`

- [ ] M2-T2 Backend: StationsSyncJob tests
  - Files: `backend/tests/jobs/test_stations_sync.py`
  - Implement: run_sync happy path (batching); batch error increments errors but continues; get_sync_status returns counts/sample, handles repository failure.
  - Acceptance: Deterministic stats; logs optional.
  - Validate: `cd backend && pytest tests/jobs/test_stations_sync.py -q`

- [ ] M2-T3 Frontend: Hooks tests
  - Files: `frontend/src/tests/unit/useHealth.test.ts`, `frontend/src/tests/unit/useStationSearch.test.ts`, `frontend/src/tests/unit/useRoutePlanner.test.ts`
  - Implement:
    - useHealth: polling 60s; retry true; staleTime=0.
    - useStationSearch: enabled gating on empty query; retry suppression for 4xx/429; retryDelay backoff; staleTime/gcTime set.
    - useRoutePlanner: enabled flag; staleTime set; queryKey stability.
  - Validate: `cd frontend && npm test -- src/tests/unit/use*.test.ts --run`

- [ ] M2-T4 Frontend: Layout + pages smoke tests
  - Files: `frontend/src/tests/unit/Layout.test.tsx`, `frontend/src/tests/unit/pages/MainPage.test.tsx`, `.../DeparturesPage.test.tsx`, `.../PlannerPage.test.tsx`
  - Implement: router renders shells; basic interactions render primary content; hooks invoked with mocked API.
  - Validate: `cd frontend && npm test -- src/tests/unit/**/pages/*.test.tsx --run`

Milestone 3 (P1): Config/DB lifecycle + E2E + cleanup

- [ ] M3-T1 Backend: Config tests
  - Files: `backend/tests/core/test_config.py`
  - Implement: CORS parsing rejects "*"; comma-separated origins; TTL bounds; VALKEY_* envs honored.
  - Validate: `cd backend && pytest tests/core/test_config.py -q`

- [ ] M3-T2 Backend: Database lifecycle tests
  - Files: `backend/tests/core/test_database.py`
  - Implement: engine created from env; AsyncSessionFactory yields sessions; simple query round-trip (if models available) or connection open/close.
  - Validate: `cd backend && pytest tests/core/test_database.py -q`

- [ ] M3-T3 Backend: App lifecycle + telemetry tests
  - Files: `backend/tests/app/test_main_lifecycle.py`
  - Implement: `_configure_sqlalchemy_logging` sets levels/propagation; request-id middleware emits header; lifespan disposes engine; telemetry functions guard on OTEL_ENABLED.
  - Validate: `cd backend && pytest tests/app/test_main_lifecycle.py -q`

- [ ] M3-T4 Frontend: Playwright E2E flow
  - Files: `frontend/tests/e2e/flows.spec.ts`
  - Implement: search → select → departures render → route plan basic flow; use dev/demo backend or MSW within Playwright.
  - CI tweak (follow-up PR): remove continue-on-error in `.github/workflows/ci.yml` E2E job once stable.
  - Validate: `cd frontend && npm run test:e2e -- --project=chromium`

- [ ] M3-T5 Backend: Clean up duplicate/low-value tests
  - Remove or merge `backend/tests/api/v1/test_offset_validation.py` into existing param validation tests.
  - Consolidate overlapping endpoint tests from `backend/tests/test_mvg_endpoints.py` into `backend/tests/api/v1/test_mvg.py`.
  - Validate: full backend suite green.

Coverage & Gates (optional but recommended)
- Backend: add `--cov-fail-under=80` to CI backend job.
- Frontend: set Vitest thresholds to ≥75% in `vitest.config.ts`.
- For newly added suites (MVGClient, caching module), target ≥90% local coverage before PR.

Out of Scope / Deferred
- Mutation testing (Stryker/Mutmut), performance testing (k6/Locust), visual regression – consider after baseline tests are stable.

Risks & Mitigations
- DB integration flakiness: pin container version, add retries on connection, scope tables via schema if needed.
- E2E instability: keep to 1–2 happy-path flows initially, run single browser project in CI.

