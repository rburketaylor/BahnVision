# Runtime Configuration

Centralized reference for environment variables and `.env` usage across the repository.

## File Locations

- Backend `.env`: place at the repository root when running locally (matches `backend/app/core/config.py` which loads `.env` from the current working directory).
- Frontend `.env`: place at `frontend/.env` (Vite reads variables prefixed with `VITE_`).
- Docker Compose: variables are set inline in `docker-compose.yml`. Override via environment or `.env`.

## Backend (FastAPI)

Place variables in the root `.env` or export them in the shell. Defaults are shown in parentheses.

- `VALKEY_URL` (valkey://localhost:6379/0) — Valkey/Redis connection.
- `VALKEY_CACHE_TTL_SECONDS` (30) — Base TTL for generic cache items.
- `VALKEY_CACHE_TTL_NOT_FOUND_SECONDS` (15) — TTL for not-found markers.
- `TRANSIT_DEPARTURES_CACHE_TTL_SECONDS` (30) — Live TTL for departures.
- `TRANSIT_DEPARTURES_CACHE_STALE_TTL_SECONDS` (300) — Stale TTL for departures.
- `TRANSIT_STATION_SEARCH_CACHE_TTL_SECONDS` (60) — Live TTL for station search.
- `TRANSIT_STATION_SEARCH_CACHE_STALE_TTL_SECONDS` (600) — Stale TTL for station search.
- `TRANSIT_STATION_LIST_CACHE_TTL_SECONDS` (86400) — Live TTL for station list.
- `TRANSIT_STATION_LIST_CACHE_STALE_TTL_SECONDS` (172800) — Stale TTL for station list.
- `TRANSIT_ROUTE_CACHE_TTL_SECONDS` (120) — Live TTL for route planning.
- `TRANSIT_ROUTE_CACHE_STALE_TTL_SECONDS` (900) — Stale TTL for route planning.
- `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS` (5) — Single-flight lock TTL.
- `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS` (5.0) — Wait time for lock.
- `CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS` (0.05) — Retry delay while waiting.
- `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS` (2.0) — Serve stale window when cache is unhealthy.
- `HEATMAP_CACHE_TTL_SECONDS` (300) — Cache TTL for heatmap aggregations.
- `CACHE_WARMUP_DEPARTURE_STATIONS` — Optional comma-separated list of station names/IDs to prewarm departures cache keys.
- `CACHE_WARMUP_DEPARTURE_LIMIT` (10) — Number of departures requested per warmup station.
- `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES` (0) — Offset minutes applied to warmup departures.
- `HEATMAP_CACHE_WARMUP_ENABLED` (true) — Enable/disable heatmap cache warmup after each GTFS-RT harvest.
- `HEATMAP_CACHE_WARMUP_TIME_RANGES` (24h) — Comma-separated list of heatmap `time_range` presets to prewarm.
- `HEATMAP_CACHE_WARMUP_ZOOM_LEVELS` (6,10) — Comma-separated list of zoom levels to prewarm.
- `HEATMAP_CACHE_WARMUP_BUCKET_WIDTH_MINUTES` (60) — Bucket width minutes to prewarm.
- `CORS_ALLOW_ORIGINS` — Comma-separated list of allowed origins (no `*`).
- `CORS_ALLOW_ORIGIN_REGEX` — Optional regex for origins.
- `DATABASE_URL` (postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision) — Async SQLAlchemy DSN.
- `DATABASE_POOL_SIZE` (10) — SQLAlchemy pool size.
- `DATABASE_MAX_OVERFLOW` (10) — SQLAlchemy max overflow.
- `DATABASE_POOL_TIMEOUT_SECONDS` (30.0) — Seconds to wait for a pooled DB connection before timeout.
- `DATABASE_POOL_RECYCLE_SECONDS` (1800) — Recycle pooled DB connections after this many seconds.
- `DATABASE_POOL_PRE_PING` (True) — Validate pooled DB connections before use.
- `DATABASE_ECHO` (False) — Verbose SQL logging.
- `ADMIN_API_KEY` — Required bearer/API key for privileged admin endpoints (for example `POST /api/v1/heatmap/aggregate-daily`).

Notes

- Legacy `REDIS_*` variables are still accepted as aliases for Valkey settings.
- `.env` loading is handled by Pydantic Settings with `env_file=".env"`.
- In Docker Compose, backend defaults are container-network DSNs:
  - `VALKEY_URL=valkey://valkey:6379/0`
  - `DATABASE_URL=postgresql+asyncpg://<user>:<password>@postgres:5432/<db>`
- Compose defaults do not publish Postgres/Valkey ports to the host. Use the `host-access` profile only when explicit host access is required.

## Docker Compose Host Access Profile (Optional)

Use this profile to expose DB/cache to the host for local tools:

```bash
docker compose --profile host-access up --build
```

Available env vars:

- `POSTGRES_HOST_BIND` (`127.0.0.1`) — host bind address for forwarded Postgres.
- `POSTGRES_HOST_PORT` (`5432`) — host port for forwarded Postgres.
- `VALKEY_HOST_BIND` (`127.0.0.1`) — host bind address for forwarded Valkey.
- `VALKEY_HOST_PORT` (`6379`) — host port for forwarded Valkey.

## Observability Stack (Optional)

When starting with `docker-compose.observability.yml`, Grafana admin credentials are required (no insecure fallback defaults):

- `GRAFANA_ADMIN_USER` — required, set a non-default username.
- `GRAFANA_ADMIN_PASSWORD` — required, set a strong secret.
- `PROMETHEUS_RETENTION_TIME` (`7d`) — TSDB retention duration.
- `PROMETHEUS_RETENTION_SIZE` (`5GB`) — TSDB max size.

## Frontend (Vite/React)

Place variables in `frontend/.env` (or use `frontend/.env.local` for local overrides). See `frontend/.env.example`.

- `VITE_API_BASE_URL` — Backend API base URL (e.g., http://localhost:8000).
- `VITE_ENABLE_DEBUG_LOGS` — `true`/`false` to control debug logging.
- `VITE_SENTRY_DSN` — Optional Sentry DSN for error tracking.
- `VITE_MAP_TILE_URL` — Optional map tile URL.
- `VITE_MAP_ATTRIBUTION` — Optional map attribution HTML.

## Examples

Backend `.env` (repository root):

```
VALKEY_URL=valkey://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision
TRANSIT_DEPARTURES_CACHE_TTL_SECONDS=30
TRANSIT_DEPARTURES_CACHE_STALE_TTL_SECONDS=300
CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS=2
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173
```

Frontend `.env` (frontend/.env):

```
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_DEBUG_LOGS=false
```
