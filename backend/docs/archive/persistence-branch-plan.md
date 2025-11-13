# Persistence Branch Plan

This plan outlines the work for integrating the existing async SQLAlchemy models and repositories into API flows with safe latency, tracked migrations, and test coverage.

## Branch
- Name: `feat/persistence-integration`
- Base: `main`

## Scope
- Use existing models in `backend/app/persistence/models.py` and `TransitDataRepository` to persist data.
- Add route snapshot persistence and wire in background-safe writes for MVG endpoints.
- Validate Alembic upgrade/rollback and add basic CI smoke coverage.

## Milestones
- MS1: Schema & migrations — see `backend/docs/roadmap/tasks.json` (MS1-T2, MS1-T3).
- MS2: Persistence integration + tests — see `backend/docs/roadmap/tasks.json` (MS2-T1, MS2-T2, MS2-T3).
- MS4: Logging follow-up (structured JSON) — see `backend/docs/roadmap/tasks.json` (MS4-T2).

## Plan
- Create branch and baseline migrations
  - `git checkout -b feat/persistence-integration`
  - `cd backend && alembic upgrade head`
- Add repository method for routes
  - Implement `create_route_snapshot()` in `backend/app/persistence/repositories.py` using `models.RouteSnapshot`.
- Wire persistence into endpoints (background to avoid latency regressions)
  - Departures: after successful cache/MVG response, background task upserts station/lines and records observations via `TransitDataRepository`.
  - Routes: capture filters, itineraries, and external status into `route_snapshots`.
- Testing and fixtures
  - Add async DB fixtures (session + Alembic upgrade/teardown) under `backend/tests/`.
  - Add tests to verify departures and route snapshot persistence flows.
- Migration CI sanity
  - Script `alembic upgrade head && alembic downgrade -1` in CI.
- Docs and ops notes
  - Update `backend/README.md` with migration IDs and local workflow as needed.

## Acceptance
- `alembic upgrade head` creates all expected tables and indexes.
- Departures persist with `transport_mode`, `delay_seconds`, and `remarks` without changing `X-Cache-Status` semantics.
- Route snapshots persist with filters, itineraries, and MVG status.
- New persistence tests pass in `pytest`.

## Handy Commands
- Create branch: `git checkout -b feat/persistence-integration`
- Local migrate: `cd backend && alembic upgrade head`
- Rollback smoke: `alembic downgrade -1 && alembic upgrade head`

