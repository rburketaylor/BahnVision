# Repository Guidelines

## Project Structure & Module Organization
- Root `design-doc.md` captures the system overview; `docker-compose.yml` wires the backend and Valkey.
- All runtime code lives in `backend/app`. `main.py` bootstraps FastAPI, `api/routes.py` exposes endpoints, and domain logic sits in `services/` with Pydantic models under `models/`.
- Add new feature modules inside `backend/app/<domain>` and keep shared configuration in `core/config.py`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — create and activate a local virtual environment.
- `pip install -r backend/requirements.txt` — install FastAPI, MVG client, and Valkey dependencies.
- `uvicorn app.main:app --reload --app-dir backend/app` — start the API with hot reload at `http://127.0.0.1:8000`.
- `docker compose up --build` — launch the backend plus Valkey using the compose file; persists local cache data in the container network.

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
- Squash small fixups locally; each PR should describe the change set, reference related issues, and mention config or schema updates.
- Add screenshots or sample responses when endpoints change, and highlight any manual operational steps required post-merge.

## Security & Configuration Tips
- Store secrets (Valkey URLs, API tokens) in environment variables or `.env` files that stay out of version control.
- Document non-default runtime options in the PR description so deployers can reproduce the environment quickly.
