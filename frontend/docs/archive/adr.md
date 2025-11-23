# ADR 001 – Frontend Stack Selection

- **Status**: Proposed
- **Date**: 29 October 2025

## Context
- Backend delivers REST endpoints under `/api/v1` with caching semantics and Prometheus metrics (`docs/tech-spec.md`).
- The product roadmap requires a responsive web client with map visualization (React/Leaflet noted in backend architecture section).
- Team wants rapid iteration, strong TypeScript support, and alignment with existing DevOps tooling (Docker Compose, GitHub Actions).

## Decision
- Build the frontend as a single-page application using React 19 + TypeScript, bundled by Vite.
- Manage server communication with TanStack Query, wrapping backend endpoints (`/api/v1/mvg/...`, `/api/v1/health`).
- Use Tailwind CSS + Headless UI for accessible component primitives, and React-Leaflet for geospatial features.
- Rely on MSW for API mocking in development/testing to respect MVG rate limits.

## Consequences
- Fast local feedback loop and DX; small learning curve for teams already versed in React.
- SPA approach defers SEO/SSR benefits; acceptable because initial users are commuters accessing bookmarked views and internal analysts.
- Need to enforce performance budgets manually (no built-in Next.js analytics); integrate Web Vitals monitoring.
- Clear path to extend toward PWA/offline capabilities using Vite plugins if kiosk support becomes priority.

## Alternatives Considered
- **Next.js (App Router)**: Pros – SSR, built-in i18n; Cons – higher deployment complexity, limited offline support for kiosk scenarios, unnecessary overhead for MVP.
- **SvelteKit**: Pros – lean bundle, great for real-time UI; Cons – team ramp-up cost, smaller ecosystem for existing Leaflet integrations.
