# Architecture

**Analysis Date:** 2026-01-27

## Pattern Overview

**Overall:** Layered microservices architecture with clean separation of concerns

**Key Characteristics:**

- Backend: FastAPI-based REST API with async processing
- Frontend: React 19 with Vite and TypeScript
- Data: PostgreSQL + Valkey caching + GTFS transit data processing
- Jobs: Background processing for GTFS real-time updates and heatmap generation
- Deployment: Docker Compose with hot reload for development

## Layers

**Presentation Layer:**

- Purpose: User interface components and page routing
- Location: `frontend/src/`
- Contains: React components, pages, services, hooks
- Depends on: API layer for data fetching
- Used by: End users via browser

**API Layer:**

- Purpose: REST API endpoints and shared utilities
- Location: `backend/app/api/`
- Contains: FastAPI routers, rate limiting, shared utilities
- Depends on: Service and persistence layers
- Used by: Presentation layer (frontend)

**Service Layer:**

- Purpose: Business logic and data processing
- Location: `backend/app/services/`
- Contains: GTFS processing, caching, daily aggregation, transit data
- Depends on: Persistence layer and external services
- Used by: API layer

**Persistence Layer:**

- Purpose: Data access and database operations
- Location: `backend/app/persistence/`
- Contains: Repository pattern implementations
- Depends on: Database connection
- Used by: Service layer

**Core Infrastructure:**

- Purpose: Application configuration, database, telemetry
- Location: `backend/app/core/`
- Contains: Settings, database setup, monitoring, telemetry
- Depends on: External services (database, cache)
- Used by: All layers

## Data Flow

**API Request Flow:**

1. HTTP request reaches FastAPI entry point (`backend/app/main.py`)
2. Request processed through middleware (CORS, rate limiting, GZip)
3. Router matches endpoint and passes to handler
4. Service layer processes business logic
5. Persistence layer handles database operations
6. Response cached if applicable
7. JSON response returned with cache headers

**GTFS Data Processing Flow:**

1. GTFS feed scheduler fetches static schedule data
2. GTFS-RT harvester processes real-time updates
3. Daily aggregation service computes statistics
4. Heatmap service processes transit patterns
5. Cache layer stores frequently accessed data
6. Background jobs persist real-time data

**State Management:**

- Frontend: React hooks + TanStack Query for server state
- Backend: Stateless services with centralized caching
- Database: PostgreSQL for persistence, Valkey for fast caching

## Key Abstractions

**Cache Service:**

- Purpose: Centralized caching with single-flight locks
- Examples: `backend/app/services/cache.py`
- Pattern: Abstract base class with Valkey and file fallback

**GTFS Service:**

- Purpose: GTFS data processing and validation
- Examples: `backend/app/services/gtfs_schedule.py`, `gtfs_realtime.py`
- Pattern: Factory pattern for different data types

**Repository Pattern:**

- Purpose: Data access abstraction
- Examples: `backend/app/persistence/`
- Pattern: Interface separation for different data sources

**Job Service:**

- Purpose: Background processing coordination
- Examples: `backend/app/jobs/`
- Pattern: Async context managers with lifecycle management

## Entry Points

**Backend API:**

- Location: `backend/app/main.py`
- Triggers: HTTP requests on port 8000
- Responsibilities: App initialization, middleware setup, router registration
- Lifespan: Manages startup/shutdown of background services

**Frontend App:**

- Location: `frontend/src/main.tsx`
- Triggers: Browser load
- Responsibilities: React app setup, provider configuration, root component rendering
- Route Configuration: Handles SPA routing via React Router

**Database:**

- Location: `backend/app/core/database.py`
- Triggers: Application startup
- Responsibilities: Connection pool management, session setup
- Used by: All database operations

## Error Handling

**Strategy:** Hierarchical error handling with structured responses

**Patterns:**

- FastAPI validation errors for input validation
- Custom exception classes for business logic
- Graceful degradation for cache failures
- Retry logic for external service calls

## Cross-Cutting Concerns

**Logging:** Python logging with request correlation via X-Request-ID
**Validation:** Pydantic models for request/response validation
**Authentication:** API key and bearer token support via middleware
**Monitoring:** OpenTelemetry integration with Prometheus metrics
**Caching:** Multi-layer caching with stale-read optimization

---

_Architecture analysis: 2026-01-27_
