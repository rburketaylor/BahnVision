# BahnVision Frontend Delivery Plan

> Status: In progress. Core flows (station search, departures, planner, insights) are shipped; this plan tracks remaining work to polish the MVP and add observability.

## Status At A Glance
- Phase 0 foundation is complete: React 19 + TypeScript + Vite, Tailwind styling, TanStack Query hooks, typed API client, and build tooling are in the repo.
- Backend endpoints for health, station search, departures, route planning, and metrics are live and typed.
- Core UI exists for station search → departures, planner, and insights; map overlays, analytics, and richer polish are pending.
- Goal: ship the MVP (station search, departures, planner, health widget) by end of Q1 2026.

Open setup item: none — `QueryClientProvider` already wraps the app in `src/main.tsx`.

## Phase 1 – MVP Workstreams
Everything below is scoped so a single engineer or automation agent can pick up a card and deliver it independently. Flows reference deeper context across the `frontend/docs/` tree.

### 1. Station Search Experience
- **Scope**: search input, debounced API calls, keyboard/touch selection, empty/error states.
- **Key files**: `components/StationSearch*.tsx`, reuse `useStationSearch`, utilities in `utils/transport.ts`.
- **Definition of done**
  - 300 ms debounce, highlight matched text, “no stations found” message, loading indicator.
  - Selection triggers navigation or callback with chosen station.
  - Accessible focus management (arrow keys, escape, screen reader labels).
- **Tests**
  - Unit test debouncing helper (Vitest).
  - Component tests with MSW fixtures for success/404/error.
  - Keyboard navigation path in Playwright.

### 2. Departures Board
- **Scope**: departures table, filters (transport type, limit 10–40, time offset), refresh controls, cache badge.
- **Key files**: `components/DeparturesBoard*.tsx`, `hooks/useDepartures`, `utils/time.ts`.
- **Definition of done**
  - Polling every 30 s respecting manual refresh invalidation.
  - Filter state persists per session (Zustand if needed), cancelled routes visually flagged, last updated timestamp.
  - `X-Cache-Status` converted to badge (“fresh”, “stale”, “stale-refresh”).
- **Tests**
  - Query refetch logic mocked in unit tests.
  - Component tests for filters and error handling.
  - Playwright flow covering filter changes and cache badge.

### 3. Route Planner
- **Scope**: origin/destination picker (reuse station search), optional departure/arrival time, transport filters, itinerary cards, map overlay.
- **Key files**: `components/RoutePlanner*.tsx`, `hooks/useRoutePlanner`, `components/RouteMap.tsx`.
- **Definition of done**
  - Enforce “departure XOR arrival” validation, show inline error if violated.
  - Route card summary (duration, transfers) with expandable legs and walking segments.
  - Map highlights active route; recent searches kept in `localStorage`.
- **Tests**
  - Form validation unit tests.
  - Component test for 404 “no routes” state.
  - Playwright happy-path itinerary selection.
  - Leaflet map interaction smoke test (mock tiles).

### 4. System Health Widget
- **Scope**: navbar badge with poll every 60 s, optional drawer for details, offline indicator, metrics link.
- **Key files**: `components/HealthStatus*.tsx`, `hooks/useHealth`.
- **Definition of done**
  - Status colours (green/amber/red) with subtle animation, last successful fetch timestamp.
  - Graceful fallback for missing `version`/`uptime` fields (documented backend gap).
  - Link to `/metrics` page or download helper.
- **Tests**
  - Unit test polling behaviour.
  - Component tests for status transitions and offline state.

### 5. Error & Feedback Framework
- **Scope**: toast notifications, global error boundary, API error mapping, retry affordances.
- **Key files**: `components/Toast*.tsx`, `hooks/useToast.ts`, `components/ErrorBoundary.tsx`, `services/api.ts`.
- **Definition of done**
  - Toast queue capped (e.g., 3 visible), auto-dismiss, accessible `aria-live`.
  - Consistent messaging for 404/502/503/network/validation errors.
  - Retry button hooks into React Query `refetch`.
- **Tests**
  - Toast state management unit tests.
  - Component tests for mapped error messages.
  - Playwright scenario triggering global error boundary.

### 6. Loading & Skeleton States
- **Scope**: skeleton loaders and loading spinners matching final layouts.
- **Key files**: `components/Skeleton.tsx`, `components/DepartureSkeleton.tsx`, `components/RouteSkeleton.tsx`.
- **Definition of done**
  - Skeletons swap seamlessly to data without layout shift.
  - Optimistic loading where appropriate (e.g., refreshing departures retains previous data until new one arrives).
- **Tests**
  - Visual regression snapshots for skeletons.
  - Component tests ensuring loading flags render correct placeholders.

### 7. Map Enhancements
- **Scope**: map components shared by station search and route planner, marker styling, interaction polish.
- **Key files**: `components/StationMap.tsx`, `components/RouteMap.tsx`, `components/MapMarker.tsx`, config in `lib/config.ts`.
- **Definition of done**
  - Default viewport centred on Munich, zoom controls responsive.
  - Highlight selected station/leg on focus.
  - Mobile layout keeps map usable (min height, gestures).
- **Tests**
  - Unit tests for marker factory logic.
  - Playwright smoke test to ensure map renders without JS errors (mock tiles).

## Agent Playbook
1. **Prep**: run `npm install`, `npm run dev`, and confirm backend reachable at `http://127.0.0.1:8000` (or set `VITE_API_BASE_URL`). Verify `QueryClientProvider` exists in `src/main.tsx`.
2. **Select a workstream**: pick one section above; treat each bullet as a checklist item to close.
3. **Implement**: follow the referenced hooks and utilities; keep stateless components where possible and hoist shared UI to `components/`.
4. **Test**: run `npm test -- --run`, targeted component tests, and Playwright scripts relevant to the feature. Update or add fixtures in `src/tests/mocks`.
5. **Document**: if behaviour or configuration changes, capture it in the relevant planning doc and ensure this plan stays accurate.

## Tracking & Dependencies
- Backend discrepancy: `/api/v1/health` currently returns only `{"status": "ok"}`; note any assumptions in PRs until backend adds `version`/`uptime`.
- Mapping tiles require provider credentials; keep default provider configurable via `lib/config.ts`.
- Weather overlay and latency monitoring are Phase 2 backlog items; leave toggles stubbed but non-blocking.

## After MVP
- **Analytics & Observability**: integrate Sentry/browser metrics once MVP stabilises (`frontend/docs/operations/observability.md`).
- **Metrics Download Helper**: light UI around `/metrics` for analysts.
- **Latency Warnings**: instrument API client to surface slow backend responses.
- **Polish & Launch**: theming refinements, bundle optimisation, localisation, release checklist (see `frontend/docs/roadmap/roadmap.md` and `frontend/docs/operations/testing.md`).

## Reference Index
- Architecture decisions: `frontend/docs/architecture/overview.md`
- UX reference flows: `frontend/docs/product/ux-flows.md`
- Testing strategy & coverage targets: `frontend/docs/operations/testing.md`
- Observability plan: `frontend/docs/operations/observability.md`
- Roadmap & timeline: `frontend/docs/roadmap/roadmap.md`

Keep this document authoritative: when scope shifts or work completes, update the relevant section so new contributors and agents always have an accurate to-do list.
