# Principal Risk/Fraud Implementation Master Plan

**Date:** 2026-02-27  
**Source:** `docs/zalando-principal-review.md` (section: role-fit improvement recommendations)

## Goal

Ship the smallest end-to-end set of additions that materially improves principal-level evidence for:

1. Risk scoring product shape
2. MLOps lifecycle ownership
3. Production operations rigor
4. Security posture hardening

## Current State (Inherited + Spot-Checked on 2026-02-28)

Baseline inherited from `docs/zalando-principal-review.md` and spot-checked against repository state:

- No risk/fraud scoring pipeline is implemented.
- No training/evaluation/registry/drift monitoring loop is implemented.
- Ops artifacts (SLOs, incident runbook/postmortem) are limited.
- Security has known gaps (CSP permissiveness, non-blocking scanner steps, limited audit trail patterns).

Spot-check evidence:

- CSP currently includes `unsafe-eval` and broad `connect-src` in `frontend/nginx.conf`.
- Non-blocking scanner patterns (`|| true`) exist in `.github/workflows/ci.yml`.
- No structured privileged-action audit logging path exists yet in `backend/app/api/v1/shared/dependencies.py` and `backend/app/main.py`.

## Problem Breakdown

- `FA-01`: No risk scoring domain slice (events -> features -> score -> decision evidence).
- `FA-02`: No model lifecycle (train, evaluate, version, deploy, rollback).
- `FA-03`: No drift/data-quality feedback loop.
- `FA-04`: No principal-level operational artifacts tied to live service behavior.
- `FA-05`: Security posture does not align with stricter risk/payments expectations.

## Workstream Topology

| Workstream                  | Owns                                                                    | Problem IDs  |
| --------------------------- | ----------------------------------------------------------------------- | ------------ |
| Integrator                  | Cross-track contracts, sequencing, final validation                     | All          |
| A - Risk Scoring Demo       | Synthetic events, feature extraction, scoring API                       | FA-01        |
| B - MLOps Loop              | Training, evaluation, model registry/versioning, rollback, drift checks | FA-02, FA-03 |
| C - Principal Ops Artifacts | SLOs, alerts, runbook, postmortem + ops docs                            | FA-04        |
| D - Security Posture        | CSP, CI security gate behavior, privileged action audit logs            | FA-05        |

## Coordination Rules

1. Single owner per file in each workstream plan.
2. Integrator owns interface contracts and conflict resolution.
3. No drive-by edits outside owned files without reassignment.
4. Every merged track must include tests or executable validation commands.
5. Every track must produce artifacts that can be cited in interviews and PR narrative.

## Execution Phases

### Phase 0 - Contract Baseline (Integrator)

1. Freeze a minimal API contract for scoring: request schema, response schema, decision explanation fields.
2. Freeze model artifact contract: version, feature set hash, training metadata.
3. Publish the versioned cross-track contract document at `docs/plans/principal-risk-fraud-implementation/contracts/risk-scoring-interface-contract-2026-02-28.md`.
4. Create tracker board for `FA-01` to `FA-05`.

Exit criteria:

- Interface contracts are published and referenced by Workstreams A and B.
- Workstream ownership acknowledged.

### Phase 1 - Feature Surface + Security Baseline (Workstreams A + D in parallel)

1. Workstream A delivers synthetic risk stream and scoring endpoint.
2. Workstream D removes highest-risk security gaps that could block adoption.

Exit criteria:

- Scoring API works with deterministic test cases.
- Security gates and CSP changes are validated and documented.

### Phase 2 - MLOps Loop (Workstream B)

1. Add training/evaluation artifact generation and versioning.
2. Add model selection and rollback path.
3. Add drift check job/report for synthetic production data.

Exit criteria:

- Reproducible train -> evaluate -> register -> serve path exists.
- Drift report and rollback procedure are executable.

### Phase 3 - Principal Ops Artifacts (Workstream C)

1. Define SLOs and alert rules mapped to scoring service signals.
2. Add runbook for incident response and rollback.
3. Add one concrete postmortem template filled from a realistic incident scenario.

Exit criteria:

- Ops artifacts are complete and actionable.
- Alerts reference real metrics exposed by the service.

### Phase 4 - Integration and Evidence Packaging (Integrator)

1. Validate all commands in this plan set.
2. Produce a single evidence index for interview use.
3. Confirm docs and API references are in sync.

Exit criteria:

- All problem IDs closed or explicitly deferred with rationale.
- Evidence index can point to code, metrics, and runbooks without gaps.

## Deferral Policy

A problem or workstream task is "explicitly deferred" only if all required fields below are documented in the master plan or linked tracking artifact.

Allowed deferral reasons:

- External dependency unavailable (service/tooling/data outside repo control)
- Security or reliability risk judged unacceptable for current release window
- Missing prerequisite contract or upstream artifact not delivered
- Intentional scope cut approved by integrator to protect critical-path delivery

Required deferral record fields:

- `item_id`: problem ID or sub-task ID
- `owner`: directly responsible person
- `reason`: one of the allowed reasons above
- `impact`: user/system impact of not completing now
- `compensating_control`: temporary mitigation in place
- `revisit_by`: concrete date for reassessment
- `exit_criteria`: objective condition that closes the deferment

Completion vs deferment criteria:

- Completed: acceptance criteria met and listed validation commands pass.
- Deferred: required record fields completed and compensating control verified.

## Suggested Artifact Targets

- Backend service: `backend/app/api/v1/endpoints/risk_scoring.py`, `backend/app/services/risk_scoring/`
- ML workflow: `scripts/ml/`, `backend/model_registry/`, `backend/tests/ml/`
- Ops assets: `backend/docs/operations/`, `observability/prometheus/`
- Security updates: `frontend/nginx.conf`, `.github/workflows/ci.yml`, backend privileged-action logging paths

## Validation Commands (Final Integration)

- `pytest backend/tests`
- `cd frontend && npm run test -- --run`
- `cd frontend && npm run lint`
- `pre-commit run --all-files`

## Deliverables Checklist

- [ ] Workstream A plan executed or explicitly deferred.
- [ ] Workstream B plan executed or explicitly deferred.
- [ ] Workstream C plan executed or explicitly deferred.
- [ ] Workstream D plan executed or explicitly deferred.
- [ ] Final evidence index added to docs with links to implementation artifacts.
