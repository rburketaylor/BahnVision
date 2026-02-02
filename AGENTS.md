# Repository Guidelines

> **Note**: `GEMINI.md` and `CLAUDE.md` are symlinks to this file (`AGENTS.md`). All AI agents share this single source of truth for repository guidelines. Edit only `AGENTS.md`; changes will be visible to all agents.

## Project Structure & Modules

- Backend lives in `backend/app`: FastAPI entry in `main.py`, routes under `api/v1/endpoints`, shared cache utilities in `api/v1/shared`, services (GTFS schedule, cache) in `services`, Pydantic models in `models`, persistence in `persistence`.
- Backend docs: `backend/docs/README.md`, tech spec at `docs/tech-spec.md`.
- Frontend lives in `frontend`: components/pages/hooks/services under `src`, Vite + React 19 + TypeScript.
- Tests mirror code: backend tests in `backend/tests`, frontend unit/integration in `frontend/src` (Vitest), E2E in `frontend` (Playwright).
- Compose topology at `docker-compose.yml`; root `README.md` is the overview.

## Build, Test, and Development Commands

### Initial Setup (One-Time)

Run `./scripts/setup-dev.sh` to bootstrap the dev environment (downloads Node.js LTS, creates Python venv, installs all dependencies).

### Environment Activation

**Automatic (recommended)**: Install direnv (`sudo apt install direnv` or `brew install direnv`), add `eval "$(direnv hook bash)"` (or zsh) to your shell config, restart your shell, and run `direnv allow` in the project root. The dev environment will now load automatically on `cd` into the project.

**Manual fallback**: If direnv is not configured, activate the environment with `source .dev-env` before running any commands below.

### Development Commands (assume environment is activated)

- Backend local dev: `uvicorn app.main:app --reload --app-dir backend`
- Frontend local dev: `cd frontend && npm run dev` (Vite at `:5173`)
- Docker stack: `docker compose up --build` (starts cache warmup, backend on `:8000`, frontend on `:3000`)

### Testing

- Backend tests: `pytest backend/tests`
- Frontend tests: `npm run test -- --run` (Vitest in single-run mode; avoid watch mode which hangs)
- Frontend coverage: `npm run test:coverage`
- Frontend E2E: `npm run test:e2e` (Playwright)
- Quality checks: `python scripts/check_test_quality.py [dir]` (included in CI)
- Secrets detection: `pre-commit run detect-secrets --all-files` (uses `.secrets.baseline`)

### Linting & Type Checking

- Frontend lint: `cd frontend && npm run lint`
- Frontend typecheck: `cd frontend && npm run type-check`
- Frontend mutation testing: `cd frontend && npm run stryker`
- Backend lint + format: `pre-commit run --all-files`
- Backend typecheck: `mypy backend/app`

### Dependency Auditing

- Backend: `pip-audit`
- Frontend: `npm audit`

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
- Playwright: Prefer built-in user-facing locators (getByRole, getByLabelText, getByPlaceholderText) over CSS selectors for more resilient, accessible tests. Use automatic waiting; avoid hard timeouts.
- Run targeted tests before PRs; aim for coverage via `npm run test:coverage` when touching frontend logic.

## Commit & Pull Request Guidelines

- **Before committing, ensure docker compose is up-to-date**: Run `docker compose up --build -d` to rebuild and start all services with the latest code. Some backend tests require Valkey and other services to be running.
- **Pre-commit hooks run tests automatically**: When you commit changes to backend Python files, pytest runs automatically. When you commit frontend TypeScript/TSX files, vitest runs automatically. This catches test failures before they reach CI. If you need to run tests manually beforehand: `pytest backend/tests` for backend, `cd frontend && npm run test -- --run` for frontend.
- **Environment must be active before committing**: With direnv, the environment loads automatically. Without it, run `source .dev-env` before `git commit` to ensure pre-commit hooks have access to the required tools (black, ruff).
- **Never skip pre-commit hooks**: Do not use `--no-verify` or similar flags. Pre-commit hooks must run on every commit, even if they report "Skipped" for files not matching their patterns.
- Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `build:`, etc.); keep subjects concise.
- PRs should describe scope, testing performed, and any manual steps; link issues and add screenshots or sample responses for UI/API changes.
- Avoid unrelated drive-by changes; update requirements/package manifests when dependencies change.
- Document config changes (e.g., cache TTLs, env vars) in PR descriptions.

## Security & Configuration Tips

- Store secrets (DB/Valkey URLs, API tokens) in env vars or `.env` excluded from VCS; do not hardcode credentials.
- Prefer copying `.env.example` to `.env` (repo root) for local development if it doesn't exist; keep `.env` out of commits.
- Default local DB URL: `postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`; configure Valkey via `CACHE_*` envs; prefer `docker compose` for parity.
- Regularly audit dependencies: `pip-audit` for Python, `npm audit` for frontend. Consider Dependabot or Renovate for automated dependency updates.
- Respect cache behavior: writes populate Valkey and fallback store; watch `X-Cache-Status` and Prometheus metrics (`/metrics`) for validation.

## Database & Migrations

- Alembic config lives at `backend/alembic.ini` with migrations under `backend/alembic/`.
- If a change affects schemas, include an Alembic migration (and mention it in the PR description).
- Common commands: `alembic -c backend/alembic.ini upgrade head` and `alembic -c backend/alembic.ini revision --autogenerate -m "..."`.
- Avoid using ORM models in migrations - they may become stale. Use `op.execute()` with raw SQL or Alembic's batch operations for schema changes. Make migrations idempotent when possible.

## Agent Behavior Guidelines

- **Verify before claiming**: Before stating that something "is used" or "applies" to this project, check the actual codebase. Use grep/search tools to confirm patterns exist.
- **Cite sources**: When referencing existing code patterns, cite the specific file(s) where they appear (e.g., "as seen in `backend/app/services/cache_service.py`").
- **Turn mistakes into rules**: If you notice you made a mistake (especially repeating the same type of mistake), re-check `AGENTS.md` and update it with a new or clarified rule that prevents that mistake in future runs.
- **Distinguish facts from recommendations**: Clearly differentiate between:
  - **Current state**: What actually exists in the codebase today (verified by inspection)
  - **Recommendations**: Best practices or suggestions that are not yet implemented
- **Don't assume**: If unsure whether a pattern or tool is used, search the codebase first rather than assuming based on common conventions.

## Docs & API Changes

- When changing backend routes or response shapes, update relevant backend docs under `backend/docs/` and any impacted frontend API/client code under `frontend/src/services/`.
