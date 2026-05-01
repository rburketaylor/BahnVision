# Workstream C Plan: Principal Ops Artifacts

**Date:** 2026-02-27  
**Owns Problem IDs:** `FA-04`  
**Source:** `docs/zalando-principal-review.md` (role-fit improvement item 3)

## Mission

Add operations artifacts that show principal-level production ownership for the new risk scoring slice.

## Owned Files (Proposed)

- `backend/docs/operations/risk-scoring-slos.md`
- `backend/docs/operations/risk-scoring-runbook.md`
- `backend/docs/operations/risk-scoring-postmortem-incident-001.md`
- `observability/prometheus/rules/risk-scoring-alerts.yml`
- `observability/grafana/dashboards/risk-scoring-ops.json`
- `docs/plans/principal-risk-fraud-implementation/ops-evidence-index-2026-02-27.md`

## Problem Split

- `C-01`: Define SLOs and SLIs for latency, availability, and scoring freshness.
- `C-02`: Define alert rules with clear severity and routing intent.
- `C-03`: Provide runbook for triage, mitigation, and rollback.
- `C-04`: Provide a complete postmortem example with timeline and action items.
- `C-05`: Publish evidence index tying alerts/docs to implemented metrics/endpoints.

## Implementation Plan

### Phase C1 - SLO/SLI Baseline

1. Define service-level objectives (example: availability, p95 latency, error rate, stale model age).
2. Map each SLO to concrete metrics and alert conditions.
3. Document business impact and error budget policy.

Acceptance:

- Every SLO has an owner, measurement source, and alert mapping.
- No SLO uses undefined or unavailable metrics.

### Phase C2 - Alerting and Dashboard Artifacts

1. Add Prometheus alert rules for high error rate, latency breach, drift breach, and stale model version.
2. Add dashboard panels for request volume, p95 latency, score distribution, and drift status.

Acceptance:

- Alert rules load without syntax errors.
- Dashboard references real metric names.

### Phase C3 - Runbook and Postmortem

1. Author incident runbook with clear first 15-minute checklist.
2. Include rollback steps using Workstream B model-switch mechanism.
3. Write one realistic postmortem with root cause, impact, and prevention actions.

Acceptance:

- On-call runbook can be executed without tribal knowledge.
- Postmortem includes timeline, contributing factors, and ownership for follow-ups.

## Risks and Mitigations

- Risk: ops docs become aspirational and disconnected from code.
  - Mitigation: require each runbook step to cite concrete command/path/metric.
- Risk: alert fatigue from noisy thresholds.
  - Mitigation: start with paging vs ticketing severity split and tune after synthetic load tests.

## Validation Commands

- `python scripts/check_test_quality.py backend/tests`
- `pytest backend/tests -m "not integration"`
- `docker compose -f docker-compose.observability.yml config`
