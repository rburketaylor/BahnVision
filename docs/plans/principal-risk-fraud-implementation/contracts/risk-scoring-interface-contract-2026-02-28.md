# Risk Scoring A<->B Interface Contract

**Date:** 2026-02-28  
**Owner:** Integrator  
**Consumers:** Workstream A (risk scoring API), Workstream B (MLOps/model loader)

## Purpose

Define the minimum stable contract between API/scoring implementation and model lifecycle implementation so tracks A and B can proceed without conflicting assumptions.

## API Request Contract (`POST /api/v1/risk/score`)

Required top-level fields:

- `transaction`
- `customer`
- `context`

Required `transaction` fields:

- `id` (string)
- `amount` (number, non-negative)
- `currency` (string)
- `timestamp` (RFC3339 string)

Required `customer` fields:

- `id` (string)
- `account_age_days` (integer, non-negative)

Required `context` fields:

- `channel` (string)
- `country_code` (string)

## API Response Contract

Required top-level fields:

- `score` (number, 0.0 to 1.0 inclusive)
- `band` (enum: `low`, `medium`, `high`)
- `decision` (enum: `approve`, `review`, `decline`)
- `explanations`
- `model_version` (string)
- `feature_set_hash` (string)

Required `explanations` fields:

- `reason_codes` (array of strings)
- `top_features` (array of objects with `name` and `value`)

## Error Contract

- Validation failures return HTTP 422 with FastAPI validation payload.
- Internal scoring/loader failures return HTTP 500 with stable machine-readable `detail`.

## Model Registry Contract

Version directory:

- `backend/model_registry/models/<model_version>/`

Required files per version:

- `manifest.json`
- model artifact file referenced by `manifest.json` `artifact_path`

Required `manifest.json` fields:

- `model_version` (string, must match directory name)
- `created_at_utc` (RFC3339 string)
- `training_data_version` (string)
- `feature_set_hash` (string)
- `algorithm` (string)
- `metrics` (object with deterministic evaluation outputs)
- `artifact_path` (string, relative path under version directory)

Active model pointer file:

- `backend/model_registry/active-model.json`
- Required fields: `active_model_version`, `updated_at_utc`

## Compatibility Rules

- Workstream A must always emit `feature_set_hash` in responses.
- Workstream B must refuse to load manifests missing required fields.
- If `feature_set_hash` in runtime expectations and manifest differ, loader must fail fast with clear error detail.

## Change Control

- Any contract change requires integrator approval and updates to both Workstream A and Workstream B plans in the same PR.
- Backward-incompatible changes require a new dated contract file and migration notes.
