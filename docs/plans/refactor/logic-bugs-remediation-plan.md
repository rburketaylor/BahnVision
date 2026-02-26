# Logic Bugs Remediation Plan (Deferred Backlog + Handoff Contract)

**Date:** 2026-02-25  
**Source:** `docs/plans/refactor/logic-bugs-analysis.md`  
**Primary goal:** Resolve remaining deferred logic-bug findings (implement or explicitly defer with strong rationale), then hand implementation back for review.

---

## Read First

This plan supersedes the older phase-based execution sequence that assumed many critical/high items were still open.

Current reality:

- Most critical/high findings are already closed.
- Remaining work is mostly deferred low/medium items plus typing triage.
- Current environment may block frontend and mypy verification unless dependencies are restored.

Do not reopen already-completed items unless a regression is proven by test failure or reproducible behavior.

---

## Current Baseline (Verified 2026-02-25)

- Numbered findings: `35 Done / 8 Deferred`
- Type triage findings: `1 Done / 3 Deferred`
- Backend regression (`pytest backend/tests -m "not integration"`): PASS
- Frontend tests (`npm run test -- --run`): blocked in this environment (invalid/incomplete local Vitest install)
- Backend mypy gate: blocked in this environment (`mypy` not installed in active venv)

---

## Preflight Checklist (Required Before Any Code Changes)

1. Activate environment
   - `source .dev-env`
2. Confirm clean baseline branch
   - `git status --short`
3. Verify backend baseline still passes
   - `pytest backend/tests -m "not integration"`
4. Verify frontend tooling integrity
   - `cd frontend && npm ls vitest --depth=0`
   - If invalid/missing, run dependency restore in a network-enabled environment before continuing.
5. Verify mypy availability for T-items
   - `python3 -m mypy --version`

If steps 4 or 5 fail, continue only with tasks that do not require those gates, and document the exact blocker in handoff.

---

## Ownership and Scope Rules

- Modify only files required for the targeted finding IDs.
- Keep changes atomic by finding ID where feasible.
- Add/adjust tests in the same PR/commit group as the logic change.
- Update `docs/plans/refactor/logic-bugs-analysis.md` tracker status and notes for every touched finding ID.

---

## Work Packages

### WP1: #18 Stable departure row keys (Low)

**Goal**

Remove avoidable row remount risk in departures rendering by stabilizing row keys across real-time timestamp changes.

**Files**

- `frontend/src/components/features/station/DeparturesBoard.tsx`
- `frontend/src/tests/unit/DeparturesBoard.test.tsx`

**Implementation guidance**

1. Replace key derivation so it does not depend on mutable `realtime_departure`.
2. Keep key uniqueness deterministic for duplicate departures (same trip/stop/route edge cases).
3. Prefer stable domain identifiers first (`trip_id`, `stop_id`, `route_id`, scheduled/departure sequence signal).

**Acceptance criteria**

- No reliance on mutable realtime timestamps in list key generation.
- Existing sort/render behavior remains unchanged.
- Updated tests cover key stability behavior.

---

### WP2: #40 Normalize heatmap query keys (Medium, suggestion)

**Goal**

Use canonical query-key construction in `useHeatmap` to reduce ambiguity and future cache-key drift.

**Files**

- `frontend/src/hooks/useHeatmap.ts`
- `frontend/src/tests/unit/useHeatmap.test.tsx`

**Implementation guidance**

1. Introduce a tiny key-normalization helper local to the hook (or shared helper if already present).
2. Normalize only what matters:
   - omit `undefined` fields,
   - normalize array order where semantically order-insensitive (e.g. transport modes),
   - keep explicit primitives.
3. Keep API call behavior unchanged (`apiClient.getHeatmapData(params)` remains semantically identical).
4. Update tests that currently assert raw object identity in query keys.

**Acceptance criteria**

- Equivalent params produce equivalent query keys.
- Existing query behavior and refresh intervals remain unchanged.
- Tests validate canonicalized key shape.

---

### WP3: #49 Standardize readiness error shape (Low)

**Goal**

Make `/ready` response schema consistent enough for strict clients.

**Files**

- `backend/app/api/v1/endpoints/health.py`
- `backend/tests/api/v1/test_health.py`
- Optional docs if API contract text exists under `backend/docs/`.

**Implementation guidance**

1. Choose one stable contract and apply consistently:
   - either always include `errors` (empty `{}` on success), or
   - document explicit `errors` optionality and enforce via schema/docs.
2. Prefer minimal contract expansion over breaking changes.
3. Ensure status codes and existing readiness semantics stay unchanged.

**Acceptance criteria**

- Success and failure payloads follow documented schema rules.
- Health endpoint tests cover both success and failure shapes explicitly.

---

### WP4: #64 Canonical heatmap component path strategy (Low)

**Goal**

Resolve long-term duplicate path ambiguity between:

- `frontend/src/components/heatmap/*` (legacy compatibility layer)
- `frontend/src/components/features/heatmap/*` (canonical implementation)

**Files**

- `frontend/src/components/heatmap/*`
- `frontend/src/components/features/heatmap/*`
- Any imports touched during migration

**Implementation options**

1. **Recommended now:** Keep compatibility shims but enforce canonical imports for new/edited code.
2. **Optional full cleanup:** Migrate all imports to canonical path and remove legacy layer in one coordinated pass.

**Acceptance criteria**

- A documented path policy exists in code comments or contributing docs.
- If full cleanup is attempted, no stale imports remain.

---

### WP5: T1/T3/T4 Typing triage closure pass

**Goal**

Determine whether remaining type findings are real runtime risks or static-analysis artifacts; close findings accordingly.

**Files**

- `backend/app/jobs/gtfs_scheduler.py` (T1)
- `backend/app/services/gtfs_realtime_harvester.py` (T3)
- `backend/app/services/transit_data.py` (T4)
- related tests as needed

**Implementation guidance**

1. Run mypy in a fully provisioned environment.
2. For each finding, classify:
   - `Runtime-affecting` -> fix code and add regression test.
   - `Typing artifact` -> add narrowly-scoped type annotations/casts/comments (avoid behavior changes).
3. Avoid broad refactors in this pass.

**Acceptance criteria**

- Each T-item marked Done or Deferred with concrete evidence.
- If deferred, include explicit revisit trigger.

---

### WP6: Decision-only items (#53, #54, #55, #56)

**Goal**

Close decision debt with explicit criteria (implement now vs defer intentionally).

**Default recommendation**

- Keep deferred unless there is a direct product/perf/accessibility requirement in scope.

**Required output**

- For each ID, record one of:
  - `Done` with concrete change and tests, or
  - `Deferred` with explicit reopen trigger and owner.

---

## Regression and Validation Gates

Run what the environment allows; document blockers precisely.

### Required backend gates

1. `pytest backend/tests -m "not integration"`
2. If backend files changed significantly: `pytest backend/tests`

### Required frontend gates (if tooling available)

1. `cd frontend && npm run test -- --run`
2. `cd frontend && npm run lint`
3. `cd frontend && npm run type-check`

### Optional but recommended

1. `cd frontend && npm run test:e2e`
2. `pre-commit run --all-files`

---

## Required Handoff Package (Strict)

When implementation is complete, provide all of the following:

1. **Finding status matrix**
   - One line per targeted ID: `ID | Status | What changed | Why`
2. **File change inventory**
   - Exact paths changed, grouped by finding ID.
3. **Test evidence**
   - Commands run and pass/fail summary numbers.
   - Explicitly list blocked commands and root cause.
4. **Risk notes**
   - Any behavior changes with user-visible impact.
5. **Follow-up list**
   - Remaining deferred items and concrete reopen triggers.

If any finding remains ambiguous, do not claim completion; mark it deferred with clear rationale.

---

## Definition of Done for This Remediation Pass

- Every currently deferred finding is either:
  - implemented and tested (`Done`), or
  - intentionally deferred with explicit reopen criteria.
- Analysis tracker is updated in `docs/plans/refactor/logic-bugs-analysis.md`.
- Validation evidence is attached in handoff notes.
- No unrelated refactors are bundled into this pass.
