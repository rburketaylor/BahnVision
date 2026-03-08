# Principal Risk/Fraud Implementation Plan Pack

**Date:** 2026-02-27  
**Source:** `docs/zalando-principal-review.md` (role-fit improvement recommendations)

This folder contains coordinated workstream plans for the principal risk/fraud implementation effort.

## Files

- `principal-risk-fraud-master-plan-2026-02-27.md`: Integrator plan, milestones, and cross-track dependencies.
- `contracts/risk-scoring-interface-contract-2026-02-28.md`: Integrator-owned API/model interface contract between Workstreams A and B.
- `workstream-a-risk-scoring-slice-plan-2026-02-27.md`: Synthetic risk scoring system (data -> features -> scoring endpoint).
- `workstream-b-mlops-lifecycle-plan-2026-02-27.md`: Training/evaluation/versioning/drift/rollback loop.
- `workstream-c-operations-readiness-plan-2026-02-27.md`: SLOs, alerts, runbook, and postmortem assets.
- `workstream-d-security-hardening-plan-2026-02-27.md`: CSP hardening, CI security gate enforcement, and audit logs.

## Execution Order

1. Start with the master plan for ownership and sequencing.
2. Publish and lock `contracts/risk-scoring-interface-contract-2026-02-28.md` before implementation.
3. Run Workstreams A and D first (feature surface + security baseline).
4. Run Workstream B after A's feature and inference contracts exist and remain aligned with the locked contract.
5. Run Workstream C after A/B metrics and failure modes are visible.
