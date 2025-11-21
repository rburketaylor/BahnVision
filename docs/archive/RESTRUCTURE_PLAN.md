## BahnVision Codebase Restructure & Improvement Plan

This document captures the planned structural and quality improvements discussed in the recent analysis. The goal is to enhance security, readability, separation of concerns, and maintainability without changing externally visible behavior.

---

## Overall Strategy

- Tackle work in phases: documentation/navigation first, then backend structure, then frontend/API, then security/infra and tests.
- Keep architecture aligned with `docs/tech-spec.md`; focus on splitting large units into smaller, cohesive modules and tightening contracts.

---

## Phase 0 – Documentation & Navigation

**Goal:** Fix inconsistencies, make docs discoverable, and support future automation.

### 0.1 Fix Critical Doc Issues

- Update `AGENTS.md` backend spec reference to `docs/tech-spec.md` (as flagged in `DOCUMENTATION_VERIFICATION_REPORT.md`).
- Update or archive `docs/devops/pipeline-changes.md` so it no longer claims metrics “don’t exist” when they do.
- Clean up `README.md` references that still point at archived `backend/docs/archive/tech-spec.md`.

### 0.2 Consolidate Architecture Docs

- Treat `docs/tech-spec.md` as the single canonical tech spec.
- In `backend/docs/README.md` and `frontend/docs/README.md`, add explicit “Start here” links back to `docs/tech-spec.md`.
- For archived specs under `backend/docs/archive`, clearly mark them as historical and link forward to the canonical spec.

### 0.3 Mark Future/Aspirational Docs

- Add “Status: Planned” / “Status: Aspirational” banners to:
  - `docs/devops/pipeline-changes.md` (if not archived)
  - `frontend/docs/operations/observability.md`
  - Frontend roadmap docs.
- Where applicable, add a short “Current state vs planned state” section.

---

## Phase 1 – Backend Core Refactor (Structure & Readability)

**Goal:** Split large backend modules into smaller, focused units without changing behavior.

### 1.1 MVG Client Refactor (`backend/app/services/mvg_client.py`)

**Motivation:** File is ~685 lines and mixes DTOs, mapping helpers, transport parsing, concurrency, and metrics.

**Plan:**

1. **Extract errors & DTOs**
   - Move `StationNotFoundError`, `MVGServiceError`, `RouteNotFoundError` into `backend/app/services/mvg_errors.py`.
   - Move data classes `Station`, `Departure`, `RouteStop`, `RouteLeg`, `RoutePlan` into `backend/app/services/mvg_dto.py`.
2. **Extract mapping utilities**
   - Move `DataMapper` and `_map_*` helpers into `backend/app/services/mvg_mapping.py`.
   - Keep mapping pure and side-effect-free (no IO or logging).
3. **Slim down `MVGClient`**
   - Keep only:
     - Orchestration of `MvgApi` calls.
     - Concurrency logic (`asyncio.to_thread`, `asyncio.gather`).
     - Error classification and metrics (`observe_mvg_request`, `record_mvg_transport_request`).
   - Ensure `get_client()` remains available for backward compatibility, but prefer usage via `app.api.v1.endpoints.mvg.shared.utils`.
4. **Extract transport-type parsing**
   - Move `parse_transport_types` into `backend/app/services/mvg_transport.py` with:
     - Normalization of names/synonyms.
     - Deduplication and error messages.
   - Add focused unit tests covering valid, invalid, and duplicate inputs.

### 1.2 Cache Service Refactor (`backend/app/services/cache.py`)

**Motivation:** File is ~360 lines and mixes TTL config, circuit breaker, in-memory store, and cache service.

**Plan:**

1. **Split configuration from behavior**
   - Move `TTLConfig` into `backend/app/services/cache_ttl_config.py`.
   - Ensure it is the only place reading TTL-related fields from `Settings`.
2. **Extract circuit breaker**
   - Move `CircuitBreaker` into `backend/app/services/cache_circuit_breaker.py`.
   - Narrow exceptions where feasible; at minimum log the original exception before opening.
3. **Extract in-memory fallback store**
   - Move `InMemoryFallbackStore` into `backend/app/services/cache_fallback_store.py`.
   - Document memory behavior and consider a future max-size or LRU eviction policy.
4. **Slim `SimplifiedCacheService`**
   - Keep public cache interface:
     - `get_json`, `get_stale_json`, `set_json`, `delete`, `single_flight`.
   - Keep dependency helpers (`get_valkey_client`, `get_cache_service`) and alias (`CacheService`).
5. **Expired entry cleanup**
   - Decide on a strategy to invoke `cleanup_expired` (e.g., periodic background task or opportunistic cleanup).

### 1.3 Shared Caching Refactor (`backend/app/api/v1/shared/caching.py`)

**Motivation:** ~440-line module combining protocols, lookup/refresh flows, and error handling.

**Plan:**

1. **Split primitives and flows**
   - Move `CacheResult`, `CacheRefreshProtocol`, and `MvgCacheProtocol` into `backend/app/api/v1/shared/cache_protocols.py`.
   - Move `handle_cache_lookup`, `handle_cache_errors`, `execute_cache_refresh`, `execute_background_refresh` into `backend/app/api/v1/shared/cache_flow.py`.
   - Keep `CacheManager` in `backend/app/api/v1/shared/cache_manager.py` as a thin orchestrator.
2. **Narrow error handling**
   - Replace broad `except Exception` with specific exception types where known.
   - Retain a single defensive `except Exception` with `logger.exception` for truly unexpected failures.
3. **Update call sites**
   - Update all endpoints (`departures.py`, `routes.py`, station endpoints) to import from new modules.
   - Ensure any metric names and cache keys remain unchanged.

## Phase 2 – Frontend Restructure (API & Config)

**Goal:** Make API interactions and configuration more modular and testable; reduce coupling in the client.

### 2.1 API Client Split (`frontend/src/services/api.ts`)

**Motivation:** Single file mixes HTTP transport, error modeling, timeout strategies, and endpoint-specific methods.

**Plan:**

1. **Core HTTP layer**
   - Create `frontend/src/services/httpClient.ts` that:
     - Implements generic `request<T>` with:
       - `fetch` + `AbortController` timeout logic.
       - Parsing `X-Cache-Status` and `X-Request-Id` headers.
       - Mapping non-2xx responses to `ApiError`.
   - Keep this layer independent of MVG-specific paths.
2. **Endpoint-specific client**
   - Create `frontend/src/services/endpoints/mvgApi.ts` containing:
     - `getHealth`
     - `searchStations`
     - `getDepartures`
     - `planRoute`
     - `getMetrics`
   - Each function:
     - Accepts typed params.
     - Builds query strings.
     - Calls `httpClient.request`.
3. **Shared API types**
   - Move `ApiError` and `ApiResponse` into `frontend/src/services/apiTypes.ts`.
   - Keep type-only imports for `CacheStatus`, responses, and param types from `frontend/src/types/api`.
4. **Update consumers**
   - Update existing consumers to use either:
     - A singleton `mvgApiClient`, or
     - Direct named exports from `mvgApi.ts`.

### 2.2 Query Hooks

- Create TanStack Query hooks:
  - `frontend/src/hooks/useHealth.ts`
  - `frontend/src/hooks/useStationSearch.ts`
  - `frontend/src/hooks/useDepartures.ts`
  - `frontend/src/hooks/useRoutePlan.ts`
- Responsibilities:
  - Define query keys.
  - Configure cache/stale times based on backend TTLs.
  - Expose `cacheStatus` and `requestId` together with data and errors, for UI/observability.

### 2.3 Frontend Tests

- Extend `frontend/src/tests/unit/api.test.ts` to cover:
  - 4xx and 5xx responses → `ApiError` with correct `statusCode` and `detail`.
  - Timeout path (`AbortError`) → `ApiError` with code `408`.
  - Generic network failures → `ApiError` with code `0`.
- Add tests for new hooks using MSW and TanStack Query test utilities to validate caching and re-fetch behaviors.

---

## Phase 3 – Testing & Quality Gates

**Goal:** Protect refactors with targeted tests and simplify future changes.

### 3.1 Backend Unit Tests

- Add focused tests for:
  - `parse_transport_types` in `mvg_transport.py`.
  - `DataMapper` (valid and malformed payloads).
  - Cache primitives:
    - `TTLConfig.get_effective_ttl` / `get_effective_stale_ttl`.
    - `CircuitBreaker` open/close behavior.
    - `SingleFlightLock` success and timeout paths.
- Add tests for cache flows:
  - `handle_cache_lookup` hit/stale/miss behavior.
  - `handle_cache_errors` mapping:
    - Timeout → 503 with stale fallback when available.
    - `StationNotFoundError` / `RouteNotFoundError` → 404.
    - `MVGServiceError` → 502 with stale fallback when available.

### 3.2 Integration Tests

- Ensure `backend/tests` still cover:
  - `/api/v1/mvg/departures` & `/api/v1/mvg/routes/plan` end-to-end behavior post-refactor.
  - `X-Cache-Status` and `X-Request-Id` headers in responses.
- Update imports in existing tests to reflect new module layout without broad behavior changes.

### 3.3 Quality Gates

- If not already present, consider adding to CI:
  - Python lint/format (e.g., `ruff`, `black`).
  - Frontend lint (`eslint`) and typechecking (`tsc`, `vite typecheck`).
  - Minimal coverage thresholds to catch regressions (backend and frontend).

---

## Phase 4 – Documentation Updates

**Goal:** Keep docs aligned with current behavior.

- Update `docs/tech-spec.md` and `frontend/docs/operations/observability.md` to:
  - Clearly separate current vs planned observability features.
  - Include example log entries and PromQL queries for common dashboards.

---

## Execution Order & Suggested PR Breakdown

1. Implement **Phase 0** doc fixes and status markers (low risk).
2. Add and/or update tests from **Phase 3** that will guard `mvg_client`, cache, and shared caching logic.
3. Execute **Phase 1** backend refactors in small PRs:
   - PR 1: MVG client split (errors/DTOs/mapping/transport helpers).
   - PR 2: Cache service split (TTL config, circuit breaker, fallback store).
   - PR 3: Shared caching refactor.
4. Restructure the frontend per **Phase 2** (HTTP client, endpoint modules, hooks).
5. Implement **Phase 4** documentation updates.

This plan is intentionally modular so you can implement phases and sub-phases incrementally, watching metrics and tests after each step rather than attempting a single large refactor.
