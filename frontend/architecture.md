# Frontend Architecture Plan

## Objectives
- Deliver a performant, map-centric BahnVision web client that consumes the FastAPI backend at `/api/v1`.
- Reuse backend caching semantics (e.g., `X-Cache-Status`) to surface data freshness to riders.
- Keep the stack lightweight so we can iterate quickly while leaving room for a native app later.

## Proposed Stack
- Framework: React 18 + TypeScript orchestrated with Vite for fast local feedback.
- Routing: React Router v7 (file-based via `@tanstack/router` alternative is an open question; start with Router v7 for maturity).
- Data fetching: TanStack Query for cache-aware API consumption, retries, and background revalidation aligned with backend stale-refresh semantics.
- UI toolkit: Tailwind CSS + Headless UI primitives for accessible components; custom theming for MVG branding.
- Map layer: React-Leaflet (matches backend system diagram) with MVG station overlays rendered from `/api/v1/mvg/stations/search` results and cached departures.
- State shape: keep global state minimal (TanStack Query + lightweight Zustand store for transient UI state like modal visibility).
- Build output: Static assets hosted behind CDN; environment config pulled from `.env` at build time (e.g., `VITE_API_BASE_URL`).

## Application Layers
1. **Presentation** – React components per page/flow (Departures board, Route Planner, Station Search overlay, System Status).
2. **Hooks & Services** – `useDepartures`, `useStationSearch`, `useRoutePlan`, `useHealth`, `useMetrics` built on top of TanStack Query.
3. **API Client** – thin wrapper around `fetch` that injects base URL, default headers, and handles 4xx/5xx mapping to domain errors.
4. **Utility Modules** – helpers for timezones (`Europe/Berlin` vs local), caching badges, map marker clustering, accessibility utilities.
5. **Shell** – `<App>` sets up routing, layout, providers (QueryClientProvider, ThemeProvider), and global toasts.

## Cross-Cutting Concerns
- **Internationalization**: start with English + German copy using `react-intl` or `lingui`; prepare translation keys.
- **Accessibility**: keyboard navigation for station list, focus management during route planning, color contrast aligning with MVG palette.
- **Responsive Design**: mobile-first layout with adaptive map controls; hide advanced filters behind drawers on small screens.
- **Offline & Caching**: TanStack Query persistent cache (IndexedDB) to allow quick reopening; show last-updated timestamp from backend responses.
- **Configuration**: environment variables for API base URL, map tile provider, feature flags (e.g., weather overlay once available).

## Deployment & Environments
- Local dev served via `npm run dev` (Vite). Proxy `/api` requests to FastAPI on `http://127.0.0.1:8000` using Vite dev server proxies.
- QA/Staging: built assets served by backend container (e.g., via Nginx) within Docker Compose using the same `docker compose up --build` entry point.
- Production: build pipeline publishes hashed assets to CDN; backend instances serve API only. Ensure cache headers align with frontend revalidation strategy.

## Open Questions
- Should we adopt Next.js for SSR to improve SEO? Current assumption is SPA is acceptable because primary usage is internal dashboards/kiosks.
- Weather overlay integration once Phase 2 backend APIs exist—will likely need separate service worker for periodic prefetch.
- Authentication/authorization is out-of-scope per backend goals; confirm before integrating any identity provider hooks.
