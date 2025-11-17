# BahnVision
FastAPI backend and React frontend for Munich transit data: live MVG departures, station search, route planning, and Prometheus metrics. Designed for low-latency responses with Valkey caching and PostgreSQL persistence.

## Overview
- Backend exposes versioned REST APIs for departures, station search, routes, health, and metrics.
- Cache-first reads with single-flight locking and stale fallbacks keep responses predictable during upstream issues.
- Persistence layer currently stores the station catalog to support search and future analytics.

## Features
- FastAPI with typed Pydantic schemas and dependency injection.
- Valkey-backed cache with stampede protection and stale refresh.
- Async SQLAlchemy targeting PostgreSQL; Alembic-ready migrations.
- Prometheus metrics at `/metrics` for latency, cache events, and MVG health.
- Docker Compose for local development.
- Optional cache warmup container hydrates MVG station data during startup so the first user doesn't wait for MVG.

## Architecture Deep-Dive

### Caching Strategy

The BahnVision backend implements a sophisticated multi-layered caching system designed for high availability and predictable latency:

#### Multi-Tier Cache Architecture
1. **Primary Cache**: Valkey-backed distributed cache with configurable TTLs per endpoint
2. **Stale Cache**: Background refresh serves stale data while fresh data is fetched
3. **Circuit Breaker**: In-process fallback cache when Valkey becomes unavailable
4. **Single-Flight Locks**: Prevents cache stampedes during concurrent requests

#### Cache Behavior Patterns
- **Cache Hit**: Direct response from Valkey (typical for frequently accessed data)
- **Cache Miss + Stale**: Immediate stale response served, background refresh triggered
- **Cache Miss + Fresh**: Synchronous MVG API call, populate both primary and stale cache
- **Circuit Breaker**: In-process cache serves when Valkey is unreachable

#### Cache Key Strategy
- `{endpoint}:{query_hash}` — Primary cache key
- `{endpoint}:{query_hash}:stale` — Stale cache backup
- Automatic TTL management based on endpoint-specific settings

### Observability & Monitoring

#### Prometheus Metrics
```text
# Cache performance
bahnvision_cache_events_total{cache,event}  # hit, miss, stale_return, refresh_success
bahnvision_cache_refresh_seconds{cache}     # Refresh latency histogram

# MVG API integration
bahnvision_mvg_requests_total{endpoint,result}  # Request outcomes
bahnvision_mvg_request_seconds{endpoint}        # MVG latency histogram

# Application metrics (planned)
bahnvision_api_request_duration_seconds{route}
bahnvision_api_exceptions_total{route,type}
```

#### Response Headers
- `X-Cache-Status`: Indicates cache path (`hit`, `miss`, `stale`, `stale-refresh`)
- `X-Request-Id`: Unique identifier for request tracing

#### Performance SLAs
- **Cache Hit Ratio**: Target >70% for optimal performance
- **MVG API Latency**: P95 <750ms for external service calls
- **API Exception Rate**: <5 exceptions per minute
- **Response Time**: P95 <200ms for cached endpoints

### Error Handling & Resilience

#### Graceful Degradation
1. **MVG API Errors**: Fall back to stale cache when available
2. **Cache Failures**: Circuit breaker provides in-process cache
3. **Database Issues**: Continue serving from cache when possible
4. **Network Issues**: Configurable timeouts and retry logic

#### Error Response Format
All errors include structured responses with:
- Error codes for programmatic handling
- Human-readable messages
- Request tracing IDs
- Fallback suggestions when applicable

### Scalability Design

#### Horizontal Scaling
- Stateless application servers with shared cache (Valkey)
- Database connection pooling with overflow management
- Container-ready deployment with health checks

#### Performance Optimizations
- Async/await throughout the stack for high concurrency
- Connection pooling for both database and cache
- Intelligent cache warming strategies
- Configurable resource limits per endpoint

## Quick Start
- Docker Compose (recommended):
  1) `docker compose up --build`
     - Compose launches a short-lived `cache-warmup` container that runs `python -m app.jobs.cache_warmup` before the API starts, hydrating Valkey/Postgres with the MVG station catalog.
  2) API docs: http://127.0.0.1:8000/docs
  3) Frontend: http://127.0.0.1:3000

- Local Python environment:
  1) `python -m venv .venv && source .venv/bin/activate` (tested with Python 3.11+)
  2) `pip install -r backend/requirements.txt`
  3) Ensure Valkey and PostgreSQL are reachable (compose defaults)
  4) `uvicorn app.main:app --reload --app-dir backend` → `http://127.0.0.1:8000`

- Local frontend environment:
  1) `npm install` (requires Node.js 24+ and npm 11+)
  2) `npm run dev` → `http://127.0.0.1:5173`
  3) Set `VITE_API_BASE_URL=http://127.0.0.1:8000` in `.env` for local backend

Frontend detailed setup: see `frontend/README.md`.

## Configuration

### Backend Environment Variables
Place these in `.env` at the repository root (copy from `.env.example`):

#### Core Infrastructure
- `VALKEY_URL` — cache connection string (default `valkey://localhost:6379/0`)
- `DATABASE_URL` — PostgreSQL async DSN (default `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`)
- `DATABASE_POOL_SIZE` — connection pool size (default 5)
- `DATABASE_MAX_OVERFLOW` — overflow connections (default 5)
- `DATABASE_ECHO` — SQL logging (default false)

#### Cache Configuration
- `VALKEY_CACHE_TTL_SECONDS` — default cache TTL (default 30)
- `VALKEY_CACHE_TTL_NOT_FOUND_SECONDS` — cache TTL for not found responses (default 15)

#### Per-Endpoint TTLs
- `MVG_DEPARTURES_CACHE_TTL_SECONDS` — departures cache TTL (default 30)
- `MVG_DEPARTURES_CACHE_STALE_TTL_SECONDS` — stale departures TTL (default 300)
- `MVG_STATION_SEARCH_CACHE_TTL_SECONDS` — station search TTL (default 60)
- `MVG_STATION_SEARCH_CACHE_STALE_TTL_SECONDS` — stale station search TTL (default 600)
- `MVG_STATION_LIST_CACHE_TTL_SECONDS` — station list TTL (default 86400)
- `MVG_STATION_LIST_CACHE_STALE_TTL_SECONDS` — stale station list TTL (default 172800)
- `MVG_ROUTE_CACHE_TTL_SECONDS` — route planning TTL (default 120)
- `MVG_ROUTE_CACHE_STALE_TTL_SECONDS` — stale route planning TTL (default 900)

#### Advanced Cache Features
- `CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS` — lock TTL (default 5)
- `CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS` — lock wait time (default 5.0)
- `CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS` — retry delay (default 0.05)
- `CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS` — circuit breaker timeout (default 2.0)

#### Cache Warmup
- `CACHE_WARMUP_DEPARTURE_STATIONS` — comma-separated station queries for warmup
- `CACHE_WARMUP_DEPARTURE_LIMIT` — departures per station (default 10)
- `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES` — future offset (default 0)

#### CORS Configuration
- `CORS_ALLOW_ORIGINS` — JSON array of allowed origins (default `["http://localhost:3000","http://localhost:5173"]`)
- `CORS_ALLOW_ORIGIN_REGEX` — regex pattern for origins (optional)

### Frontend Environment Variables
Place these in `frontend/.env` (Vite only reads variables prefixed with `VITE_`):

#### Required
- `VITE_API_BASE_URL` — Backend API base URL (default `http://localhost:8000`)

#### Optional
- `VITE_ENABLE_DEBUG_LOGS` — Enable debug logging (default `false`)
- `VITE_SENTRY_DSN` — Sentry error tracking DSN
- `VITE_MAP_TILE_URL` — Custom map tile URL (default OpenStreetMap)
- `VITE_MAP_ATTRIBUTION` — Custom map attribution HTML

### Development vs Production
- **Development**: Use `http://127.0.0.1:8000` for `VITE_API_BASE_URL`
- **Production**: Use actual backend URL (e.g., `https://api.bahnvision.app`)
- **Docker Compose**: Backend variables from root `.env`, frontend variables passed via build args

See `docs/runtime-configuration.md` for detailed examples and use cases.

## Cache Warmup
- Run manually via `cd backend && python -m app.jobs.cache_warmup` to hydrate the station catalog (and optional departures caches) without starting the API.
- Docker Compose executes the same command through the `cache-warmup` service before the backend container starts, so the very first search reuses cached MVG data.
- Configure departure hydration with `CACHE_WARMUP_DEPARTURE_STATIONS`, `CACHE_WARMUP_DEPARTURE_LIMIT`, and `CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES`. Leave the station list empty to skip departures warmup.

## API Documentation

### REST Endpoints

#### Health & Monitoring
- `GET /api/v1/health` — Application readiness probe
  - **Response**: `{"status": "ok"}`
- `GET /metrics` — Prometheus metrics (cache hit ratios, request latencies, MVG health)

#### Station Information
- `GET /api/v1/mvg/stations/search` — Station autocomplete and search
  - **Parameters**:
    - `query` (required): Search query string
    - `limit` (optional): Maximum results (default 40, max 50)
  - **Example**: `GET /api/v1/mvg/stations/search?query=marien&limit=5`
  - **Response**: Array of station objects with id, name, latitude, longitude
- `GET /api/v1/mvg/stations/list` — Get all MVG stations (cached)
  - **Response**: Array of all station objects

#### Live Departures
- `GET /api/v1/mvg/departures` — Real-time departures for a station
  - **Parameters**:
    - `station` (required): Station ID or name (case-insensitive)
    - `transport_type` (optional): Filter by transport type (`UBAHN`, `TRAM`, `BUS`, `SBAHN`)
    - `limit` (optional): Maximum departures (default 10, max 40)
    - `offset` (optional): Future offset in minutes (default 0, max 240) or derived from `from`
    - `from` (optional): UTC timestamp anchor; mutually exclusive with `offset`
  - **Example**: `GET /api/v1/mvg/departures?station=marienplatz&transport_type=UBAHN&limit=10`
  - **Response**: Array of departure objects with line, destination, minutes, platform, etc.
  - **Headers**: `X-Cache-Status` indicates cache path (`hit`, `miss`, `stale`, `stale-refresh`)

#### Route Planning
- `GET /api/v1/mvg/routes/plan` — Multi-modal route planning
  - **Parameters**:
    - `origin` (required): Origin station ID or name
    - `destination` (required): Destination station ID or name
    - `departure_time` (optional): Departure time (ISO 8601, default now)
    - `arrival_time` (optional): Arrival deadline (ISO 8601, mutually exclusive with departure_time)
    - `transport_type` (optional): One or more transport type filters
  - **Example**: `GET /api/v1/mvg/routes/plan?origin=marienplatz&destination=hauptbahnhof`
  - **Response**: Route objects with legs, duration, transfers, and intermediate stops

### Usage Examples

```bash
# Station search
curl "http://127.0.0.1:8000/api/v1/mvg/stations/search?query=hauptbahnhof"

# U-Bahn departures from Marienplatz
curl "http://127.0.0.1:8000/api/v1/mvg/departures?station=marienplatz&transport_type=UBAHN"

# Route planning with all transport types
curl "http://127.0.0.1:8000/api/v1/mvg/routes/plan?origin=sendlinger_tor&destination=olympiazentrum"

# Check application health
curl "http://127.0.0.1:8000/api/v1/health"

# View Prometheus metrics
curl "http://127.0.0.1:8000/metrics"
```

### Response Format

Endpoints return bare JSON models defined in `app/models/mvg.py` and raise FastAPI’s default error responses on validation or upstream failures. Cacheable endpoints add `X-Cache-Status` headers; request IDs are surfaced via `X-Request-Id`.

### Auto-Documentation
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/openapi.json`

## Testing

### Backend Testing
- **Framework**: pytest with async support
- **Location**: `backend/tests/`
- **Coverage Goals**: ≥80% statement coverage, ≥75% overall coverage
- **Test Types**:
  - Unit tests for services, repositories, and utilities
  - Integration tests for API endpoints with TestClient
  - Cache behavior tests with in-memory doubles (FakeValkey, FakeMVGClient)
  - Metrics and observability tests

```bash
# Run all backend tests
pytest backend/tests/

# Run with coverage
pytest backend/tests/ --cov=app --cov-report=html

# Run specific test suites
pytest backend/tests/test_api/
pytest backend/tests/test_cache/
pytest backend/tests/test_mvg_client/
```

### Frontend Testing
- **Frameworks**: Vitest (unit/integration), Playwright (E2E), React Testing Library
- **Mocking**: MSW (Mock Service Worker) for API mocking
- **Location**: `frontend/src/` (co-located with components) and `frontend/tests/`
- **Coverage Goals**: ≥80% statement coverage

```bash
# Run unit/integration tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e

# Run E2E tests in headed mode
npm run test:e2e:headed
```

### CI/CD Integration
- **Backend**: GitHub Actions run pytest with coverage reporting to Codecov
- **Frontend**: GitHub Actions run Vitest and Playwright tests
- **Coverage Reports**: Automatic upload to Codecov for both backend and frontend
- **Quality Gates**: Tests must pass before merge, coverage trends monitored

### Testing Strategy
1. **Backend Priority**: Focus on cache behavior, API contracts, and error handling
2. **Frontend Priority**: User interactions, loading states, and error boundaries
3. **Integration**: Test full request/response cycles using MSW mocks
4. **Performance**: Monitor cache hit ratios and response times in test scenarios
5. **Regression**: Comprehensive test coverage for critical paths (station search, departures, route planning)

## Project Structure

### Backend
- `backend/app` — FastAPI application
  - `main.py` — app factory with lifespan management and router registration
  - `api/` — versioned routes, metrics exporter, and HTTP handlers
  - `services/` — stateless domain services (cache, MVG client, business logic)
  - `models/` — Pydantic request/response schemas and validation
  - `persistence/` — async SQLAlchemy models, repositories, and dependencies
  - `core/` — configuration, shared database engine, and utilities
  - `jobs/` — standalone scripts (cache warmup, data migration)
- `backend/tests` — comprehensive pytest suites mirroring `app/` structure
  - `test_api/` — API endpoint tests with TestClient
  - `test_services/` — service layer tests with fakes and mocks
  - `test_persistence/` — repository and model tests
  - `conftest.py` — shared fixtures and test configuration
- `backend/docs` — backend-specific documentation
  - `archive/` — archived specifications and historical documents

### Frontend
- `frontend/` — React 19 + TypeScript application
  - `src/components/` — reusable UI components
  - `src/pages/` — route-level page components
  - `src/hooks/` — custom React hooks (TanStack Query, etc.)
  - `src/services/` — API client and external service integrations
  - `src/types/` — TypeScript type definitions
  - `src/utils/` — utility functions and helpers
  - `src/tests/` — unit/integration tests co-located with source
  - `tests/e2e/` — Playwright end-to-end test suites

### Documentation
- `docs/` — project-wide documentation hub
  - `README.md` — documentation index and guide
  - `architecture/` — system design, patterns, and decisions
  - `product/` — feature specifications, user stories, and requirements
  - `operations/` — deployment, monitoring, and maintenance guides
  - `roadmap/` — planned features and development milestones
  - `testing/` — testing strategies, coverage goals, and CI/CD integration
  - `devops/` — infrastructure, CI/CD pipelines, and automation

### Development & CI/CD
- `.github/workflows/` — GitHub Actions pipelines (`ci.yml`, `test-migrations.yml`)
- `.vscode/` — VS Code workspace settings and launch configurations

### Infrastructure
- `docker-compose.yml` — local development stack (API + Valkey + PostgreSQL + Frontend)
- `.env.example` — environment configuration template
- `requirements.txt` — Python dependencies (backend)
- `package.json` — Node.js dependencies and scripts (frontend)

## Development Workflow

### Local Development
```bash
# Backend development server
uvicorn app.main:app --reload --app-dir backend

# Frontend development server
npm run dev

# Full stack with Docker Compose
docker compose up --build
```

### Code Quality Tools

#### Backend
```bash
# Linting and formatting
ruff check backend/app backend/tests
ruff format backend/app backend/tests

# Type checking
mypy backend/app

# Security scanning
bandit -r backend/app

# Dependency security
pip-audit
```

#### Frontend
```bash
# Linting and formatting
npm run lint
npm run lint:fix
npm run format

# Type checking
npm run type-check

# Security scanning
npm audit
```

### Testing Commands
```bash
# Backend
pytest backend/tests/                    # All tests
pytest backend/tests/ --cov=app         # With coverage
pytest backend/tests/ -x                # Stop on first failure
pytest backend/tests/ -k "test_cache"   # Run specific tests

# Frontend
npm test                                # Watch mode
npm run test:coverage                   # With coverage
npm run test:e2e                        # End-to-end tests
```

### Pre-commit Setup
The project uses pre-commit hooks for code quality. Install with:
```bash
pre-commit install
```

Pre-commit hooks run:
- Backend: ruff (linting + formatting), mypy (type checking)
- Frontend: ESLint, Prettier, TypeScript checks
- General: trailing whitespace, end-of-file fixes

### Environment Setup
1. **Copy environment template**: `cp .env.example .env`
2. **Configure local URLs**:
   - Backend: `DATABASE_URL`, `VALKEY_URL`
   - Frontend: `VITE_API_BASE_URL=http://127.0.0.1:8000`
3. **Install dependencies**: Backend via `pip install -r requirements.txt`, Frontend via `npm install`
4. **Run database migrations** (if applicable)

### Git Workflow
- **Branch**: `develop` for integration, `main` for production
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `docs:`, etc.)
- **PRs**: Require passing tests, coverage checks, and code review
- **Release**: Create PR from `develop` to `main` with release notes

### Debugging
- **Backend logs**: Enable with `VITE_ENABLE_DEBUG_LOGS=true` or Python logging config
- **Cache debugging**: Monitor `/metrics` endpoint for cache hit ratios
- **Frontend debugging**: React DevTools, TanStack Query DevTools
- **API testing**: FastAPI auto-generated docs at `/docs` and `/redoc`

## Documentation
- Project docs hub: `docs/README.md`
- Backend docs hub: `backend/docs/README.md`
- Backend tech spec (archived): `backend/docs/archive/tech-spec.md`
- Frontend docs hub: `frontend/docs/README.md`

## Contributing
- Conventional Commits (e.g., `feat:`, `fix:`, `docs:`)
- Include a brief rationale in PRs; document non-default runtime options
