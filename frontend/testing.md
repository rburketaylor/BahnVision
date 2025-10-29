# Frontend Testing Strategy

## Principles
- Cover critical rider journeys (station search, departures view, route planning) with automated tests before launch.
- Keep tests fast and deterministic; mock backend responses with recorded fixtures to avoid MVG rate limits.
- Align coverage with backend expectations: verify cache headers, HTTP error handling, and concurrency safeguards.

## Test Layers
1. **Unit Tests**
   - Tools: Vitest + React Testing Library.
   - Scope: pure utilities (time formatting, cache badge logic), hooks (ensure query keys, polling cadence, error states).
2. **Component/UI Tests**
   - Tools: React Testing Library + MSW for network mocks.
   - Validate rendering of departures table, route cards, loading skeletons, and error toasts.
   - Snapshot testing limited to iconography/consistent layout wrappers.
3. **Integration/E2E Tests**
   - Tools: Playwright.
   - Flows: station search → departures; route planning with filters; stale cache banner when backend returns `X-Cache-Status: stale` (mocked via MSW or dev proxy).
   - Run against local FastAPI via docker compose in CI using seeded fixtures.
4. **Visual Regression (Optional)**
   - Percy or Chromatic once UI stabilizes; ensures map overlays and theming remain intact.

## Test Data & Mocking
- Maintain JSON fixtures mirroring responses defined in `backend/app/models/mvg.py` and `backend/docs/tech-spec.md`.
- Use MSW to stub `/api/v1` endpoints; simulate error cases (404, 502, 503) and alternate cache headers.
- For Playwright, start backend in mocked mode or inject static fixtures via query parameters (e.g., `?mock=marienplatz`).

## Continuous Integration
- `npm run lint` (ESLint) – dry-run first per repository policy, then enforce on touched files.
- `npm run test` – Vitest unit suite.
- `npm run test:e2e` – Playwright headless; gate merges.
- Publish Playwright videos/artifacts for failed runs.

## Coverage Goals
- ≥80% statement coverage on hooks/services.
- 100% coverage on error branches that map backend failures to UI copy.
- Track coverage reports in CI, fail if <75% overall.

## Manual QA Checklist
- Verify map markers align with station lat/long.
- Confirm stale cache badge appears when backend returns stale headers.
- Simulate offline mode (Chrome dev tools) to ensure helpful message and cached data message.
- Validate screen reader announcements for route legs and cancellations.
