# Workstream A Plan: Risk Scoring Demo Slice

**Date:** 2026-02-27  
**Owns Problem IDs:** `FA-01`  
**Source:** `docs/zalando-principal-review.md` (role-fit improvement item 1)

## Mission

Implement a small but real risk scoring domain path:

`synthetic transaction -> feature extraction -> risk score -> explainable response`

Contract dependency:

- Implement against `docs/plans/principal-risk-fraud-implementation/contracts/risk-scoring-interface-contract-2026-02-28.md`.

## Owned Files (Proposed)

- `backend/app/api/v1/endpoints/risk_scoring.py`
- `backend/app/services/risk_scoring/feature_extractor.py`
- `backend/app/services/risk_scoring/scoring_engine.py`
- `backend/app/models/risk_scoring.py`
- `backend/tests/api/v1/test_risk_scoring_endpoint.py`
- `backend/tests/services/test_risk_scoring_engine.py`
- Optional frontend surfacing:
  - `frontend/src/services/endpoints/riskApi.ts`
  - `frontend/src/pages/RiskScoringDemoPage.tsx`

## Problem Split

- `A-01`: Define a stable synthetic transaction schema and sample generator.
- `A-02`: Implement deterministic feature extraction with validation.
- `A-03`: Implement scoring engine with explanation payload (`top_features`, `score_band`, `reason_codes`).
- `A-04`: Expose endpoint with request/response contracts and error handling.
- `A-05`: Add tests for deterministic scores and edge-case behavior.

## Implementation Plan

### Phase A1 - Contracts and Seed Data

1. Confirm the integrator-owned contract document is published and unchanged for the current cycle.
2. Define request schema (`transaction`, `customer`, `context`) in implementation aligned to the contract.
3. Define response schema (`score`, `band`, `decision`, `explanations`, `model_version`) in implementation aligned to the contract.
4. Add fixture generator for synthetic requests.

Acceptance:

- Schema validation fails for missing required fields.
- Fixtures include low, medium, and high-risk examples.

### Phase A2 - Feature and Score Engine

1. Implement pure feature extraction from request payload.
2. Implement baseline scorer (weighted linear score with clamped output 0..1).
3. Emit deterministic reason codes from feature thresholds.

Acceptance:

- Same input always returns identical score and reason codes.
- Unit tests cover threshold boundary conditions.

### Phase A3 - API Surface

1. Add `POST /api/v1/risk/score` endpoint.
2. Return structured explanation fields and model version.
3. Include `X-Request-Id` behavior through existing middleware path.

Acceptance:

- API contract test passes for success and validation error cases.
- Response contains score, decision, and explanation fields for all valid requests.

### Phase A4 - Demo Surface (Optional but High Signal)

1. Add minimal frontend page that submits sample transaction and renders score details.
2. Wire typed API client and error state.

Acceptance:

- Demo can run locally and show at least three seeded scenarios.

## Risks and Mitigations

- Risk: scoring feels toy-like.
  - Mitigation: ensure explanations and thresholds map to business language.
- Risk: endpoint drifts from future model artifact format.
  - Mitigation: include `model_version` and feature list hash in response now.

## Validation Commands

- `pytest backend/tests/api/v1/test_risk_scoring_endpoint.py`
- `pytest backend/tests/services/test_risk_scoring_engine.py`
- `pytest backend/tests -m "not integration"`
