# BahnVision Backend

This directory contains the Python/FastAPI backend for BahnVision. The service
uses the [`mvg`](https://github.com/mondbaron/mvg) package to fetch live data
from Münchner Verkehrsgesellschaft (MVG) and exposes it through a REST API that
the frontend can consume.

## Getting Started

1. **Create a virtual environment (recommended)**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run the API**
   ```bash
   uvicorn app.main:app --reload --app-dir backend/app
   ```

   The service will listen on `http://127.0.0.1:8000` by default. Open
   `http://127.0.0.1:8000/docs` to explore the interactive Swagger UI.

## Key Endpoints

- `GET /api/v1/health` – readiness probe.
- `GET /api/v1/mvg/departures` – upcoming departures for a station. Parameters:
  - `station` (required): station name or global MVG station id (e.g.
    `de:09162:6` for München Hauptbahnhof).
  - `limit` (optional): number of departures to retrieve (default 10, max 40).
  - `offset` (optional): minutes to offset departures (e.g. walking time).
  - `transport_type` (optional, repeatable): filter by transport mode, accepts
    values like `UBAHN`, `SBAHN`, `tram`, `bus`.
- `GET /api/v1/mvg/stations/search` – station autocomplete helper backed by MVG
  search. Parameters:
  - `query` (required): station name fragment or MVG address string.
  - `limit` (optional): number of suggestions to return (default 8, max 20).
- `GET /api/v1/mvg/routes/plan` – multi-leg journey planning between two
  stations. Parameters:
  - `origin` (required): origin station query (name or global id).
  - `destination` (required): destination station query (name or global id).
  - `departure_time` (optional): desired departure timestamp (UTC).
  - `arrival_time` (optional): desired arrival deadline (UTC).
  - `transport_type` (optional, repeatable): limit journey legs to specific MVG
    transport products.
- `GET /metrics` – Prometheus metrics describing MVG request latency, cache hit
  ratios, and background refresh behaviour.

Example request:
```bash
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=de:09162:6&transport_type=UBAHN"
```

## Notes

- The MVG API enforces rate limits; responses are cached in Valkey to keep load
  manageable.
- The `mvg` client offers additional endpoints (`nearby`, `lines`, etc.) that
  can be wrapped in similar fashion when needed.
- Prometheus metrics are exposed at `/metrics` (default registry) so Grafana or
  other tooling can scrape cache/MVG counters without extra plumbing.

## Caching

The backend caches MVG responses in Valkey (Redis-compatible). Configure the cache with environment
variables:

- `VALKEY_URL` (default `valkey://localhost:6379/0`)
- `VALKEY_CACHE_TTL_SECONDS` (default `30` seconds)
- `VALKEY_CACHE_TTL_NOT_FOUND_SECONDS` (default `15` seconds)
- `MVG_DEPARTURES_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS` – tune freshness for departures cache.
- `MVG_STATION_SEARCH_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS` – tune station lookup caching.
- `MVG_ROUTE_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS` – tune route planning cache lifetime.
- `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS`,
  and `CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS` – govern single-flight locking behaviour.
- `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS` – window (seconds) to rely on in-process
  fallback storage after Valkey connectivity issues (default `10` seconds).

Legacy `REDIS_*` variables are still accepted for backwards compatibility.

For local development, start a Valkey container or run the app through
`docker compose` (see below).

### Roadmap for production-grade caching

Planned enhancements to showcase a production-ready caching layer:

- **Cache-aside pattern with per-endpoint TTLs** and deterministic keys so each
  route can tune freshness independently. (Departures and station search use
  dedicated TTL/stale TTL knobs in `Settings`.)
- **Stampede protection** via single-flight locking to ensure only one worker
  refreshes a cold key while others wait on the result. (Implemented.)
- **Soft TTL with asynchronous refresh** to keep latency low while data stays
  reasonably fresh. (Implemented via stale reads with background refresh.)
- **Circuit breaker behaviour**: if MVG goes flaky, serve stale data for a
  grace window instead of failing requests outright. (Stale fallback now in
  place; deeper circuit-breaker logic still pending.)
- **Observability hooks** capturing cache hit/miss ratios, fetch latency, lock
  contention, and Valkey error counts. (Implemented via Prometheus metrics.)
- **Graceful degradation** that automatically falls back to in-process or
  disk-backed cache if Valkey becomes unavailable.

## Testing

Run the automated suite with:

```bash
pytest backend/tests
```

## Run with Docker

1. **Build the image**
   ```bash
   docker build -f backend/Dockerfile -t bahnvision-backend .
   ```

2. **Start the container**
   ```bash
   docker run --rm -p 8000:8000 bahnvision-backend
   ```

   The API will be available on `http://127.0.0.1:8000`. Pass environment
   variables with `-e KEY=value` or mount config files as needed.

Orchestrate services together with Docker Compose:

```bash
docker compose up --build
```

This brings up the backend and a Valkey instance wired with sensible defaults.
