# Pending Plan Items (Consolidated)

This file consolidates unresolved items from:

- `docs/plans/realtime-stats-data-investigation-findings.md`
- `docs/plans/verified-issue-remediation-2026-02-08.md`

## Verification Status (2026-02-17)

## Realtime Stats and Monitoring

- [ ] Run and capture diagnostic commands to isolate the realtime stats ingestion root cause (no captured diagnostics artifact found in the repository).
- [ ] Add explicit logging for silent early returns in GTFS-RT harvesting (partially done: empty-feed path logs in `backend/app/services/gtfs_realtime_harvester.py`, but `_upsert_stats` early return on empty input is still silent).
- [ ] Extend health checks to validate data freshness (not only dependency liveness) (`backend/app/api/v1/endpoints/health.py` still checks liveness/readiness only).
- [ ] Add Prometheus metrics for GTFS-RT harvesting (success/failure counts, durations, output volume) (not present in `backend/app/core/metrics.py` or harvester code).
- [ ] Add alerting rules tied to GTFS-RT ingestion and freshness (recommended in `backend/docs/gtfs-rt-monitoring.md`, but no Prometheus alert rule files are configured in repo).
- [x] Document a monitoring dashboard for GTFS-RT/realtime stats operations (`backend/docs/gtfs-rt-monitoring.md`).

## Backend Reliability and Model Cleanup

- [ ] Review and harden GTFS import transaction boundaries to reduce partial-update risk (import flow in `backend/app/services/gtfs_feed.py` still performs multi-step truncate/import with intermediate commits).
- [x] Replace remaining `datetime.utcnow()` defaults in GTFS models with timezone-aware alternatives (`backend/app/models/gtfs.py` contains no `datetime.utcnow()` defaults).
- [x] Migrate GTFS SQLAlchemy models off legacy `Column(...)` style to modern typed declarative mappings (`backend/app/models/gtfs.py` uses `Mapped[...]` + `mapped_column(...)`).
- [ ] Add retry/backoff behavior for scheduled daily aggregation triggering (`backend/app/api/v1/endpoints/heatmap.py` `_daily_aggregation_task` has no retry/backoff loop).
