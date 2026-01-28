# External Integrations

**Analysis Date:** 2026-01-27

## APIs & External Services

**GTFS Data Sources:**

- GTFS Schedule feeds - Static transit data from German operators

  - SDK: gtfs-kit 12.0.2
  - Import: Automated scheduling via APScheduler
  - Storage: Local filesystem (gtfs_data Docker volume)

- GTFS-RT (Real-time) - Live transit updates
  - SDK: gtfs-realtime-bindings 2.0.0
  - Processing: Background harvester with PostgreSQL persistence
  - Protobuf: Native protocol buffers support
  - Polling: Configurable intervals (external source dependent)

**Data Processing:**

- HTTPX 0.28.1 - Async HTTP client for external API calls
  - Used for fetching GTFS-RT data from operator sources
  - Timeout configuration per endpoint
  - Instrumented for OpenTelemetry tracing

## Data Storage

**Databases:**

- PostgreSQL 18-alpine - Primary application database
  - Connection: `DATABASE_URL` environment variable
  - ORM: SQLAlchemy 2.0.45 with asyncpg driver
  - Schema: Alembic migrations, transit GTFS models
  - Data: Station data, schedule data, statistics, aggregated metrics

**File Storage:**

- Local filesystem - GTFS schedule data persistence
  - Path: `/data/gtfs` (Docker volume)
  - Format: Standard GTFS feed files (ZIP/extracted)
  - Management: Automated import, cleanup, and versioning

**Caching:**

- Valkey 6.1.1 - In-memory cache (Redis fork)
  - Connection: `VALKEY_URL` environment variable
  - Client: Custom Python service wrapper
  - TTLs: Configurable per endpoint (departures: 30s, station list: 24h)
  - Features: Single-flight locks, stale read support
  - Fallback: Redis compatibility layer

## Authentication & Identity

**Auth Provider:**

- Custom implementation - No third-party authentication
  - Implementation: JWT/OAuth2 planning (not implemented)
  - Current state: Public API endpoints with optional API key support

## Monitoring & Observability

**Error Tracking:**

- Open-source ready - Sentry integration planned
  - Current: Custom error handling with structured logging
  - HTTP status codes: Consistent API error responses

**Metrics:**

- Prometheus - Built-in metrics collection
  - Endpoint: `/metrics` (plain text)
  - Metrics: Request rates, cache status, GTFS processing stats
  - Client: prometheus-client 0.24.1

**Logging:**

- Structured logging with Python logging
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Levels: INFO for application, WARNING for SQLAlchemy
  - Headers: Request correlation via X-Request-Id

**Distributed Tracing:**

- OpenTelemetry - Full observability stack
  - Export: OTLP protocol (Jaeger/compatible)
  - Instrumentation: FastAPI, HTTPX, SQL queries
  - Propagation: B3 headers
  - Configuration: Environment-based enablement

## CI/CD & Deployment

**Hosting:**

- Docker Compose - Local development and staging
  - Services: frontend, backend, postgres, valkey, daily-aggregation
  - Build: Multi-stage Dockerfiles with buildkit
  - Volumes: Persistent data for GTFS and database

**CI Pipeline:**

- Pre-commit hooks - Quality gates
  - Backend: pytest, black, ruff, mypi
  - Frontend: vitest, eslint, prettier
  - Security: detect-secrets for secret detection

## Environment Configuration

**Required env vars:**

- `DATABASE_URL` - PostgreSQL connection string
- `VALKEY_URL` - Valkey/Redis connection string
- `CORS_ALLOW_ORIGINS` - Frontend origin list (JSON array)
- `VITE_API_BASE_URL` - Frontend API endpoint

**Optional env vars:**

- `OTEL_ENABLED` - Enable OpenTelemetry (default: false)
- `OTEL_EXPORTER_OTLP_ENDPOINT` - Tracing endpoint
- `GTFS_RT_HARVESTING_ENABLED` - Enable real-time processing
- `HEATMAP_CACHE_WARMUP_ENABLED` - Pre-warm cache on startup

## Webhooks & Callbacks

**Incoming:**

- None detected - GTFS-RT polling from external sources

**Outgoing:**

- Scheduled endpoints - Internal triggers
  - Daily aggregation cron job via HTTP POST
  - Cache warming requests on startup
  - Health check endpoints for monitoring

---

_Integration audit: 2026-01-27_
