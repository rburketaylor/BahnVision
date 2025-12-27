# Frontend Roadmap

> Status: In progress. Core pages (landing, departures, planner, insights) are implemented; map overlays, richer observability, and analytics remain planned. See `docs/tech-spec.md` for backend capabilities.

## Current state vs planned state

- Current: Departures, station search, and planner flows work against the backend; no maps, limited analytics/observability, and minimal polish.
- Planned: Deliver the phases below to reach the Q1 2026 MVP with departures and route planning plus maps and analyst tooling.

## Timeline Assumptions

- Current date: 29 October 2025.
- Target MVP launch: end of Q1 2026 with core departures + route planning.
- Backend endpoints already live per `docs/tech-spec.md`; persistence enhancements slated for MS1-T2.

## Phase Breakdown

### Phase 0 – Planning & Setup (Oct–Nov 2025)

- Finalize architecture decisions (this doc set + ADR).
- Bootstrap repository: Vite + React + TypeScript, CI scaffolding, lint/test tooling.
- Integrate MSW mocks for backend endpoints; ensure developers can work offline.

### Phase 1 – MVP Core Flows (Dec 2025 – Jan 2026)

- Build station search + departures board with cache status badges.
- Implement route planner with map overlays and error handling.
- Add system health widget polling `/api/v1/health`.
- Wire TanStack Query caching and optimistic UI for refresh button.
- Deliver accessibility baseline (keyboard navigation, screen reader labels).

### Phase 2 – Insights & Operations (Feb 2026)

- Introduce analytics instrumentation + observability plumbing.
- Add metrics download helper linking to `/metrics` and interpretive UI copy for analysts.
- Surface backend latency warnings if routes/departures exceed thresholds.
- Begin QA with synthetic load using Playwright + backend fixtures.

### Phase 3 – Polish & Launch (Mar 2026)

- Visual refinements, theming, localization (English + German copy review).
- Performance optimization (code splitting, prefetch popular stations, web vitals tuning).
- Execute release readiness checklist; capture screenshots and manual QA notes.
- Prepare operator documentation and handoff runbook.

## Dependencies & Risks

- Backend spec mismatch (health endpoint payload) may require backend update or frontend workaround.
- Weather features blocked pending Phase 2 backend; keep feature flag to avoid UI debt.
- Data accuracy relies on GTFS feed availability; ensure fallback messaging is clear before public launch.

## Deliverables Per Phase

- Phase 0: repo skeleton, ADR approved.
- Phase 1: MVP feature branch, demo build deployed to staging.
- Phase 2: analytics dashboards, automated test coverage ≥75%.
- Phase 3: production release candidate, ops documentation complete.

## Post-Launch Backlog

- Weather overlay once backend `/weather` endpoints ship.
- Historical trends view using persisted departures (requires MS1-T2 backend migrations).
- Offline kiosk mode with auto-refresh restrictions for station monitors.
