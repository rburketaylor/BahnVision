# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BahnVision is a FastAPI backend service that delivers MVG (Munich transit) live data through a REST API with production-grade caching, persistence, and observability. The architecture emphasizes predictable latency via Valkey caching with single-flight locks, stale fallbacks, and circuit breaker patterns.

## Essential Commands

### Development Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Running the Service
```bash
# Local development with hot reload
uvicorn app.main:app --reload --app-dir backend

# With Docker Compose (includes Valkey)
docker compose up --build
```

### Testing
```bash
# Run all tests
pytest backend/tests

# Run specific test file
pytest backend/tests/test_mvg_endpoints.py

# Run with verbose output
pytest backend/tests -v
```

## Architecture & Code Organization

### Core Application Structure
- `backend/app/main.py` — FastAPI application factory with lifespan management (disposes SQLAlchemy engine on shutdown)
- `backend/app/api/routes.py` — registers versioned routers under `/api/v1`
- `backend/app/api/v1/endpoints/` — endpoint implementations (health, mvg)
- `backend/app/api/metrics.py` — Prometheus metrics endpoint at `/metrics`

### Service Layer Pattern
Services in `backend/app/services/` encapsulate shared infrastructure:
- `mvg_client.py` — wraps MVG API interactions with rate limit handling and latency instrumentation.
- `cache.py` — Valkey-backed cache service implementing single-flight locks, stale fallbacks, and circuit breaker behaviour.
Domain-specific orchestration currently happens inside route handlers and repository helpers; future service classes will live alongside these modules.

### Cache Architecture (Critical)
The `CacheService` (backend/app/services/cache.py:15) implements sophisticated production patterns:

**Single-flight locking**: Only one request refreshes a cache miss while others wait on the result, preventing stampedes. Uses `{key}:lock` keys with NX (set-if-not-exists) semantics.

**Stale reads with background refresh**: Cache entries have dual TTLs — a fresh TTL and longer stale TTL (`{key}:stale`). When fresh data expires but stale exists, serve stale immediately and trigger async refresh.

**Circuit breaker fallback**: On Valkey connection failures, automatically opens circuit breaker for configurable timeout (default 10s) and falls back to in-process `_fallback_store` dictionary. All writes populate both Valkey and fallback store.

**Configuration**: Tunable per-endpoint TTLs via environment variables:
- `MVG_DEPARTURES_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS`
- `MVG_STATION_SEARCH_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS`
- `MVG_ROUTE_CACHE_TTL_SECONDS` / `_STALE_TTL_SECONDS`
- `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS`, `_WAIT_SECONDS`, `_RETRY_DELAY_SECONDS`
- `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS`

### Persistence Layer
Located in `backend/app/persistence/`:
- `models.py` — SQLAlchemy 2.x async ORM models for stations, departures, routes, weather, ingestion runs
- `repositories.py` — `TransitDataRepository` provides persistence operations
- `dependencies.py` — FastAPI dependency injection for repository instances
- `core/database.py` — shared async SQLAlchemy engine with connection pooling

Database schema supports historical analysis: stores raw JSON payloads alongside normalized columns, with `departure_weather_links` for geo-temporal weather enrichment (Phase 2).

### Configuration Management
`backend/app/core/config.py` uses Pydantic settings:
- Sources environment variables with `.env` file fallback
- Supports legacy `REDIS_*` aliases for Valkey settings (backward compatibility)
- Validates types and provides defaults
- Access via cached `get_settings()` function

### HTTP Schemas
`backend/app/models/` contains Pydantic request/response schemas that define API contracts with the frontend.

## Testing Architecture

`backend/tests/conftest.py` provides test fixtures:
- `FakeValkey` — in-memory cache replacement with TTL support and failure simulation (`should_fail` flag)
- `FakeMVGClient` — test double tracking call counts and configurable failure modes
- `api_client` fixture — TestClient with dependency overrides for isolated endpoint testing

Mock failures by setting flags on fixtures (e.g., `fake_valkey.should_fail = True` or `fake_mvg_client.fail_departures = True`).

## Observability & Metrics

Prometheus metrics follow `bahnvision_*` naming convention:
- `bahnvision_cache_events_total{event="hit|miss|stale|refresh"}`
- `bahnvision_cache_refresh_duration_seconds` (histogram with resource/status labels)
- `bahnvision_mvg_requests_total{endpoint, status}` and `bahnvision_mvg_request_duration_seconds`
- `bahnvision_api_request_duration_seconds{route}` (ASGI middleware)
- `bahnvision_api_exceptions_total{route, type}`

Structured JSON logging with `request_id`, `station_id`, `cache_status`, `mvg_status`, `duration_ms`.

Target SLAs (per `backend/docs/architecture/tech-spec.md`):
- Cache hit ratio >70% (warning <70%, critical <55%)
- MVG P95 latency <750ms
- API exception rate <5/min

## Key Design Patterns

### Dependency Injection
Services use FastAPI's dependency injection:
```python
# In endpoint
async def get_departures(
    cache_service: CacheService = Depends(get_cache_service),
    mvg_client: MVGClient = Depends(get_client),
):
    # Use services
```

Override dependencies in tests via `app.dependency_overrides` (see conftest.py:228).

### Async/Await Throughout
All I/O operations are async: MVG API calls, Valkey operations, database queries. Use `async def` and `await` consistently.

### Type Hints & Pydantic Validation
Prefer typed function signatures. API request/response validation enforced via Pydantic models in `models/` directory.

## Documentation References

- `backend/docs/architecture/tech-spec.md` — canonical backend specification with architecture diagram, data models, REST interfaces, observability requirements, and rollout plan.
- `backend/docs/product/prd.md` — product requirements.
- `backend/docs/roadmap/tasks.json` — structured task backlog.

## Environment Configuration

Default PostgreSQL 18 connection:
```
DATABASE_URL=postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision
```

PostgreSQL 18 is used for its performance improvements (up to 3× I/O performance), skip scan optimization on B-tree indexes, and page checksums enabled by default.

For Docker Compose deployments, Valkey URL is automatically set to `valkey://valkey:6379/0`.

## Dependency Management

When adding new Python packages to `backend/requirements.txt`:

1. **Always check for the latest version** before adding dependencies:
   ```bash
   # Check latest version on PyPI
   pip index versions <package-name>

   # Alternative: search PyPI
   curl -s https://pypi.org/pypi/<package-name>/json | grep -oP '"version":\s*"\K[^"]+'
   ```

2. **Never guess package versions** based on knowledge cutoff — always verify the current latest version

3. **Pin exact versions** (use `==` not `>=`) for reproducible builds

4. **Example workflow**:
   ```bash
   # Check latest alembic version
   pip index versions alembic

   # Add to requirements.txt with exact version
   echo "alembic==1.17.0" >> backend/requirements.txt

   # Install the package
   pip install -r backend/requirements.txt
   ```

## Common Gotchas

1. **Cache service always writes to both Valkey and fallback store** — this ensures circuit breaker resilience
2. **Single-flight lock timeout is 5s by default** — long-running refreshes may need tuning via `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS`
3. **Stale cache keys use `:stale` suffix** — manual cache inspection needs to check both `{key}` and `{key}:stale`
4. **SQLAlchemy engine disposal** — handled in main.py:14 lifespan context; tests must not interfere with this lifecycle
5. **Transport type enum casing** — MVG API uses uppercase (`UBAHN`, `SBAHN`) but endpoint accepts case-insensitive input
6. **Commit messages** — follow Conventional Commits format seen in git history; include body for multi-file context
