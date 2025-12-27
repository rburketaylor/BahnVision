# BahnVision Frontend

React + TypeScript frontend for the BahnVision German transit live data dashboard.

## Quick Start

### Docker Compose (full stack)

- From repository root: `docker compose up --build`
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

### Prerequisites

- Node.js 24+ and npm 11+
- Backend API running at `http://localhost:8000` (see [../backend/README.md](../backend/README.md))

### Development Setup

```bash
# Install dependencies
npm install

# Start development server with hot reload
npm run dev

# Application will be available at http://localhost:5173
```

### Environment Configuration

Create a `.env` file (see `.env.example`):

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_ENABLE_DEBUG_LOGS=false

See `docs/runtime-configuration.md` for cross-project configuration details.
```

## Available Scripts

### Development

- `npm run dev` — Start development server with hot reload (port 5173)
- `npm run build` — Build for production (output to `dist/`)
- `npm run preview` — Preview production build locally
- `npm run type-check` — Run TypeScript type checking

### Code Quality

- `npm run lint` — Run ESLint and Prettier checks
- `npm run lint:fix` — Auto-fix linting and formatting issues

### Testing

- `npm test` — Run unit tests with Vitest
- `npm run test:ui` — Open Vitest UI for interactive testing
- `npm run test:e2e` — Run Playwright end-to-end tests
- `npm run test:e2e:ui` — Open Playwright UI for debugging E2E tests

## Tech Stack

- **Framework:** React 19 with TypeScript
- **Build Tool:** Vite 7
- **Routing:** React Router 7
- **State Management:** TanStack Query 5 (server state) + Zustand 5 (UI state)
- **Styling:** Tailwind CSS 4 + Headless UI 2
- **Maps:** React-Leaflet 5 + Leaflet 1.9 (planned usage; components not yet live)
- **Testing:** Vitest 4 + React Testing Library + Playwright + MSW 2
- **Error Tracking:** Sentry 10 (planned; SDK not yet wired)

## Project Structure

```
src/
├── components/     # Reusable UI components
├── hooks/          # Custom React hooks (useDepartures, useStationSearch, etc.)
├── lib/            # Configuration and query client setup
├── pages/          # Page components (DeparturesPage, PlannerPage, InsightsPage)
├── services/       # API client and external service integrations
├── tests/          # Unit, integration, and E2E tests
│   ├── mocks/      # MSW handlers for API mocking
│   ├── unit/       # Unit tests
│   └── e2e/        # Playwright E2E tests
├── types/          # TypeScript type definitions
└── utils/          # Helper functions (time, transport, etc.)
```

## Docker Deployment

### Build and Run with Docker Compose

```bash
# From repository root
docker compose up --build

# Frontend available at http://localhost:3000
# Backend API at http://localhost:8000
```

### Build Standalone

```bash
docker build -t bahnvision-frontend .
docker run -p 3000:80 \
  -e VITE_API_BASE_URL=http://localhost:8000 \
  bahnvision-frontend
```

## API Integration

The frontend consumes REST endpoints from the BahnVision backend:

- `GET /api/v1/health` — System health status
- `GET /api/v1/transit/stations/search?query={query}` — Station autocomplete
- `GET /api/v1/transit/departures?station={id}` — Live departures board
- `GET /api/v1/transit/heatmap/data` — Heatmap activity data
- `GET /metrics` — Prometheus metrics (for analysts)

See [docs/archive/api-integration.md](./docs/archive/api-integration.md) for complete API documentation.

## Testing Strategy

### Unit Tests

Located in `src/tests/unit/`. Test individual functions, hooks, and components in isolation.

```bash
npm test -- api.test.ts
```

### E2E Tests

Located in `tests/e2e/`. Test complete user flows with Playwright.

```bash
npm run test:e2e
```

### Coverage Goals

- ≥80% statement coverage
- 100% error branch coverage
- ≥75% overall coverage

See [docs/operations/testing.md](./docs/operations/testing.md) for the complete testing strategy.

## Documentation

- **[docs/archive/implementation-summary.md](./docs/archive/implementation-summary.md)** — Complete Phase 0 implementation details
- **[docs/](./docs/)** — Organised documentation hub:
  - [archive/overview.md](./docs/archive/overview.md) — Tech stack and architectural patterns
  - [archive/api-integration.md](./docs/archive/api-integration.md) — REST API contract details
  - [archive/adr.md](./docs/archive/adr.md) — Architecture Decision Records
  - [product/ux-flows.md](./docs/product/ux-flows.md) — User journeys and UI states
  - [operations/testing.md](./docs/operations/testing.md) — Testing strategy and tools
  - [operations/observability.md](./docs/operations/observability.md) — Telemetry and error tracking
  - [roadmap/roadmap.md](./docs/roadmap/roadmap.md) — Phase plan and timeline
  - [roadmap/delivery-plan.md](./docs/roadmap/delivery-plan.md) — Detailed workstreams and checklists
  - [roadmap/unified-implementation-plan.md](./docs/roadmap/unified-implementation-plan.md) — Sequential, automation-friendly delivery steps
  - Backend docs hub: `backend/docs/README.md`
  - Backend technical spec: `docs/tech-spec.md`

## Contributing

Follow Conventional Commits format for commit messages:

```
feat: add station search autocomplete
fix: correct timezone conversion for departures
docs: update API integration guide
test: add E2E test for route planning
```

Run linting and tests before committing:

```bash
npm run lint:fix
npm test -- --run
```

## Troubleshooting

### Build Failures

If you encounter TypeScript errors during build:

```bash
# Clear TypeScript cache
rm -rf node_modules/.tmp

# Rebuild
npm run build
```

### Test Failures

If tests fail to run:

```bash
# Ensure jsdom is installed
npm install --save-dev jsdom

# Clear test cache
npx vitest --run --clearCache
```

### Port Already in Use

If port 5173 is already in use:

```bash
# Kill the process using port 5173
lsof -ti:5173 | xargs kill -9

# Or specify a different port
npm run dev -- --port 5174
```
