# Workstream B Plan: Minimal MLOps Loop

**Date:** 2026-02-27  
**Owns Problem IDs:** `FA-02`, `FA-03`  
**Source:** `docs/zalando-principal-review.md` (role-fit improvement item 2)

## Mission

Create a minimal but complete ML lifecycle around the risk scoring slice:

`train -> evaluate -> register -> serve selected model -> detect drift -> rollback`

Contract dependency:

- Consume and honor `docs/plans/principal-risk-fraud-implementation/contracts/risk-scoring-interface-contract-2026-02-28.md` before implementing loader/registry logic.

## Owned Files (Proposed)

- `scripts/ml/train_risk_model.py`
- `scripts/ml/evaluate_risk_model.py`
- `scripts/ml/check_risk_drift.py`
- `backend/model_registry/README.md`
- `backend/model_registry/models/<model_version>/manifest.json`
- `backend/app/services/risk_scoring/model_loader.py`
- `backend/tests/ml/test_train_and_registry_flow.py`
- `backend/tests/ml/test_drift_detection.py`

## Problem Split

- `B-01`: Training pipeline from synthetic historical data.
- `B-02`: Evaluation report with baseline metrics and threshold gate.
- `B-03`: Lightweight model registry/version manifest contract.
- `B-04`: Runtime model selection and rollback switch.
- `B-05`: Drift report comparing recent live features vs training baseline.

## Implementation Plan

### Phase B0 - Contract Lock

1. Verify the integrator-owned contract document is published and approved for the cycle.
2. Confirm runtime feature extraction assumptions and model manifest fields match the contract.

Acceptance:

- Contract path is referenced in PR/task artifacts for B work.
- No implementation starts with unresolved A<->B contract gaps.

### Phase B1 - Training and Evaluation Scripts

1. Add repeatable training script that reads synthetic dataset and writes artifact.
2. Add evaluation script that computes precision/recall/auc or equivalent deterministic metrics.
3. Persist machine-readable report (`metrics.json`) per model version.

Acceptance:

- Running train + evaluate twice with same seed yields same metrics.
- Metrics report includes timestamp, data version, and feature hash.

### Phase B2 - Model Registry Contract

1. Define registry directory layout and manifest schema.
2. Store model artifact and metadata atomically per version.
3. Add "current model" pointer strategy (env var or symlink-free manifest pointer file).

Acceptance:

- Registry can hold multiple model versions concurrently.
- Model loader can resolve active model and fail clearly on missing artifacts.

### Phase B3 - Serving, Rollback, and Drift

1. Wire scoring engine to load active model from registry.
2. Add rollback command/path to switch active model safely.
3. Add drift check script and report (feature distribution delta and threshold status).

Acceptance:

- Rollback path swaps model version without code changes.
- Drift report clearly marks pass/fail per tracked feature.

## Risks and Mitigations

- Risk: heavyweight ML dependencies slow delivery.
  - Mitigation: start with a lean artifact format and only add dependencies if necessary.
- Risk: online/offline feature mismatch.
  - Mitigation: enforce shared feature extraction module used by both train and serve paths.

## Validation Commands

- `python scripts/ml/train_risk_model.py --help`
- `python scripts/ml/evaluate_risk_model.py --help`
- `python scripts/ml/check_risk_drift.py --help`
- `pytest backend/tests/ml`
