# Repository Guidelines

> **Note**: `GEMINI.md` and `CLAUDE.md` are symlinks to this file (`AGENTS.md`). All AI agents share this single source of truth for repository guidelines. Edit only `AGENTS.md`; changes will be visible to all agents.

## Project Structure & Modules
- Backend lives in `backend/app`: FastAPI entry in `main.py`, routes under `api/v1/endpoints`, shared cache utilities in `api/v1/shared`, services (GTFS schedule, cache) in `services`, Pydantic models in `models`, persistence in `persistence`.
- Backend docs: `backend/docs/README.md`, tech spec at `docs/tech-spec.md`.
- Frontend lives in `frontend`: components/pages/hooks/services under `src`, Vite + React 19 + TypeScript.
- Tests mirror code: backend tests in `backend/tests`, frontend unit/integration in `frontend/src` (Vitest), E2E in `frontend` (Playwright).
- Compose topology at `docker-compose.yml`; root `README.md` is the overview.

## Build, Test, and Development Commands
- **Quick setup**: Run `./scripts/setup-dev.sh` to bootstrap the dev environment (downloads Node.js LTS, creates Python venv, installs all dependencies). Then `source .dev-env` to activate.
- Backend local dev: `source backend/.venv/bin/activate && uvicorn app.main:app --reload --app-dir backend`.
- Frontend local dev: `cd frontend && npm run dev` (Vite at `:5173`).
- Local Node toolchain lives at `.node/bin/`; prepend it when running frontend commands if `npm`/`node` is missing, e.g. `PATH=".node/bin:$PATH" npm run test`.
- Docker stack: `docker compose up --build` (starts cache warmup, backend on `:8000`, frontend on `:3000`).
- Local Python virtualenv lives in `backend/.venv`; activate with `source backend/.venv/bin/activate` before backend commands.
- Backend tests: `source backend/.venv/bin/activate && pytest backend/tests`.
- Frontend tests: `npm run test -- --run` (Vitest in single-run mode; avoid watch mode which hangs), `npm run test:coverage` for coverage, `npm run test:e2e` for Playwright.
- Frontend lint + format check: `cd frontend && npm run lint`.
- Frontend typecheck: `cd frontend && npm run type-check`.
- Backend lint + format (preferred): `source backend/.venv/bin/activate && pre-commit run --all-files`.

## Coding Style & Naming Conventions
- Python: PEP 8, 4-space indent, snake_case modules; prefer typed signatures and Pydantic models; keep services stateless and cache logic centralized.
- TypeScript/React: idiomatic React 19 with hooks; prefer typed props and TanStack Query for data fetching; Tailwind utility classes.
- Use existing patterns for caching (single-flight locks, stale reads) and metrics; avoid new dependencies without discussion.
- Pre-commit hooks enforce black formatting and ruff linting; install with `pre-commit install` after setting up the backend virtualenv.

## Testing Guidelines
- Mirror code structure in tests; add regression tests for bugs and unit/integration for new features.
- Backend: use FastAPI TestClient, Fake Valkey/GTFS doubles for deterministic tests.
- Backend test markers: `pytest backend/tests -m "not integration"` for fast unit tests; `pytest backend/tests -m integration` for service-backed tests.
- Frontend: RTL + MSW for API mocking; keep tests colocated under `src`; name test files `*.test.ts[x]`.
- Run targeted tests before PRs; aim for coverage via `npm run test:coverage` when touching frontend logic.

## Commit & Pull Request Guidelines
- **Before committing, ensure docker compose is up-to-date**: Run `docker compose up --build -d` to rebuild and start all services with the latest code. Some backend tests require Valkey and other services to be running.
- **Run the full test suite before committing**: Execute `source backend/.venv/bin/activate && pytest backend/tests` for backend and `cd frontend && npm run test -- --run` for frontend (Vitest single-run; do not use watch mode). Fix any failures before proceeding with commits.
- **Always activate the backend virtualenv before committing**: Run `source backend/.venv/bin/activate` before any `git commit` to ensure pre-commit hooks have access to the required tools (black, ruff).
- **Never skip pre-commit hooks**: Do not use `--no-verify` or similar flags. Pre-commit hooks must run on every commit, even if they report "Skipped" for files not matching their patterns.
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, etc.); keep subjects concise.
- PRs should describe scope, testing performed, and any manual steps; link issues and add screenshots or sample responses for UI/API changes.
- Avoid unrelated drive-by changes; update requirements/package manifests when dependencies change.
- Document config changes (e.g., cache TTLs, env vars) in PR descriptions.

## Security & Configuration Tips
- Store secrets (DB/Valkey URLs, API tokens) in env vars or `.env` excluded from VCS; do not hardcode credentials.
- Prefer copying `.env.example` to `.env` (repo root) for local development if it doesn't exist; keep `.env` out of commits.
- Default local DB URL: `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`; configure Valkey via `CACHE_*` envs; prefer `docker compose` for parity.
- Respect cache behavior: writes populate Valkey and fallback store; watch `X-Cache-Status` and Prometheus metrics (`/metrics`) for validation.

## Database & Migrations
- Alembic config lives at `backend/alembic.ini` with migrations under `backend/alembic/`.
- If a change affects schemas, include an Alembic migration (and mention it in the PR description).
- Common commands: `source backend/.venv/bin/activate && alembic -c backend/alembic.ini upgrade head` and `source backend/.venv/bin/activate && alembic -c backend/alembic.ini revision --autogenerate -m "..."`.

## Docs & API Changes
- When changing backend routes or response shapes, update relevant backend docs under `backend/docs/` and any impacted frontend API/client code under `frontend/src/services/`.
