# Runtime Configuration

Centralized reference for environment variables and `.env` usage across the repository.

## File Locations

- Backend `.env`: place at the repository root when running locally (matches `backend/app/core/config.py` which loads `.env` from the current working directory).
- Frontend `.env`: place at `frontend/.env` (Vite reads variables prefixed with `VITE_`).
- Docker Compose: variables are set inline in `docker-compose.yml`. Override via environment or edit the compose file.

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
- `DATABASE_POOL_SIZE` (5) — SQLAlchemy pool size.
- `DATABASE_MAX_OVERFLOW` (5) — SQLAlchemy max overflow.
- `DATABASE_ECHO` (False) — Verbose SQL logging.

Notes

- Legacy `REDIS_*` variables are still accepted as aliases for Valkey settings.
- `.env` loading is handled by Pydantic Settings with `env_file=".env"`.

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
