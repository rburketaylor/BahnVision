# Docs Claims Audit & Alignment Plan

Date: 2026-01-26

## Goal

Bring repository documentation back into alignment with the current codebase by correcting API routes/params, healthcheck semantics, runtime defaults, and frontend stack/deploy instructions.

## Current State (Verified)

- Backend routes are mounted under `/api/v1` (`backend/app/api/v1/routes.py:8`).
- Transit endpoints use **stops** (not stations) and the departures query param is `stop_id`:
  - Search: `GET /api/v1/transit/stops/search?query=...` (`backend/app/api/v1/endpoints/transit/stops.py:53`)
  - Departures: `GET /api/v1/transit/departures?stop_id=...` (`backend/app/api/v1/endpoints/transit/departures.py:61`)
- Heatmap is under `/api/v1/heatmap/*`:
  - `GET /api/v1/heatmap/cancellations` (`backend/app/api/v1/endpoints/heatmap.py:181`)
  - `GET /api/v1/heatmap/overview` (`backend/app/api/v1/endpoints/heatmap.py:387`)
- `/api/v1/health` is a lightweight uptime/version endpoint (no dependency probes) (`backend/app/api/v1/endpoints/health.py:13`).
- `X-Request-Id` middleware injects a request id response header (`backend/app/main.py:62`).
- `X-Cache-Status` is explicitly set on heatmap responses today (`backend/app/api/v1/endpoints/heatmap.py:263`).
- Backend config defaults for DB pool are `DATABASE_POOL_SIZE=10` / `DATABASE_MAX_OVERFLOW=10` (`backend/app/core/config.py:46`).
- Frontend Docker image uses build-time args for Vite env (`frontend/Dockerfile:21`).
- Frontend dependencies do not include Zustand or Headless UI (`frontend/package.json:21`).

## Problems Found (Docs Drift)

### 1) API route + parameter drift

Docs currently reference routes/params that do not exist:

- Stations vs stops:
  - `README.md` lists `/api/v1/transit/stations/search` and `station=...` (`README.md:56`).
  - `docs/tech-spec.md` lists `/transit/stations/*` and `station` params (`docs/tech-spec.md:41`).
  - `frontend/README.md` repeats the same (`frontend/README.md:111`).
  - `frontend/docs/product/ux-flows.md` references `/stations/search?q=...` and `/departures?station=...` (`frontend/docs/product/ux-flows.md:23`).

### 2) Heatmap path drift

Docs refer to `/api/v1/transit/heatmap/data` (not present). Current endpoints are `/api/v1/heatmap/cancellations` and `/api/v1/heatmap/overview`.

### 3) Overbroad claim about `X-Cache-Status`

Root README describes `X-Cache-Status` as a general response header, but current code sets it explicitly for heatmap endpoints only.

### 4) Healthcheck semantics mismatch

`docs/tech-spec.md` claims `/health` probes Valkey/Postgres and returns `503` when dependencies are down (`docs/tech-spec.md:41`), but current `/api/v1/health` is lightweight uptime/version only (`backend/app/api/v1/endpoints/health.py:13`).

### 5) Runtime defaults drift

`docs/runtime-configuration.md` documents DB pool defaults as `5/5` (`docs/runtime-configuration.md:40`) but code defaults are `10/10` (`backend/app/core/config.py:46`).

### 6) Frontend stack + Docker instructions drift

- Frontend README claims Zustand 5 + Headless UI 2, but those dependencies are not present (`frontend/README.md:62`, `frontend/package.json:21`).
- Frontend README suggests runtime `docker run -e VITE_API_BASE_URL=...` but the image builds Vite env at build time via args (`frontend/README.md:102`, `frontend/Dockerfile:21`).

## Proposed Changes (Docs + Optional Code)

### A) Docs-only alignment (recommended first pass)

1. Update API endpoint tables and examples to match current backend:
   - Files: `README.md`, `backend/README.md`, `frontend/README.md`, `docs/tech-spec.md`, `frontend/docs/product/ux-flows.md`.
2. Update heatmap endpoint references to `/api/v1/heatmap/cancellations` and `/api/v1/heatmap/overview`.
3. Update `X-Cache-Status` documentation to explicitly scope it (heatmap today), or mark “planned for other endpoints”.
4. Update healthcheck documentation to describe the lightweight `/api/v1/health` response and point dependency monitoring to `/api/v1/system/ingestion-status` where appropriate (`backend/app/api/v1/endpoints/ingestion.py:82`).
5. Fix `docs/runtime-configuration.md` DB pool defaults to `10/10`.
6. Fix frontend README stack list and Docker standalone instructions:
   - Either remove “runtime env var” claim, or document that changing API base URL requires rebuilding the image (build args).

### B) Optional code alignment (if we want docs to keep stronger claims)

1. Implement a dependency-readiness endpoint (e.g., `GET /api/v1/ready`) that checks Valkey + Postgres and returns `503` on failure, then update:
   - `docs/tech-spec.md` to describe `/health` vs `/ready` split
   - `backend/Dockerfile` healthcheck target (`backend/Dockerfile:25`)
2. Standardize `X-Cache-Status` across more endpoints (departures/search) if desired, then update docs accordingly.

## Acceptance Criteria

- All docs that enumerate API routes match the actual FastAPI routes and params.
- Healthcheck documentation matches actual `/api/v1/health` behavior (or a new readiness endpoint exists and is documented).
- Runtime configuration docs reflect code defaults for DB pooling.
- Frontend README accurately reflects dependencies and how `VITE_*` config is provided in Docker.

## Work Checklist

- [ ] Update `README.md` endpoint table + example query params.
- [ ] Update `backend/README.md` endpoint list + curl example param names.
- [ ] Update `frontend/README.md` (endpoints, stack list, Docker standalone section).
- [ ] Update `docs/tech-spec.md` endpoint table + health semantics + error handling claims.
- [ ] Update `docs/runtime-configuration.md` DB default values.
- [ ] Update `frontend/docs/product/ux-flows.md` endpoint URLs/params and explicitly mark aspirational behaviors.
- [ ] (Optional) Add `/api/v1/ready` endpoint + update `backend/Dockerfile` healthcheck.
- [ ] (Optional) Expand `X-Cache-Status` to non-heatmap endpoints or narrow docs claim.
