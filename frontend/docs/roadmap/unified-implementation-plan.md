# BahnVision Frontend: Unified Implementation Plan

> Status: In progress. Core flows (station search, departures board, planner, insights) exist; use this plan to close remaining gaps (maps, observability, analytics) and validate current implementations. Backend contract details live in `docs/tech-spec.md`.

This document synthesizes all planning artifacts and codebase analysis into a single, actionable plan for developing the BahnVision frontend. It is designed to be executed by a software agent, with clear, sequential phases and testable deliverables.

## 1. Project Overview & Technical Foundation

The frontend is a React 19 + TypeScript single-page application built with Vite. It leverages Tailwind CSS for styling, TanStack Query for data fetching, and React Router for navigation. The backend API contract is documented in `frontend/docs/architecture/api-integration.md`.

**Key Technical Decisions (from ADR & Architecture):**
- **Stack:** React, Vite, TypeScript, Tailwind CSS, Headless UI.
- **Data Fetching:** TanStack Query to manage server state, respecting backend cache headers (`X-Cache-Status`).
- **Routing:** `react-router` for client-side navigation.
- **Mapping:** `react-leaflet` for all geospatial visualizations.
- **Testing:** A hybrid approach using Vitest for unit tests, React Testing Library for components, and Playwright for end-to-end flows. MSW is used for API mocking.

---

## 2. Phased Implementation Roadmap

### Phase 0: Setup & Scaffolding (Complete)

This phase involved bootstrapping the repository with the correct tools and configurations. Analysis of the existing codebase confirms this is complete.

- **[x]** Initialize Vite + React + TypeScript project.
- **[x]** Configure ESLint, Prettier, and Vitest.
- **[x]** Establish file structure (`/pages`, `/components`, `/hooks`, `/services`).
- **[x]** Create placeholder pages and basic routing in `App.tsx`.

### Phase 1: Core Feature Implementation (MVP)

This phase delivered the essential user-facing features. Current coverage:
- Health widget hook and usage in insights page exist (uptime/version still planned on backend).
- Station search component and hook are implemented with autocomplete.
- Departures page with filters, cache badge, and auto/manual refresh is live.
- Route planner page with origin/destination selection, optional times, and transport filters is live; map overlay is planned.
- Loading and error states exist; toast/error boundary work can be expanded.

### Phase 2: Observability & Testing

With core features in place, this phase focuses on ensuring reliability and gathering insights.

**Actionable Steps:**

1.  **Integrate Sentry for Error Tracking:**
    *   Add the Sentry SDK and configure it with the DSN from environment variables (`VITE_SENTRY_DSN`).
    *   Ensure release health and source maps are configured in the build process.

2.  **Write Comprehensive Tests:**
    *   **Unit Tests (Vitest):** Cover all utility functions (`time.ts`, `transport.ts`) and critical logic within hooks.
    *   **Component Tests (RTL):** Write tests for the `DeparturesBoard`, `StationSearch`, and `ItineraryCard` components, using MSW to mock API responses.
    *   **E2E Tests (Playwright):** Create test suites for the following user flows:
        *   Searching for a station and viewing its departures.
        *   Planning a route between two stations.
        *   Verifying that cache status badges appear correctly.

3.  **Implement Basic Analytics:**
    *   Integrate a privacy-compliant analytics provider.
    *   Add tracking for key events: `station_search_submitted`, `departures_view_loaded`, `route_plan_requested`.

### Phase 3: Polish & Launch Readiness

This final phase focuses on visual refinements, performance, and documentation.

**Actionable Steps:**

1.  **Localization (i18n):**
    *   Integrate a library like `react-intl` or `lingui`.
    *   Extract all user-facing strings into resource files for English and German.

2.  **Performance Optimization:**
    *   Analyze bundle size and implement code-splitting where necessary.
    *   Review Web Vitals scores and optimize rendering performance.

3.  **Final QA & Documentation:**
    *   Conduct a full manual QA pass based on the checklist in `frontend/docs/operations/testing.md`.
    *   Update the `README.md` with final build/run instructions.
    *   Create screenshots and document key features for operator handoff.
