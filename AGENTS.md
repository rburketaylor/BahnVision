# Repository Guidelines

## Project Structure & Modules
- Backend lives in `backend/app`: FastAPI entry in `main.py`, routes under `api/v1/endpoints`, shared cache utilities in `api/v1/shared`, services (MVG client, cache) in `services`, Pydantic models in `models`, persistence in `persistence`.
- Backend docs: `backend/docs/README.md`, tech spec at `docs/tech-spec.md`.
- Frontend lives in `frontend`: components/pages/hooks/services under `src`, Vite + React 19 + TypeScript.
- Tests mirror code: backend tests in `backend/tests`, frontend unit/integration in `frontend/src` (Vitest), E2E in `frontend` (Playwright).
- Compose topology at `docker-compose.yml`; root `README.md` is the overview.

## Build, Test, and Development Commands
- Backend local dev: `python -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt` then `uvicorn app.main:app --reload --app-dir backend`.
- Frontend local dev: `npm install` then `npm run dev` (Vite at `:5173`).
- Local Node toolchain (Node 24.11.1) lives at `./.node/node-v24.11.1-linux-x64/bin`; prepend it when running frontend commands if `npm`/`node` is missing, e.g. `PATH=".node/node-v24.11.1-linux-x64/bin:$PATH" npm run test`.
- Docker stack: `docker compose up --build` (starts cache warmup, backend on `:8000`, frontend on `:3000`).
- Local Python virtualenv lives in `.venv`; activate with `source .venv/bin/activate` before backend commands, or run directly with `PATH=".venv/bin:$PATH"` on one-offs (e.g. `PATH=".venv/bin:$PATH" python -m pytest backend/tests`).
- Backend tests: `pytest backend/tests`.
- Frontend tests: `npm run test` (Vitest), `npm run test:coverage` for coverage, `npm run test:e2e` for Playwright.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, snake_case modules; prefer typed signatures and Pydantic models; keep services stateless and cache logic centralized.
- TypeScript/React: idiomatic React 19 with hooks; prefer typed props and TanStack Query for data fetching; Tailwind utility classes.
- Use existing patterns for caching (single-flight locks, stale reads) and metrics; avoid new dependencies without discussion.

## Testing Guidelines
- Mirror code structure in tests; add regression tests for bugs and unit/integration for new features.
- Backend: use FastAPI TestClient, Fake Valkey/MVG doubles for deterministic tests.
- Frontend: RTL + MSW for API mocking; keep tests colocated under `src`; name test files `*.test.ts[x]`.
- Run targeted tests before PRs; aim for coverage via `npm run test:coverage` when touching frontend logic.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, etc.); keep subjects concise.
- PRs should describe scope, testing performed, and any manual steps; link issues and add screenshots or sample responses for UI/API changes.
- Avoid unrelated drive-by changes; update requirements/package manifests when dependencies change.
- Document config changes (e.g., cache TTLs, env vars) in PR descriptions.

## Security & Configuration Tips
- Store secrets (DB/Valkey URLs, API tokens) in env vars or `.env` excluded from VCS; do not hardcode credentials.
- Default local DB URL: `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`; configure Valkey via `CACHE_*` envs; prefer `docker compose` for parity.
- Respect cache behavior: writes populate Valkey and fallback store; watch `X-Cache-Status` and Prometheus metrics (`/metrics`) for validation.
