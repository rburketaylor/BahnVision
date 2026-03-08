# Workstream D Plan: Security Posture Hardening

**Date:** 2026-02-27  
**Owns Problem IDs:** `FA-05`  
**Source:** `docs/zalando-principal-review.md` (role-fit improvement item 4)

## Mission

Raise security posture so the repo demonstrates intentional risk controls rather than best-effort checks.

## Owned Files (Proposed)

- `frontend/nginx.conf`
- `.github/workflows/ci.yml`
- `backend/app/api/v1/shared/dependencies.py`
- `backend/app/main.py` (if audit logging middleware is added)
- `backend/docs/security/risk-scoring-security-controls.md`
- `backend/tests/security/test_admin_audit_logging.py`
- `frontend/src/tests/security/csp-header.test.ts`

## Problem Split

- `D-01`: Reduce CSP permissiveness, especially `unsafe-eval` and broad `connect-src`.
- `D-02`: Convert non-blocking security scans into enforced or explicitly-governed gates.
- `D-03`: Add structured audit logging for privileged actions (who, what, when, request id, result).
- `D-04`: Add tests and docs proving controls are active.

## Implementation Plan

### Phase D1 - CSP Hardening

1. Audit required script and connect sources for current frontend runtime.
2. Remove unnecessary permissive directives.
3. Add documented temporary exceptions only when unavoidable.

Acceptance:

- CSP remains functional for app flows.
- Final policy removes or sharply restricts `unsafe-eval`.

### Phase D2 - CI Security Gate Enforcement

1. Review current workflow steps that use permissive patterns.
2. Change critical scans to fail the build on findings or execution errors.
3. Keep report upload steps on `if: always()` without masking scan failures.

Acceptance:

- CI clearly fails when configured scanners fail.
- Security summary still uploads artifacts for triage.

### Phase D3 - Privileged Action Audit Logging

1. Define audit event schema for privileged endpoints (admin and model-management actions).
2. Emit structured logs with request id and actor identity where available.
3. Document retention and redaction guidance in security docs.

Acceptance:

- Privileged requests emit one structured audit event per attempt.
- Tests validate both success and denied-access audit events.

## Risks and Mitigations

- Risk: stricter CSP breaks local dev or third-party tooling.
  - Mitigation: separate dev/prod policy with explicit reasoning and expiration for temporary exceptions.
- Risk: enabling hard CI gates increases short-term failures.
  - Mitigation: rollout by severity with explicit backlog for remaining non-blocking checks.

## Validation Commands

- `pre-commit run detect-secrets --all-files`
- `pre-commit run --all-files`
- `cd frontend && npm run test -- --run`
- `pytest backend/tests/security/test_admin_audit_logging.py`
