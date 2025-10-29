# Repository Guidelines

## Project Structure & Module Organization
- `backend/docs/tech-spec.md` is the canonical backend spec; additional context lives under `backend/docs/`. `docker-compose.yml` wires the backend container and Valkey for local runs.
- Runtime code is in `backend/app`. `main.py` bootstraps FastAPI, `api/routes.py` registers versioned routers in `api/v1/`, and `api/metrics.py` exposes the Prometheus scrape endpoint.
- Domain service logic lives in `services/` with HTTP schemas under `models/`. Persistence code (SQLAlchemy models, repositories, and dependencies) resides in `persistence/` and uses the shared async engine from `core/database.py`.
- Shared configuration stays in `core/config.py`, which now includes Valkey cache settings and database connectivity options.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create and activate a local virtual environment.
- `pip install -r backend/requirements.txt` — install FastAPI, MVG client, and Valkey dependencies.
- `uvicorn app.main:app --reload --app-dir backend` — start the API with hot reload at `http://127.0.0.1:8000`.
- `docker compose up --build` — launch the backend plus Valkey using the compose file; persists local cache data in the container network.
- The default `DATABASE_URL` points at a local Postgres instance (`postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision`). Ensure it is reachable before running features that hit persistence.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation; keep modules and files snake_case (`services/mvg_client.py`).
- Prefer typed function signatures and Pydantic models for request/response validation.
- Co-locate HTTP schemas with the route that consumes them, and keep service classes stateless so they can be reused by dependency injection.

## Testing Guidelines
- Use `pytest` with files named `test_*.py`; place them under `backend/tests/` mirroring the `app/` structure.
- Test FastAPI routes via the `TestClient` and mock Valkey interactions to keep suites deterministic.
- Target meaningful coverage on service modules and cache behaviors before merging major features.

## Commit & Pull Request Guidelines
- Follow the Conventional Commit style seen in history (`feat:`, `build:`, `docs:`) and keep subject lines under ~60 characters.
- Maintain concise subjects, but include a commit body summarizing documentation reorganizations or other multi-file context so reviewers see the rationale without opening diffs.
- Squash small fixups locally; each PR should describe the change set, reference related issues, and mention config or schema updates.
- Add screenshots or sample responses when endpoints change, and highlight any manual operational steps required post-merge.

## Security & Configuration Tips
- Store secrets (Valkey URLs, API tokens) in environment variables or `.env` files that stay out of version control.
- Document non-default runtime options (e.g. custom `DATABASE_URL` or cache TTL overrides) in the PR description so deployers can reproduce the environment quickly.
