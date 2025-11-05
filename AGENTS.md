# Agent Guide

This document is the canonical guide for all AI coding assistants working in this repository. It consolidates the most accurate guidance from prior assistant-specific files.

## What This Project Is
- BahnVision delivers Munich public transit data via a FastAPI backend and a React + TypeScript frontend.
- Backend emphasizes predictable latency using Valkey-backed caching with single-flight locks, stale fallbacks, and circuit-breaker behavior.
- Persistence uses async SQLAlchemy with a shared engine; observability exports Prometheus metrics.

## Core References
- Backend spec: `backend/docs/architecture/tech-spec.md`
- Frontend docs hub: `frontend/docs/README.md`
- Compose topology and envs: `docker-compose.yml`

## Agent Protocol
- Read before changing; propose small, verifiable plans.
- Run and test locally; avoid destructive operations.
- Prefer `rg` for search; read files in manageable chunks.
- Do not guess package versions; verify and pin exact versions.
- Keep changes minimal and scoped; follow existing structure and style.

## Repository Structure
- Backend runtime: `backend/app`
  - `main.py` — FastAPI app factory with lifespan management
  - `api/routes.py` — registers versioned routers under `/api/v1`
  - `api/metrics.py` — exposes Prometheus metrics at `/metrics`
  - `services/` — shared infrastructure (e.g., MVG client, cache service)
  - `models/` — Pydantic schemas for request/response validation
  - `persistence/` — async SQLAlchemy models, repositories, dependencies
  - `core/config.py` — Pydantic settings, Valkey/database config
- Frontend runtime: `frontend/`
  - `src/components`, `src/pages`, `src/hooks`, `src/services`
  - Vite + React 19 + TypeScript; Tailwind; TanStack Query; React Router

## Running the Stack
- Local (backend):
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r backend/requirements.txt`
  - `uvicorn app.main:app --reload --app-dir backend` → `http://127.0.0.1:8000`
- Local (frontend):
  - `npm install`
  - `npm run dev` → `http://127.0.0.1:5173`
- Docker Compose (recommended):
  - `docker compose up --build`
  - Backend at `http://127.0.0.1:8000`; Frontend at `http://127.0.0.1:3000`
- Database connectivity:
  - Default `DATABASE_URL` (local): `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`
  - Compose overrides target the `postgres` service per `docker-compose.yml`

## Backend Architecture
- Dependency injection: use FastAPI dependencies for services and repositories.
- Service layer:
  - `services/mvg_client.py` wraps MVG API requests and instruments latency/metrics; maps results and errors.
  - `services/cache.py` provides Valkey-backed cache with:
    - Single-flight locking to prevent stampedes
    - Stale reads with background refresh
    - Circuit breaker fallback to in-process store on failures
- Cache configuration (selected env vars):
  - `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `_WAIT_SECONDS`, `_RETRY_DELAY_SECONDS`
  - `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`
  - Endpoint-specific TTLs (e.g., `MVG_*_CACHE_TTL_SECONDS`, `*_STALE_TTL_SECONDS`)
- Persistence layer (`backend/app/persistence/`):
  - Async SQLAlchemy models and repositories
  - `core/database.py` provides a shared async engine
- HTTP schemas in `backend/app/models/` enforce request/response contracts.

## Frontend Architecture
- Stack: React 19, TypeScript, Vite, Tailwind, TanStack Query, React Router.
- Structure: components, pages, hooks, and services under `frontend/src`.
- Testing: Vitest, React Testing Library, Playwright; MSW for API mocking.

## Observability
- Metrics (Prometheus):
  - `bahnvision_cache_events_total{cache,event}` — events include examples like `hit`, `miss`, `stale_return`, `lock_timeout`, `not_found`, `refresh_success`, `refresh_error`, `refresh_skip_hit`, `refresh_not_found`, `background_not_found`, `background_lock_timeout`.
  - `bahnvision_cache_refresh_seconds{cache}` — histogram of cache refresh latency.
  - `bahnvision_mvg_requests_total{endpoint,result}` — MVG client request outcomes.
  - `bahnvision_mvg_request_seconds{endpoint}` — histogram of MVG client request latency.
  - Planned: `bahnvision_api_request_duration_seconds{route}` and `bahnvision_api_exceptions_total{route,type}`.
- Response headers: `X-Cache-Status` indicates cache path (`hit`, `miss`, `stale`, `stale-refresh`).
- Planned: structured JSON logging with `request_id`, `station_id`, `cache_status`, `mvg_status`.
- SLAs (targets): cache hit ratio >70%, MVG P95 latency <750ms, API exception rate <5/min.

## Coding Style
- Python: PEP 8, 4-space indentation, snake_case modules.
- Prefer typed function signatures; use Pydantic for validation.
- Keep services stateless; co-locate HTTP schemas with consuming routes.
- Frontend: standard React/TS practices; organize by components/pages/hooks/services.

## Testing Guidelines
- Backend:
  - Use `pytest`; place tests under `backend/tests/` mirroring `app/`.
  - Test FastAPI routes via `TestClient`; override dependencies as needed.
  - Use in-memory doubles (e.g., `FakeValkey`, `FakeMVGClient`) to keep tests deterministic.
- Frontend:
  - Unit/integration via Vitest + React Testing Library
  - E2E via Playwright; use MSW for API mocking

## Dependency & Versioning Policy
- Verify current versions (e.g., `pip index versions <pkg>`); do not guess based on memory.
- Pin exact versions (use `==`) for reproducible builds.
- Typical workflow:
  - Check versions → update `backend/requirements.txt` → install → verify.

## Security & Configuration
- Store secrets (Valkey URLs, API tokens) in environment variables or a local `.env` kept out of version control.
- Document non-default runtime options (e.g., custom `DATABASE_URL`, cache TTL overrides) in PRs.
 - Valkey settings accept legacy `REDIS_*` env var aliases for backward compatibility.

## Commit & PR Guidelines
- Follow Conventional Commits (e.g., `feat:`, `fix:`, `docs:`, `build:`).
- Keep subjects concise; include a body for multi-file changes.
- Reference related issues; highlight config/schema updates and any manual steps.
- Include screenshots or sample responses for endpoint changes.

## Common Gotchas
- Cache writes populate both Valkey and fallback store (circuit-breaker resilience).
- Single-flight lock timeouts may need tuning for long refreshes.
- Stale cache keys use `:stale` suffix; inspect both `{key}` and `{key}:stale`.
- SQLAlchemy engine disposal occurs in app lifespan; tests must respect this lifecycle.
- Transport type enum casing: API accepts case-insensitive input; MVG uses uppercase.

## Troubleshooting
- Backend not starting: confirm `DATABASE_URL` and Valkey reachability, then retry.
- Cache behaving unexpectedly: check metrics and `:stale` keys; verify TTL envs.
- Frontend API calls failing: verify `VITE_API_BASE_URL` and CORS; ensure backend is reachable.

This AGENTS.md is authoritative for all assistants working in this repository.
