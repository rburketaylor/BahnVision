# Bug Triage Plan

**Date**: 2026-02-07  
**Status**: Open (triage only, no fixes applied)

## Scope

This plan prioritizes issues found in a parallel bug sweep across backend, frontend, migrations/config, and tests.

Priority definitions:

- **P0**: High production risk or user-facing core behavior broken.
- **P1**: Material correctness/reliability issues that should be fixed next.
- **P2**: Lower-risk defects, test/tooling gaps, and quality improvements.

## P0

1. **Invalid ingestion status default breaks writes**

- Files: `backend/app/persistence/repositories.py:164`
- Risk: Runtime DB write failures for ingestion completion.
- Why P0: Can break ingestion pipeline completion path.
- First validation: Run completion path without explicit status and confirm enum write behavior.

2. **Ingestion source enum mismatch between historical values and ORM**

- Files: `backend/app/persistence/models.py:63`, `backend/alembic/versions/0d6132be0bb0_initial_schema.py:30`, `backend/alembic/versions/80a6a8257627_rename_mvg_to_transit.py:28`
- Risk: Existing rows with legacy values may fail ORM reads/deserialization.
- Why P0: Data-access breakage risk on existing production records.
- First validation: Query/deserialize rows containing legacy `MVG_*` source values.

3. **Station schedule time picker does not affect departures request**

- Files: `frontend/src/pages/StationPage.tsx:101`, `frontend/src/pages/StationPage.tsx:186`
- Risk: Core user workflow returns stale/unexpected data.
- Why P0: User-visible feature appears functional but is a no-op.
- First validation: Select schedule time and inspect query params/network request.

## P1

1. **Transport mode filter ignored for 7d/30d cancellations totals**

- Files: `backend/app/services/heatmap_service.py:448`
- Risk: Incorrect analytics for filtered views.
- First validation: Compare filtered vs unfiltered totals in 24h vs 7d/30d.

2. **Transport mode filter ignored in overview impacted stations (daily path)**

- Files: `backend/app/services/heatmap_service.py:1074`
- Risk: Filtered overview results are misleading.
- First validation: Compare impacted station lists with and without filter at 7d.

3. **Transport mode filter ignored in network summary (daily path)**

- Files: `backend/app/services/heatmap_service.py:1265`
- Risk: Summary KPIs do not match selected filter.
- First validation: Compare summary KPIs with and without filter at 7d.

4. **GTFS stop info can false-404 when coordinates are NULL**

- Files: `backend/app/services/transit_data.py:438`
- Risk: Existing stops appear missing.
- First validation: Request stop info for stop with NULL lat/lon.

5. **GTFS-RT CANCELED schedule relationship not mapped end-to-end**

- Files: `backend/app/services/gtfs_realtime.py:621`, `backend/app/services/transit_data.py:58`, `backend/app/services/transit_data.py:667`
- Risk: Cancellation data dropped/misclassified.
- First validation: Feed/update with schedule relationship `CANCELED` and verify response mapping.

6. **CORS example format conflicts with parser behavior**

- Files: `.env.example:30`, `backend/app/core/config.py:316`
- Risk: Misconfigured CORS in local/prod setups following example.
- First validation: Load example value and inspect parsed origins.

7. **Alembic autogenerate may miss GTFS schema changes**

- Files: `backend/alembic/env.py:19`, `backend/app/models/gtfs.py:21`
- Risk: Schema drift and missing migrations.
- First validation: Make controlled GTFS model change and run autogenerate.

8. **Migration assumes PG15+ without version guard (`UNIQUE NULLS NOT DISTINCT`)**

- Files: `backend/alembic/versions/fix_heatmap_duplication.py:36`
- Risk: Migration failure on older Postgres.
- First validation: Run migration on PG14-compatible environment.

9. **ORM metadata mismatch with migration constraint semantics**

- Files: `backend/app/persistence/models.py:543`, `backend/alembic/versions/fix_heatmap_duplication.py:92`
- Risk: Migration/autogenerate drift and potential constraint churn.
- First validation: Compare metadata-generated diff against current schema.

10. **Daily aggregation uses local date instead of UTC**

- Files: `backend/app/api/v1/endpoints/heatmap.py:612`
- Risk: Off-by-one-day aggregation around timezone boundaries.
- First validation: Run with non-UTC server timezone and compare expected day window.

11. **Heatmap overview omits `last_updated_at` despite response model**

- Files: `backend/app/api/v1/endpoints/heatmap.py:506`, `backend/app/models/heatmap.py:88`
- Risk: Frontend freshness indicator incomplete/unknown.
- First validation: Inspect endpoint response payload for missing field.

12. **GTFS-RT dedup overcounts when cache batch ops fail**

- Files: `backend/app/services/gtfs_realtime_harvester.py:874`
- Risk: Inflated stats during cache degradation.
- First validation: Simulate cache `mget/mset` failure during harvest.

13. **Import lock fallback to in-memory lock is unsafe cross-worker**

- Files: `backend/app/services/gtfs_import_lock.py:47`
- Risk: Concurrent import+harvest in multi-worker deployments.
- First validation: Multi-process run with cache unavailable and concurrent workloads.

14. **Heatmap health endpoint returns HTTP 200 on dependency failure**

- Files: `backend/app/api/v1/endpoints/heatmap.py:584`
- Risk: Monitoring may miss real failures.
- First validation: Force dependency failure and inspect status code.

15. **Monitoring response-time metric parsed from histogram bucket counts**

- Files: `frontend/src/components/features/monitoring/PerformanceTab.tsx:45`
- Risk: Incorrect latency shown to operators.
- First validation: Compare UI value to `_sum/_count` derived latency.

16. **Date-only parsing in ingestion UI can display prior day in non-UTC zones**

- Files: `frontend/src/components/features/monitoring/IngestionTab.tsx:33`
- Risk: Misleading date display for users.
- First validation: Render `YYYY-MM-DD` in US timezone and verify displayed day.

17. **Playwright baseURL/webServer port mismatch under one CI mode**

- Files: `frontend/playwright.config.ts:3`
- Risk: CI flakiness/failures targeting wrong port.
- First validation: Run with `PLAYWRIGHT_START_WEB_SERVER=1` and verify target URL.

18. **Test masking: cancellation loop test can pass without verifying behavior**

- Files: `backend/tests/jobs/test_rt_processor.py:115`
- Risk: Regressions can slip through.
- First validation: Intentionally break cancellation handling and run test.

## P2

1. **Delay totals can be understated on in-bucket status upgrades**

- Files: `backend/app/services/gtfs_realtime_harvester.py:848`
- Risk: Analytics precision issue.

2. **Heatmap overview cache key lacks transport-mode normalization**

- Files: `backend/app/api/v1/endpoints/heatmap.py:541`, `backend/app/services/heatmap_cache.py:12`
- Risk: Cache misses for equivalent requests.

3. **GTFS-RT TaskGroup treats cache-store failure as full feed failure**

- Files: `backend/app/services/gtfs_realtime.py:331`
- Risk: Circuit-breaker noise and reduced observability clarity.

4. **Compose health dependency references backend healthcheck that may not exist**

- Files: `docker-compose.yml:82`, `docker-compose.yml:32`
- Risk: Startup ordering issue in some Compose configurations.

5. **Non-idempotent GTFS table migration DDL**

- Files: `backend/alembic/versions/add_gtfs_tables.py:22`
- Risk: Re-run/recovery fragility.

6. **Heatmap search hotkey captures modified shortcuts (Ctrl/Cmd+S)**

- Files: `frontend/src/components/features/heatmap/HeatmapSearchOverlay.tsx:42`
- Risk: UX/accessibility friction.

7. **Health error UI collapses non-string errors to generic message**

- Files: `frontend/src/components/features/monitoring/OverviewTab.tsx:21`
- Risk: Reduced diagnosability.

8. **Timing-based tests are likely flaky under load**

- Files: `backend/tests/services/test_cache_primitives.py:70`, `backend/tests/services/test_cache_compatibility.py:209`
- Risk: Intermittent CI failures.

9. **Frontend test-quality coverage gap in checker tool**

- Files: `scripts/check_test_quality.py:23`, `.pre-commit-config.yaml:91`
- Risk: False confidence for TS/TSX test assertion quality.

10. **Non-deterministic time defaults in test fixtures**

- Files: `backend/tests/fixtures/gtfs_data.py:118`
- Risk: Date-boundary flakiness.

## Suggested Execution Order

1. Address all **P0** items first.
2. In **P1**, prioritize API correctness issues affecting filtered analytics and monitoring correctness.
3. Land **P2** in batches by area (backend runtime, frontend UX, test/tooling hardening).
