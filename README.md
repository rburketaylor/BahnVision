# BahnVision
FastAPI backend and React frontend for Munich transit data: live MVG departures, station search, route planning, and Prometheus metrics. Designed for low-latency responses with Valkey caching and PostgreSQL persistence.

## Overview
- Backend exposes versioned REST APIs for departures, station search, routes, health, and metrics.
- Cache-first reads with single-flight locking and stale fallbacks keep responses predictable during upstream issues.
- Persistence layer prepares historical telemetry to unlock future analytics and forecasting.

## Features
- FastAPI with typed Pydantic schemas and dependency injection.
- Valkey-backed cache with stampede protection and stale refresh.
- Async SQLAlchemy targeting PostgreSQL; Alembic-ready migrations.
- Prometheus metrics at `/metrics` for latency, cache events, and MVG health.
- Docker Compose for local development.
- Optional cache warmup container hydrates MVG station data during startup so the first user doesn't wait for MVG.

## Quick Start
- Docker Compose (recommended):
  1) `docker compose up --build`
     - Compose launches a short-lived `cache-warmup` container that runs `python -m app.jobs.cache_warmup` before the API starts, hydrating Valkey/Postgres with the MVG station catalog.
  2) API docs: http://127.0.0.1:8000/docs
  3) Frontend: http://127.0.0.1:3000

- Local Python environment:
  1) `python -m venv .venv && source .venv/bin/activate`
  2) `pip install -r backend/requirements.txt`
  3) Ensure Valkey and PostgreSQL are reachable (compose defaults)
  4) `uvicorn app.main:app --reload --app-dir backend`

Frontend quick start: see `frontend/README.md`.

## Configuration
- `VALKEY_URL` — cache connection string (default `valkey://localhost:6379/0`).
- `DATABASE_URL` — async SQLAlchemy DSN (default `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`).
- Per-feature TTLs: `MVG_DEPARTURES_CACHE_TTL_SECONDS`, `MVG_STATION_SEARCH_CACHE_TTL_SECONDS`, `MVG_ROUTE_CACHE_TTL_SECONDS` and corresponding `_STALE_TTL_SECONDS`.
- Single-flight tuning: `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS`, `CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS`.
- Circuit breaker window: `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`.
- Cache warmup knobs: `CACHE_WARMUP_DEPARTURE_STATIONS` (comma-separated station queries), `CACHE_WARMUP_DEPARTURE_LIMIT` (defaults to 10), `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES` (defaults to 0).

Store secrets and overrides in environment variables or a local `.env` (not committed). See `docs/runtime-configuration.md` for a full list and examples. Copy `.env.example` to `.env` at the repo root to get started. Docker Compose reads `.env` for the backend and passes `VITE_*` envs to the frontend build.

## Cache Warmup
- Run manually via `cd backend && python -m app.jobs.cache_warmup` to hydrate the station catalog (and optional departures caches) without starting the API.
- Docker Compose executes the same command through the `cache-warmup` service before the backend container starts, so the very first search reuses cached MVG data.
- Configure departure hydration with `CACHE_WARMUP_DEPARTURE_STATIONS`, `CACHE_WARMUP_DEPARTURE_LIMIT`, and `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES`. Leave the station list empty to skip departures warmup.

## API
- `GET /api/v1/health` — readiness probe
- `GET /api/v1/mvg/stations/search` — station autocomplete
- `GET /api/v1/mvg/departures` — live departures
- `GET /api/v1/mvg/routes/plan` — route planning
- `GET /metrics` — Prometheus metrics

Sample:
```bash
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=marienplatz&transport_type=UBAHN"
```

## Project Structure
- `backend/app` — FastAPI app
  - `main.py` — app bootstrap and router registration
  - `api/` — versioned routes and metrics exporter
  - `services/` — stateless domain services (cache, MVG client)
  - `models/` — Pydantic request/response schemas
  - `persistence/` — SQLAlchemy models, repositories, dependencies
  - `core/` — config and shared database engine
- `backend/tests` — pytest suites for routes, caching, metrics
- `backend/docs` — backend architecture, product, operations, roadmap
- `frontend` — React app (see its README)
- `docker-compose.yml` — API + Valkey + Postgres + Frontend for local runs

## Development
- Run API locally: `uvicorn app.main:app --reload --app-dir backend`
- Run tests: `pytest backend/tests`
- Compose stack: `docker compose up --build`

## Documentation
- Backend docs hub: `backend/docs/README.md`
- Backend tech spec: `backend/docs/architecture/tech-spec.md`
- Frontend docs hub: `frontend/docs/README.md`

## Contributing
- Conventional Commits (e.g., `feat:`, `fix:`, `docs:`)
- Include a brief rationale in PRs; document non-default runtime options
