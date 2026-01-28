# Technology Stack

**Analysis Date:** 2026-01-27

## Languages

**Primary:**

- Python 3.10+ - Backend API, data processing, and GTFS handling
- TypeScript 5.9.3 - Frontend React components and services

**Secondary:**

- Docker - Container orchestration and deployment
- Shell scripting - Build and deployment automation

## Runtime

**Environment:**

- Python 3.10+ (FastAPI runtime)
- Node.js 20+ (Vite development server)
- Docker containers for production

**Package Manager:**

- Python: pip (with uv recommendation for setup)
- Node.js: npm 10.x
- Docker Compose for service orchestration
- Lockfiles: requirements.txt (backend), package-lock.json (frontend)

## Frameworks

**Core:**

- FastAPI 0.128.0 - Python async web framework for REST API
- React 19.2.3 - UI framework with hooks and modern features
- Vite 7.3.1 - Build tool and development server for frontend

**Testing:**

- pytest 9.0.2 - Python test framework
- vitest 4.0.17 - JavaScript testing framework
- Playwright 1.57.0 - End-to-end testing
- Mutmut 3.0.0 - Mutation testing (Python)

**Build/Dev:**

- Black 26.1.0 - Python code formatter
- Ruff 0.14.13 - Python linter and formatter
- Mypy 1.19.1 - TypeScript type checking
- Prettier 3.8.0 - Code formatting
- ESLint 9.39.2 - JavaScript linting
- Stryker 9.4.0 - Mutation testing (JavaScript)

## Key Dependencies

**Critical:**

- Valkey 6.1.1 - In-memory cache (Redis fork)
- SQLAlchemy 2.0.45 - Database ORM
- PostgreSQL 18-alpine - Primary database
- HTTPX 0.28.1 - Async HTTP client
- Pydantic 2.12.0 - Data validation and serialization

**Infrastructure:**

- Prometheus-client 0.24.1 - Metrics collection
- OpenTelemetry - Distributed tracing (opentelemetry-api 1.39.1, opentelemetry-sdk 1.39.1)
- Alembic 1.18.1 - Database migrations

**Data Processing:**

- GTFS-kit 12.0.2 - GTFS schedule data processing
- GTFS-realtime-bindings 2.0.0 - Real-time transit protocol
- Polars 1.36.1 - DataFrame library for fast data processing
- APScheduler 3.11.2 - Job scheduling

## Configuration

**Environment:**

- Configuration via `.env` file with pydantic-settings
- Environment variables for all sensitive data (database, cache, API keys)
- Support for Docker Compose defaults

**Build:**

- pyproject.toml for Python packaging
- package.json for Node.js dependencies
- Dockerfiles in backend/ and frontend/ directories
- Vite configuration for frontend builds

## Platform Requirements

**Development:**

- Python 3.10+ with virtual environment
- Node.js 20+ (recommended via setup script)
- Docker Compose (for full stack simulation)
- direnv (optional environment loading)

**Production:**

- Linux containers (Docker)
- PostgreSQL database
- Valkey/Redis for caching
- Nginx (frontend container)
- Cron scheduler (daily aggregation)

---

_Stack analysis: 2026-01-27_
