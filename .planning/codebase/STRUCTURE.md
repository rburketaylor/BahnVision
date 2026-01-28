# Codebase Structure

**Analysis Date:** 2026-01-27

## Directory Layout

```
BahnVision/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/             # API endpoints and shared utilities
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/ # Route implementations
│   │   │   │   └── shared/   # Shared utilities (rate limiting, etc.)
│   │   ├── core/            # Core application infrastructure
│   │   ├── jobs/            # Background processing jobs
│   │   ├── models/          # Pydantic models and data schemas
│   │   ├── persistence/     # Database repositories and models
│   │   └── services/        # Business logic services
│   ├── alembic/            # Database migrations
│   ├── tests/              # Backend tests
│   └── docs/               # Backend documentation
├── frontend/               # React TypeScript frontend
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── contexts/       # React contexts (theming, etc.)
│   │   ├── hooks/          # Custom React hooks
│   │   ├── lib/            # Utilities and configurations
│   │   ├── pages/          # Page components
│   │   ├── services/       # API client services
│   │   ├── tests/          # Frontend unit/integration tests
│   │   ├── types/          # TypeScript type definitions
│   │   └── utils/          # Utility functions
│   ├── tests/              # E2E tests (Playwright)
│   └── docs/               # Frontend documentation
├── docs/                   # Project documentation
├── scripts/                # Development and build scripts
├── .planning/             # GSD planning documents
└── docker-compose.yml      # Development environment setup
```

## Directory Purposes

**Backend (`backend/`):**

- Purpose: Python FastAPI backend serving transit data API
- Contains: API routes, services, database models, background jobs
- Key files: `backend/app/main.py` (entry point)

**Frontend (`frontend/`):**

- Purpose: React application for transit data visualization
- Contains: UI components, pages, API clients, tests
- Key files: `frontend/src/main.tsx` (entry point)

**API Layer (`backend/app/api/`):**

- Purpose: HTTP endpoint definitions and shared utilities
- Contains: FastAPI routers, middleware, rate limiting
- Key files: `backend/app/api/v1/routes.py`

**Services (`backend/app/services/`):**

- Purpose: Business logic implementation
- Contains: GTFS processing, caching, data aggregation
- Key files: `cache.py`, `gtfs_schedule.py`, `heatmap_service.py`

**Persistence (`backend/app/persistence/`):**

- Purpose: Data access layer
- Contains: Repository pattern implementations, database models
- Key files: SQLAlchemy models and repository classes

**Models (`backend/app/models/`):**

- Purpose: Pydantic schemas for API validation
- Contains: Request/response models, data transfer objects
- Key files: `gtfs.py`, `transit.py`, `heatmap.py`

**Jobs (`backend/app/jobs/`):**

- Purpose: Background processing tasks
- Contains: GTFS scheduling, real-time harvesting, cache warming
- Key files: `gtfs_scheduler.py`, `rt_processor.py`

**Frontend Components (`frontend/src/components/`):**

- Purpose: Reusable UI components
- Contains: Map components, charts, forms, layout components
- Key files: `Layout.tsx`, map-related components

**Frontend Pages (`frontend/src/pages/`):**

- Purpose: Page-level components
- Contains: Main app pages for different features
- Key files: `MainPage.tsx`, `StationPage.tsx`, `HeatmapPage.tsx`

## Key File Locations

**Entry Points:**

- `[backend/app/main.py]`: FastAPI application factory and setup
- `[frontend/src/main.tsx]`: React app initialization with providers
- `[frontend/src/App.tsx]`: Main routing component

**Configuration:**

- `[backend/app/core/config.py]`: Application settings and environment config
- `[frontend/package.json]`: Frontend dependencies and scripts
- `[docker-compose.yml]`: Service orchestration

**Core Logic:**

- `[backend/app/services/]`: Business logic implementation
- `[frontend/src/services/]`: API client implementations
- `[frontend/src/lib/]`: Shared utilities and configurations

**Testing:**

- `[backend/tests/]`: Backend test suites (unit, integration)
- `[frontend/src/tests/]`: Frontend unit/integration tests
- `[frontend/tests/]`: E2E tests with Playwright

## Naming Conventions

**Files:**

- Python: `snake_case.py` (e.g., `gtfs_schedule.py`)
- TypeScript: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Tests: `*.test.ts` or `*.test.tsx` for frontend, `*_test.py` for backend

**Directories:**

- Python: `snake_case/` (e.g., `gtfs_schedule/`)
- TypeScript: `PascalCase/` (e.g., `HeatmapControls/`)
- Tests: `tests/` at root of each project

**API Endpoints:**

- RESTful conventions with version prefix `/api/v1/`
- Resource-based URLs (e.g., `/transit/stations`, `/heatmap/data`)
- Consistent response structures with metadata

## Where to Add New Code

**New Backend API Endpoint:**

- Primary code: `backend/app/api/v1/endpoints/[feature]/.py`
- Tests: `backend/tests/api/v1/[feature]/.py`
- Models: `backend/app/models/[feature].py`

**New Frontend Feature:**

- Components: `frontend/src/components/[Feature]/`
- Pages: `frontend/src/pages/[Feature]Page.tsx`
- Services: `frontend/src/services/[feature].ts`
- Tests: `frontend/src/components/[Feature]/[Feature].test.tsx`

**New Backend Service:**

- Implementation: `backend/app/services/[service_name].py`
- Tests: `backend/tests/services/[service_name]_test.py`
- Models: `backend/app/models/[related_model].py`

**New Database Model:**

- SQLAlchemy: `backend/app/persistence/models/[model].py`
- Pydantic: `backend/app/models/[model].py`
- Migration: `backend/alembic/versions/`

## Special Directories

**`.planning/`:**

- Purpose: GSD planning and architecture documents
- Generated: Yes (created by GSD tools)
- Committed: Yes (part of project documentation)

**`backend/mutants/`:**

- Purpose: Mutation testing backup directory
- Generated: Yes (by Stryker)
- Committed: Yes (for CI/CD consistency)

**`frontend/node_modules/`:**

- Purpose: Frontend dependencies
- Generated: Yes (by npm)
- Committed: No (excluded by .gitignore)

---

_Structure analysis: 2026-01-27_
