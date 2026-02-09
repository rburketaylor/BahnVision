# Pending Plan Items (Consolidated)

This file consolidates unresolved items from:

- `docs/plans/realtime-stats-data-investigation-findings.md`
- `docs/plans/verified-issue-remediation-2026-02-08.md`

## Realtime Stats and Monitoring

1. Run and capture diagnostic commands to isolate the realtime stats ingestion root cause.
2. Add explicit logging for silent early returns in GTFS-RT harvesting (including `_upsert_stats` empty-input path).
3. Extend health checks to validate data freshness (not only dependency liveness).
4. Add Prometheus metrics for GTFS-RT harvesting (success/failure counts, durations, and output volume).
5. Add alerting rules tied to GTFS-RT ingestion and freshness.
6. Document a monitoring dashboard for GTFS-RT/realtime stats operations.

## Backend Reliability and Model Cleanup

1. Review and harden GTFS import transaction boundaries to reduce partial-update risk.
2. Replace remaining `datetime.utcnow()` defaults in GTFS models with timezone-aware alternatives.
3. Migrate GTFS SQLAlchemy models off legacy `Column(...)` style to modern typed declarative mappings.
4. Add retry/backoff behavior for scheduled daily aggregation triggering.
