# BahnVision Frontend Implementation Summary

Phase 0 (Oct–Nov 2025) laid the groundwork for the BahnVision web client. Everything below is in place today and ready for Phase 1 feature work.

## Foundation Delivered
- **Project bootstrap**: React 19 + TypeScript + Vite 7 with hot reload, strict TS configuration, modern ES2022 target.
- **Styling**: Tailwind CSS 4 with MVG colour palette, Headless UI primitives, responsive-first layout scaffolding.
- **Routing & shell**: React Router 7 with `Departures`, `Planner`, `Insights` stubs and shared layout/navigation.
- **API layer**: Typed fetch wrapper (`src/services/api.ts`), full endpoint typings (`src/types/api.ts`), TanStack Query hooks for health, station search, departures, and route planning.
- **State & utilities**: Query client configuration, Zustand dependency ready for UI state, utilities for timezones and transport metadata, feature-flagged debug logging.

## Tooling & Quality
- **Testing stack**: Vitest + React Testing Library, Playwright for end-to-end flows, MSW for API mocks, jsdom setup file.
- **Linting & formatting**: ESLint 9 with React/TypeScript rules and Prettier 3 integration, strict CI scripts in `package.json`.
- **Build & deploy**: Multi-stage Dockerfile (Nginx runtime), `docker-compose.yml` wiring the backend, SPA-friendly `nginx.conf`, `.dockerignore`.
- **Documentation**: Developer quick start in `frontend/README.md`, deep dives across `frontend/docs/`, and this summary for handed-off work.

## Project Layout
```
frontend/
├── src/
│   ├── components/      # Shared UI primitives (Layout, navigation)
│   ├── hooks/           # useHealth, useDepartures, useStationSearch, useRoutePlanner
│   ├── lib/             # query-client.ts, config.ts
│   ├── pages/           # DeparturesPage, PlannerPage, InsightsPage stubs
│   ├── services/        # api.ts (typed client)
│   ├── tests/           # mocks/, unit/, e2e/ plus setup.ts
│   ├── types/           # api.ts (backend contract)
│   └── utils/           # time.ts, transport.ts
├── public/              # Static assets
├── Dockerfile / nginx.conf
├── package.json / package-lock.json
├── tailwind.config.ts / postcss.config.js
├── tsconfig*.json / vite.config.ts / vitest.config.ts
└── DEV_README.md
```

## Day-To-Day Commands
```bash
# Local development
npm install
npm run dev   # http://localhost:5173

# Quality gates
npm test -- --run
npm run lint
npm run test:e2e   # requires dev server
npm run build
```

See `frontend/docs/roadmap/delivery-plan.md` for the up-to-date delivery roadmap and feature checklists.
