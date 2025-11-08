# BahnVision Backend

FastAPI service that serves MVG departures, station search, route planning, health, and Prometheus metrics. Uses Valkey for low‑latency caching and PostgreSQL for persistence.

## Quick Start

- Docker Compose (recommended):
  - `docker compose up --build`
  - API docs: http://127.0.0.1:8000/docs
  - Metrics: http://127.0.0.1:8000/metrics

- Local Python environment:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -r backend/requirements.txt`
  - `uvicorn app.main:app --reload --app-dir backend`

## Configuration

- `VALKEY_URL` — cache DSN (default `valkey://localhost:6379/0`)
- `DATABASE_URL` — async DSN (default `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`)
- Per-feature TTLs: `MVG_DEPARTURES_CACHE_TTL_SECONDS`, `MVG_STATION_SEARCH_CACHE_TTL_SECONDS`, `MVG_ROUTE_CACHE_TTL_SECONDS` and corresponding `_STALE_TTL_SECONDS`
- Single‑flight tuning: `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS`, `CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS`
- Circuit breaker window: `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`

Legacy `REDIS_*` variables are accepted for backward compatibility. See `docs/runtime-configuration.md` for a complete list. Place your `.env` at the repository root (copy from `.env.example`).

## API Endpoints

- `GET /api/v1/health` — readiness probe
- `GET /api/v1/mvg/stations/search` — station autocomplete
- `GET /api/v1/mvg/departures` — live departures
- `GET /api/v1/mvg/routes/plan` — route planning
- `GET /metrics` — Prometheus metrics

Example:
```bash
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=de:09162:6&transport_type=UBAHN"
```

## Caching

Valkey‑backed cache with cache‑aside reads, single‑flight stampede protection, and stale refresh to keep latency predictable during upstream issues. See technical details in `backend/docs/architecture/tech-spec.md`.

## Database

Async SQLAlchemy engine and repositories live under `backend/app/persistence/`. Configure via `DATABASE_URL`. Alembic migrations are planned to evolve schemas alongside features.

## Development

- Run API: `uvicorn app.main:app --reload --app-dir backend`
- Tests: `pytest backend/tests`
- Compose stack: `docker compose up --build`

## Documentation

- Docs hub: `backend/docs/README.md`
- Technical spec: `backend/docs/architecture/tech-spec.md`
 - Roadmap & branch plan: `backend/docs/roadmap/persistence-branch-plan.md`

## Contributing

- Use Conventional Commits (e.g., `feat:`, `fix:`, `docs:`)
- Include rationale and any non‑default runtime options in PRs
