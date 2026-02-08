# Verified Issue Remediation Plan

**Date**: 2026-02-08  
**Status**: Open (plan only; no fixes applied)  
**Baseline commit**: `0aa7887`

## Scope

This document converts the external bug report into an implementation plan based on verified code inspection.

This plan distinguishes:

- **Current state (verified fact)**: exists in code now
- **Recommendation**: change to implement

## Verification Outcome

### Confirmed

1. Unprotected admin trigger endpoint (`POST /api/v1/heatmap/aggregate-daily`)
2. No rate limit on `GET /api/v1/heatmap/cancellations`
3. Docker compose has no resource caps
4. `key={index}` in station departures list
5. `requestAnimationFrame` callback not cancelled
6. Station page form labels not associated with controls
7. Missing DB index on `gtfs_trips.route_id`
8. No FK from `realtime_station_stats.stop_id` to `gtfs_stops.stop_id`
9. DB pool timeout/recycle/pre-ping not configured
10. Health check is shallow for service dependency verification
11. Postgres/Valkey ports exposed on host in default compose
12. Grafana defaults to `admin/admin` in observability compose
13. `datetime.utcnow()` is used in GTFS-related code
14. GTFS models still use legacy `Column()` style
15. WebGL warning suppression monkeypatch exists
16. Flaky E2E `waitForTimeout(500)`
17. `popupLayout` tests assert static HTML strings, not component behavior

### Partially Confirmed

1. Deduplication race (TOCTOU risk) in GTFS-RT trip marker updates
2. Circuit breaker thread/process safety risk (depends on runtime object sharing)
3. Missing tests for ingestion endpoint and direct `heatmap_cache.py` unit coverage
4. Daily aggregation cron has no explicit retry/backoff policy
5. Cache deserialization/model-validate robustness could be improved

### Not Confirmed

1. “No tests for config loading logic” is incorrect (tests exist in backend and frontend)
2. “Cache key collision risk with varying time precision” not demonstrated as a concrete defect

## Priority Model

- **P0**: Security/integrity exposure or high-probability production impact
- **P1**: Correctness/reliability issues with material impact
- **P2**: Quality hardening and maintainability improvements

## P0 Workstream: Security and Abuse Controls

### P0-1 Protect `POST /heatmap/aggregate-daily`

- Current state:
  - Endpoint has no auth dependency: `backend/app/api/v1/endpoints/heatmap.py:642`
  - Router is included without auth guard: `backend/app/api/v1/routes.py:11`
- Recommendation:
  - Add explicit admin authorization dependency (API key or service-token based).
  - Reject unauthorized requests with `401/403`.
  - Add audit log fields: caller identity, source IP/request id, enqueue result.
- Implementation targets:
  - `backend/app/api/v1/endpoints/heatmap.py`
  - `backend/app/api/v1/shared/dependencies.py` (or new auth module)
  - `backend/app/core/config.py` (admin secret/token config)
  - `backend/tests/api/v1/test_heatmap.py` (auth coverage)
- Acceptance criteria:
  - Anonymous call gets `401/403`.
  - Authorized call enqueues job and returns current response payload.
  - Auth bypass attempts are covered by tests.

### P0-2 Add rate limit to `/heatmap/cancellations`

- Current state:
  - No limiter decorator on cancellations endpoint: `backend/app/api/v1/endpoints/heatmap.py:224`
  - Overview endpoint is already rate-limited: `backend/app/api/v1/endpoints/heatmap.py:472`
- Recommendation:
  - Add `@limiter.limit(...)` policy for cancellations endpoint.
  - Use stricter policy than overview if endpoint cost is higher.
- Implementation targets:
  - `backend/app/api/v1/endpoints/heatmap.py`
  - `backend/app/api/v1/shared/constants.py` (if new limit constant needed)
  - `backend/tests/api/v1/test_heatmap.py` and/or `backend/tests/api/v1/shared/test_rate_limit.py`
- Acceptance criteria:
  - 429 responses are emitted after threshold.
  - Existing normal request path unaffected.

### P0-3 Harden local/compose exposure defaults

- Current state:
  - Default compose exposes DB/cache ports: `docker-compose.yml:77`, `docker-compose.yml:90`
  - No per-service resource caps in default compose.
- Recommendation:
  - Keep backend/frontend mapped; remove host mappings for Postgres/Valkey by default or gate with dev profile.
  - Add resource ceilings for critical services (`backend`, `postgres`, `valkey`, `frontend`) via compose-compatible constraints.
- Implementation targets:
  - `docker-compose.yml`
  - `docs/local-setup.md` (document alternate access path for DB tools)
- Acceptance criteria:
  - `docker compose up` still works for main app.
  - DB/Valkey not exposed unless explicit opt-in.
  - Services have explicit memory/CPU ceilings.

### P0-4 Remove insecure Grafana default credentials

- Current state:
  - Observability compose defaults to `admin/admin`: `docker-compose.observability.yml:21-22`
  - Same defaults are present in `.env.example`: `.env.example:68-69`
- Recommendation:
  - Remove insecure default password value; require user-provided value.
  - Fail startup/document required variables for observability profile.
- Implementation targets:
  - `docker-compose.observability.yml`
  - `.env.example`
  - `docs/runtime-configuration.md`
- Acceptance criteria:
  - Observability stack requires non-default credential configuration.
  - Docs clearly show secure setup path.

## P1 Workstream: Data Integrity and Reliability

### P1-1 Fix dedup TOCTOU risk in trip marker updates

- Current state:
  - Two-step `mget` then `mset` update path can race across concurrent workers:
    - read: `backend/app/services/gtfs_realtime_harvester.py:923`
    - write: `backend/app/services/gtfs_realtime_harvester.py:995`
- Recommendation:
  - Use atomic server-side update strategy (Lua script or transaction/compare-and-set semantics).
  - Preserve “upgrade-to-worse-status” logic while preventing double-counting.
- Implementation targets:
  - `backend/app/services/gtfs_realtime_harvester.py`
  - `backend/tests/services/test_gtfs_realtime_harvester.py` (concurrency scenario)
- Acceptance criteria:
  - Parallel harvest simulations do not inflate counts.
  - Existing behavior for status upgrades remains intact.

### P1-2 Make circuit breaker state safe for shared runtime use

- Current state:
  - Mutable breaker state dict in service object: `backend/app/services/gtfs_realtime.py:149`
- Recommendation:
  - Guard updates with lock or refactor to immutable state transitions.
  - Ensure per-service instance lifecycle is explicit and tested.
- Implementation targets:
  - `backend/app/services/gtfs_realtime.py`
  - `backend/app/api/v1/shared/dependencies.py` (lifetime clarity)
  - `backend/tests/services/test_gtfs_realtime.py`
- Acceptance criteria:
  - Concurrent calls cannot corrupt breaker state.
  - State transitions (`CLOSED`, `OPEN`, `HALF_OPEN`) remain deterministic.

### P1-3 Improve ingestion endpoint and cache-helper test coverage

- Current state:
  - No API tests found for `/system/ingestion-status`.
  - `heatmap_cache.py` helpers are used, but not directly unit-tested as a module.
- Recommendation:
  - Add focused API tests for ingestion status success/fallback/error cases.
  - Add direct unit tests for heatmap cache key normalization and key generation.
- Implementation targets:
  - `backend/tests/api/v1/test_ingestion.py` (new)
  - `backend/tests/services/test_heatmap_cache.py` (new)
- Acceptance criteria:
  - Endpoint behavior validated for missing feed info, missing harvester, and row-count fallback paths.
  - Cache key normalization invariants are directly enforced.

### P1-4 Add DB pool timeout/recycle/pre-ping configuration

- Current state:
  - Engine sets only `pool_size` and `max_overflow`: `backend/app/core/database.py:23-28`
- Recommendation:
  - Add configurable `pool_timeout`, `pool_recycle`, and `pool_pre_ping` settings.
- Implementation targets:
  - `backend/app/core/config.py`
  - `backend/app/core/database.py`
  - `backend/tests/core/test_config.py`
  - `docs/runtime-configuration.md`
- Acceptance criteria:
  - Settings are configurable via env vars and validated.
  - Engine initialization uses new settings.

### P1-5 Strengthen health checks for dependency readiness

- Current state:
  - `/api/v1/health` is lightweight app liveness only: `backend/app/api/v1/endpoints/health.py:13`
  - Compose backend health check targets this endpoint: `docker-compose.yml:60`
- Recommendation:
  - Keep liveness endpoint simple.
  - Add separate readiness endpoint that verifies DB + cache dependencies.
  - Move compose healthcheck to readiness endpoint.
- Implementation targets:
  - `backend/app/api/v1/endpoints/health.py`
  - `backend/tests/api/v1/test_health.py`
  - `docker-compose.yml`
- Acceptance criteria:
  - Liveness remains fast/non-blocking.
  - Readiness fails when DB or cache is unavailable.

## P1 Workstream: API/Schema Robustness

### P1-6 Validate stop path params explicitly

- Current state:
  - Stop IDs are plain `str` params:
    - `backend/app/api/v1/endpoints/transit/stops.py:307`
    - `backend/app/api/v1/endpoints/transit/stops.py:332`
    - `backend/app/api/v1/endpoints/transit/stops.py:385`
- Recommendation:
  - Use `Path(...)` constraints (min/max length, possibly pattern) for stop IDs.
- Implementation targets:
  - `backend/app/api/v1/endpoints/transit/stops.py`
  - `backend/tests/api/v1/test_transit.py` / `test_transit_station_stats.py`
- Acceptance criteria:
  - Invalid path params rejected with 422.
  - Valid stop IDs unaffected.

### P1-7 Add resilient handling for cache/model deserialization failures

- Current state:
  - Multiple code paths assume valid cached model payloads (e.g. `model_validate(...)` in heatmap/stops).
- Recommendation:
  - Catch `ValidationError` and JSON decode errors at API/service boundaries.
  - Treat malformed cache entries as misses; optionally purge bad key.
- Implementation targets:
  - `backend/app/api/v1/endpoints/heatmap.py`
  - `backend/app/api/v1/endpoints/transit/stops.py`
  - `backend/app/services/cache.py`
  - `backend/tests/api/v1/test_heatmap.py`
- Acceptance criteria:
  - Corrupt cache data does not produce 500 when recoverable path exists.

### P1-8 Add `gtfs_trips.route_id` index

- Current state:
  - `gtfs_trips.route_id` exists without dedicated index in migration: `backend/alembic/versions/add_gtfs_tables.py:63-77`
- Recommendation:
  - Add Alembic migration creating index on `gtfs_trips(route_id)`.
- Implementation targets:
  - `backend/alembic/versions/<new_revision>.py`
  - `backend/app/models/gtfs.py` (if index declared in model metadata)
- Acceptance criteria:
  - Migration is reversible and idempotent where practical.
  - Query plans for route joins show index usage.

### P1-9 Add FK for `realtime_station_stats.stop_id` or enforce equivalent integrity

- Current state:
  - `stop_id` in `RealtimeStationStats` is not constrained by FK: `backend/app/persistence/models.py:465`
- Recommendation:
  - Preferred: add FK to `gtfs_stops(stop_id)` with import/refresh compatibility analysis.
  - If FK is intentionally avoided for ingestion speed, document rationale and add periodic orphan cleanup.
- Implementation targets:
  - `backend/app/persistence/models.py`
  - `backend/alembic/versions/<new_revision>.py`
  - `docs/tech-spec.md` (integrity model)
- Acceptance criteria:
  - Integrity policy is explicit and enforced (FK or documented compensating controls).

### P1-10 Review GTFS import transaction boundaries for parallel COPY

- Current state:
  - Import performs parallel COPY across dedicated connections (`TaskGroup` + `_get_asyncpg_conn`) and commits in stages.
- Recommendation:
  - Decide explicit consistency target:
    - all-or-nothing import (single transaction strategy), or
    - staged import with well-defined recovery/rollback behavior.
  - Document and test failure behavior between phases.
- Implementation targets:
  - `backend/app/services/gtfs_feed.py`
  - `backend/tests/services/test_gtfs_feed_importer.py`
  - `docs/tech-spec.md`
- Acceptance criteria:
  - Import failure leaves DB in documented, recoverable state.

## P2 Workstream: Frontend Correctness and Test Quality

### P2-1 Replace unstable React list key usage

- Current state:
  - Departures list uses `key={index}`: `frontend/src/components/features/station/DeparturesBoard.tsx:103`
- Recommendation:
  - Use stable key (`trip_id` + scheduled/realtime timestamp fallback).
- Implementation targets:
  - `frontend/src/components/features/station/DeparturesBoard.tsx`
  - `frontend/src/tests/unit/DeparturesBoard.test.tsx`
- Acceptance criteria:
  - Rendering remains correct under reordering/updates.

### P2-2 Cancel pending RAF callback on cleanup

- Current state:
  - RAF scheduled without cancellation handle: `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx:1118`
- Recommendation:
  - Store RAF id in ref; cancel in cleanup/unmount and before re-scheduling.
- Implementation targets:
  - `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx`
  - `frontend/src/tests/unit/MapLibreHeatmap.test.tsx`
- Acceptance criteria:
  - No stale popup callbacks after unmount.

### P2-3 Associate labels with form controls in Station page

- Current state:
  - Standalone labels without `htmlFor` at `frontend/src/pages/StationPage.tsx:554`, `:571`, `:587`
- Recommendation:
  - Add deterministic `id` to controls and `htmlFor` on labels.
- Implementation targets:
  - `frontend/src/pages/StationPage.tsx`
  - `frontend/src/tests/unit/pages/StationPage.test.tsx`
- Acceptance criteria:
  - Accessible name relationships validated in tests.

### P2-4 Remove fixed sleeps in E2E

- Current state:
  - `waitForTimeout(500)` in test: `frontend/tests/e2e/error-handling.spec.ts:64`
- Recommendation:
  - Replace with state-driven waits (`expect(...).toBeVisible`, locator polling).
- Implementation targets:
  - `frontend/tests/e2e/error-handling.spec.ts`
- Acceptance criteria:
  - Test remains stable under slow CI runners.

### P2-5 Improve weak/unit-test patterns

- Current state:
  - Minimal assertions in shared component tests (`Badge`, `Card`)
  - Static HTML string tests in `popupLayout`
- Recommendation:
  - Test rendered components and behaviors, not synthetic markup literals.
  - Strengthen assertions to verify semantics and behavior changes.
- Implementation targets:
  - `frontend/src/tests/unit/Badge.test.tsx`
  - `frontend/src/tests/unit/Card.test.tsx`
  - `frontend/src/tests/unit/popupLayout.test.tsx`
  - optionally `frontend/src/tests/unit/StationPopup.test.tsx`
- Acceptance criteria:
  - Tests fail on meaningful regressions, not only class-presence smoke checks.

## P2 Workstream: Cleanup and Modernization

### P2-6 Replace deprecated `datetime.utcnow()` usage

- Current state:
  - Usage present in GTFS model/service paths.
- Recommendation:
  - Use timezone-aware UTC (`datetime.now(timezone.utc)`), preserving schema expectations.
- Implementation targets:
  - `backend/app/models/gtfs.py`
  - `backend/app/services/gtfs_feed.py`
- Acceptance criteria:
  - No `utcnow` calls remain in backend app code.

### P2-7 Plan migration from legacy SQLAlchemy `Column()` GTFS models

- Current state:
  - GTFS models use legacy style in `backend/app/models/gtfs.py`.
- Recommendation:
  - Migrate incrementally to `Mapped[...]` + `mapped_column(...)`.
  - Keep runtime behavior unchanged; prioritize readability and typing.
- Implementation targets:
  - `backend/app/models/gtfs.py`
  - related typing/tests
- Acceptance criteria:
  - Type checks pass; no runtime query behavior regressions.

### P2-8 Remove or scope WebGL warning monkeypatch

- Current state:
  - `console.warn` monkeypatch in component setup: `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx:405`
- Recommendation:
  - Replace with targeted logging filter strategy or remove suppression.
  - Ensure cleanup remains reliable if suppression retained.
- Implementation targets:
  - `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx`
  - `frontend/src/tests/unit/MapLibreHeatmap.test.tsx`
- Acceptance criteria:
  - Debug logging remains useful without global console side effects.

## Deferred / Clarification Items

1. **Config loading test gap**: Not actionable (tests already exist):
   - `backend/tests/core/test_config.py`
   - `frontend/src/tests/unit/config.test.ts`
2. **Cache key collision claim**: Keep under observation unless concrete failing scenario is produced.

## Delivery Plan

### Phase 1 (P0)

- Auth + rate limiting + compose exposure + Grafana credential hardening
- Goal: close immediate security/abuse gaps

### Phase 2 (P1)

- Dedup race hardening, breaker safety, health/readiness split, DB schema/index/integrity, ingestion/cache tests
- Goal: correctness and resilience

### Phase 3 (P2)

- Frontend correctness/accessibility/test quality + modernization/deprecation cleanup
- Goal: maintainability and regression resistance

## Validation Matrix

- Backend:
  - `pytest backend/tests`
  - targeted: `pytest backend/tests/api/v1 backend/tests/services`
- Frontend:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run type-check`
  - `cd frontend && npm run test -- --run`
  - `cd frontend && npm run test:e2e` (targeted specs first)
- Security/config:
  - `pre-commit run detect-secrets --all-files`

## Notes

- This plan intentionally excludes issues that were not validated in current code.
- If runtime deployment topology differs (single-process vs multi-worker), reprioritize the concurrency items accordingly.
