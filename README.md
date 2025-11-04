# BahnVision
FastAPI-powered transit intelligence service that ingests live MVG data, caches it for low-latency responses, and prepares historical telemetry for future predictive features. This repo is my showcase for production-grade backend architecture, reliability patterns, and observability-first engineering.

## Elevator Pitch
Munich riders need dependable departures, route planning, and station search even when upstream APIs misbehave. BahnVision delivers a resilient API with Valkey-backed caching, PostgreSQL persistence, and Prometheus metrics so a React/Leaflet frontend (in progress) can stay fast and trustworthy. The system is designed to survive MVG outages by serving stale-but-safe data, while capturing enough history to unlock Phase 2 forecasting and AI guidance.

## Feature Highlights
- Live MVG departures, route planning, and station search endpoints with strict Pydantic validation and typed FastAPI dependencies.
- Resilience-first cache layer: Valkey single-flight locking, circuit breaker fallbacks, and stale refresh workflows surfaced via `X-Cache-Status`.
- Async SQLAlchemy persistence ready for historical departures, routes, weather enrichment, and ingestion metadata.
- Built-in Prometheus instrumentation for API latency, cache behaviour, and MVG request health exposed at `/metrics`.
- Docker Compose environment wiring the API with Valkey, plus pytest suites that verify cache behaviour, stale fallbacks, and metrics.

## Architecture Overview
- **FastAPI application factory** in `backend/app/main.py` wires versioned routers, metrics, and lifespan cleanup.
- **Layered services** under `backend/app/services/` encapsulate the cache service and MVG client integration used by the API.
- **CacheService** combines Valkey with an in-process fallback store, single-flight locks, and a configurable circuit breaker.
- **Persistence layer** (`backend/app/persistence/`) shares an async engine (`core/database.py`) and targets Alembic migrations for schema evolution.
- **Observability** is built-in via `app/core/metrics.py`, Prometheus-compatible histograms/counters, and tests in `backend/tests/api/test_metrics.py`.
- **Configuration** centralised in `core/config.py` with `.env` support, making it easy to tune TTLs, database pools, and feature flags per environment.

### Tech Stack
- Python 3, FastAPI, Pydantic, Starlette
- Async SQLAlchemy + Alembic migrations targeting PostgreSQL
- Valkey (Redis-compatible) cache with asyncio client
- Prometheus client library for metrics
- pytest + HTTPX TestClient + Faker for unit and integration coverage
- Docker + Docker Compose for reproducible local environments

### Directory Tour
- `backend/app/api/` – versioned routers, health, MVG endpoints, and metrics exporter.
- `backend/app/services/` – cache orchestration (`cache.CacheService`) and MVG API client wrappers.
- `backend/app/models/` – Pydantic schemas for HTTP contracts and persistence DTOs.
- `backend/app/persistence/` – SQLAlchemy models, repositories, and database dependencies.
- `backend/tests/` – pytest suites covering API flows, cache behaviour, and metrics.
- `backend/docs/` – documentation hub (see `backend/docs/README.md` for the architecture, product, roadmap, and archive layout).
- `frontend/docs/` – React app documentation hub (see `frontend/docs/README.md` for architecture, product, operations, and roadmap notes).
- `docs/` – cross-project guidance (assistant handbooks, repo operations guidelines).

## Getting Started

### Option 1: Docker Compose (recommended)
1. Install Docker & Docker Compose.
2. Run `docker compose up --build`.
3. Visit `http://127.0.0.1:8000/docs` for the interactive OpenAPI explorer.

### Option 2: Local Python environment
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r backend/requirements.txt`
3. Ensure Valkey and PostgreSQL are reachable (defaults match `docker-compose.yml`).
4. `uvicorn app.main:app --reload --app-dir backend`

## Configuration
- `VALKEY_URL` – cache connection string (`valkey://localhost:6379/0` by default).
- `DATABASE_URL` – async SQLAlchemy DSN (`postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`).
- `MVG_*_CACHE_TTL_SECONDS` – granular TTLs for departures, station search, and routes (live + stale durations).
- `CACHE_SINGLEFLIGHT_*` – lock TTL, wait timeout, and retry delay for cache stampede prevention.
- `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS` – how long to fallback to in-process cache when Valkey is unhealthy.

## Testing & Quality
- `pytest backend/tests` exercises API endpoints, cache fallbacks, and metrics exposure.
- Fixtures in `backend/tests/conftest.py` stub MVG responses, simulate Valkey outages, and verify resilience logic.
- Type hints and static assertions keep FastAPI dependencies explicit and editor-friendly.
- Future CI plan includes running Alembic migrations against ephemeral Postgres (see roadmap MS1-T3).

## API Surface
- `GET /api/v1/health` – readiness ping used by orchestrators.
- `GET /api/v1/mvg/departures` – live departures with support for transport filters, limit/offset, and cache status headers.
- `GET /api/v1/mvg/stations/search` – fuzzy station lookup for type-ahead UIs.
- `GET /api/v1/mvg/routes/plan` – multi-leg itinerary planner supporting departure/arrival targets and cacheable not-found markers.
- `GET /metrics` – Prometheus scrape endpoint instrumenting API latency, cache events, MVG call counts, and refresh durations.

Sample request:

```bash
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=marienplatz&transport_type=UBAHN"
```

## Data & Persistence
- PostgreSQL schema covers `stations`, `transit_lines`, `departure_observations`, `route_snapshots`, `weather_observations`, and `ingestion_runs`.
- Enumerations and constraints capture transport modes, departure states, weather conditions, and ingestion statuses for analytics readiness.
- Alembic integration (tracked in `backend/alembic/`) will evolve schemas as milestones from `backend/docs/roadmap/tasks.json` land.
- Phase 2 persistence will log MVG responses for ML training while keeping API latency low via cache-first reads.

## Observability
- Counters: `bahnvision_cache_events_total`, `bahnvision_mvg_requests_total`, `bahnvision_api_exceptions_total`.
- Histograms: `bahnvision_api_request_duration_seconds`, `bahnvision_cache_refresh_duration_seconds`, `bahnvision_mvg_request_duration_seconds`.
- X-Cache-Status header communicates `hit`, `miss`, `stale`, or `stale-refresh` paths so clients and logs can track freshness.
- Planned additions include structured JSON logging with correlation IDs and Grafana dashboards (see roadmap MS4).

## Future Roadmap
- **MS1 & MS2** – Ship Alembic migrations and persist departures/routes directly from service workflows.
- **MS3** – Harden cache single-flight locking, stale refresh instrumentation, and not-found suppression.
- **MS4** – Codify Prometheus metrics, structured logging, alert rules, and Grafana dashboard templates.
- **MS5** – Enable weather ingestion, retention pruning job, and feature-flagged background workers.
- **MS6** – Document rollout playbook, agree on MVG latency SLAs, and build 20rps load testing suites.
- **Phase 2 vision** – Predictive delay insights, AI journey guidance, and richer multi-modal analytics once historical data accrues.

## Hiring Manager Notes
- Demonstrates experience designing resilient distributed systems: cache circuit breakers, stale data strategies, and background refresh tasks.
- Highlights pragmatic DevOps alignment: Docker-first workflow, metrics-ready endpoints, and planned alerting artefacts.
- Shows product thinking via personas, success metrics, and a maintained milestone roadmap under `backend/docs/roadmap/tasks.json`.
- Offers strong testing discipline with deterministic cache simulations and fixtures that mimic upstream failures.

I’m using BahnVision as a profile piece—feedback and collaboration are welcome! Feel free to open issues or reach out if you’d like a guided tour.
