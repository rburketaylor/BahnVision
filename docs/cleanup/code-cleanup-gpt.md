# Code cleanup findings (GPT)

Date: 2025-12-14

This document summarizes **what appears safe to delete** in this repo (mostly generated artifacts), plus **what is optional** (docs/examples) and **what to verify first**.

## What I checked

- Repo contains common generated artifacts in both `backend/` and `frontend/` (coverage outputs, Playwright report, build outputs, caches).
- Root `.gitignore` and `frontend/.gitignore` explicitly ignore most of these paths.
- CI workflow expects these outputs to be **generated** during jobs (e.g. `frontend/coverage/lcov.info`, `frontend/playwright-report/`), not committed.
- A quick `git ls-files` spot-check showed these candidate artifact paths are **not tracked** by git.

## Safe to delete (generated/untracked; will be re-created)

### Backend

- Python virtualenv: `backend/.venv/`
- Test / lint caches: `backend/.pytest_cache/`, `backend/.ruff_cache/`
- Coverage outputs:
  - `backend/.coverage`
  - `backend/coverage.json`
  - `backend/coverage.xml` (if present)
  - `backend/htmlcov/` (if present)
- Python bytecode caches: `backend/**/__pycache__/` and `backend/**/*.pyc`

### Frontend

- Dependencies: `frontend/node_modules/`
- Build output: `frontend/dist/`
- Unit-test coverage output: `frontend/coverage/`
- E2E outputs: `frontend/playwright-report/`, `frontend/test-results/`
- Mutation testing output: `frontend/reports/` (your `reports/mutation/` looks like Stryker output)

### Root (local dev bootstrap artifacts)

- `.node/` (local Node toolchain installed by setup script)
- `.dev-env` (activation file written by setup script)

## Likely safe, but only if you don’t need mutation-testing artifacts

- `backend/mutants/`
  - Appears to be **mutmut output** and is ignored by git.
  - Safe to delete as output, but keep mutation testing config if you still run mutmut.

## Optional repo content (delete only if you don’t need the capability)

These are not runtime dependencies of the backend/frontend code, but they are referenced by docs and/or scripts.

### Demo / monitoring / chaos stack

- `docker-compose.demo.yml`
- `examples/monitoring/`
- `examples/toxiproxy/`
- `scripts/chaos-scenarios.sh`

Notes:
- Docs reference the demo overlay.
- CI uploads Playwright outputs; the demo overlay may also be used for integration/e2e workflows.

### Kubernetes examples + kind helper

- `examples/k8s/`
- `scripts/setup-kind.sh`

Notes:
- Referenced in docs and in security tooling (k8s YAML scanning).

### Planning/history docs

- `docs/planning/archive/` (and potentially other planning docs)

Notes:
- Safe from a runtime perspective, but may be useful historical context.

## Suggested verification commands

Before deleting anything, you can confirm what’s ignored/generated:

- Preview ignored files that would be removed:
  - `git clean -ndX`
- Remove ignored files:
  - `git clean -fdX`

Important caution:
- `git clean -fdX` will also remove ignored local config such as `.env` (at repo root). If you want to keep `.env`, either back it up or delete paths explicitly instead of using a blanket clean.

## Conservative “delete explicitly” list

If you prefer explicit deletes (safer than `git clean -fdX`):

- Backend:
  - `rm -rf backend/.venv backend/.pytest_cache backend/.ruff_cache backend/htmlcov`
  - `rm -f backend/.coverage backend/coverage.json backend/coverage.xml`
  - `find backend -type d -name __pycache__ -prune -exec rm -rf {} +`
  - `find backend -type f -name '*.pyc' -delete`
- Frontend:
  - `rm -rf frontend/node_modules frontend/dist frontend/coverage frontend/playwright-report frontend/test-results frontend/reports`

## If you want a smaller repo footprint in git

If your goal is to reduce repo size in version control (not just local disk usage), the only candidates above that matter are the **tracked** ones.

Based on spot checks, the generated artifacts listed in this doc are not tracked, so the biggest wins are:
- Ensure `dist/`, `coverage/`, `playwright-report/`, `test-results/`, `reports/`, `node_modules/`, `backend/.venv/` stay untracked.
- Consider removing optional folders (`examples/`, `docs/planning/archive/`) only if you don’t need those capabilities or docs.
