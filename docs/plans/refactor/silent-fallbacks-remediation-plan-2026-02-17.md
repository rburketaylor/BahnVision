# Silent Fallbacks and Hidden Error Handling Remediation Plan

**Date:** 2026-02-17  
**Source audit:** Subagent code scan across backend, frontend, scripts, and CI workflow config  
**Goal:** Eliminate or instrument silent fallbacks so real failures are visible, actionable, and test-covered.

---

## Scope and Outcomes

This plan covers all currently identified issues where failures are swallowed, converted to success-like defaults, or made non-blocking without strong visibility.

Expected outcomes:

1. Runtime failures are no longer indistinguishable from valid empty states.
2. Intentional fallbacks are explicit and observable (logs, metrics, headers, or surfaced error state).
3. CI security/reliability checks no longer silently pass on failure by default.
4. Regression tests lock in expected behavior.

---

## Findings Tracker (All Issues in Scope)

| ID    | Severity    | File                                                           | Pattern summary                                                                 |
| ----- | ----------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------- | --- | ------ |
| SF-01 | High        | `backend/app/services/transit_data.py`                         | Broad exception handling returns `[]` for departure fetch failures.             |
| SF-02 | High        | `backend/app/services/gtfs_realtime_harvester.py`              | `_fetch_trip_updates` catches broad errors and returns empty updates.           |
| SF-03 | High        | `.github/workflows/ci.yml`                                     | `mutation-testing` job uses `continue-on-error: true`.                          |
| SF-04 | Medium-High | `backend/app/services/gtfs_realtime_harvester.py`              | `harvest_once` catches broadly and returns `0`, masking run failures.           |
| SF-05 | Medium      | `frontend/src/services/httpClient.ts`                          | JSON/text parse failures suppressed with empty fallback objects/strings.        |
| SF-06 | Medium      | `frontend/src/lib/recentSearches.ts`                           | `localStorage` failures swallowed; defaults returned silently.                  |
| SF-07 | Medium      | `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx` | Cluster expansion catch silently falls back to `easeTo`.                        |
| SF-08 | Medium      | `.github/workflows/ci.yml`                                     | `bandit`/`safety` steps use `                                                   |     | true`. |
| SF-09 | Medium      | `.github/workflows/ci.yml`                                     | `npm audit` step uses `                                                         |     | true`. |
| SF-10 | Medium      | `.github/workflows/ci.yml`                                     | `semgrep` step uses `                                                           |     | true`. |
| SF-11 | Low-Medium  | `frontend/src/pages/HeatmapPage.tsx`                           | `localStorage` read/write catches are silent.                                   |
| SF-12 | Low-Medium  | `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx` | Additional localStorage catches are silent.                                     |
| SF-13 | Low         | `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx` | Popup unmount failures only `console.warn`, no telemetry path.                  |
| SF-14 | Low         | `backend/app/main.py`                                          | Cache warmer startup/shutdown exceptions logged but not surfaced operationally. |

---

## Coordination Rules (Conflict-Free Parallel Work)

1. Single owner per file: only the assigned subagent edits each owned file.
2. No drive-by edits: do not modify files outside ownership unless integrator reassigns ownership first.
3. Cross-cutting behavior changes are coordinated through the integrator in small handoffs.
4. Tests follow ownership: each subagent adds/updates tests only under its owned area.
5. Integrator-only docs tracking: only integrator updates this plan file and final rollout notes.

---

## Subagents and Owned Files

### Integrator (orchestrates and merges)

**Owns**

- `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`
- Final merge conflict resolution and full-repo validation

**Responsibilities**

- Track progress for SF-01..SF-14.
- Enforce ownership boundaries.
- Run final combined verification and summarize rollout risks.

### Subagent A - Backend departures + app lifecycle

**Owns**

- `backend/app/services/transit_data.py`
- `backend/app/main.py`
- Backend tests directly related to these files (create/update targeted test files only)

**Implements**

- SF-01, SF-14

### Subagent B - Backend GTFS realtime harvesting

**Owns**

- `backend/app/services/gtfs_realtime_harvester.py`
- Backend tests directly related to harvester behavior

**Implements**

- SF-02, SF-04

### Subagent C - Frontend map + storage UX behavior

**Owns**

- `frontend/src/lib/recentSearches.ts`
- `frontend/src/pages/HeatmapPage.tsx`
- `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx`
- Frontend tests for the above files

**Implements**

- SF-06, SF-07, SF-11, SF-12, SF-13

### Subagent D - Frontend HTTP error diagnostics

**Owns**

- `frontend/src/services/httpClient.ts`
- HTTP client tests

**Implements**

- SF-05

### Subagent E - CI workflow reliability and security gates

**Owns**

- `.github/workflows/ci.yml`

**Implements**

- SF-03, SF-08, SF-09, SF-10

---

## Implementation Standards (Apply Across All Workstreams)

1. Do not swallow unknown exceptions silently.
2. Catch only expected exception types when fallback is truly required.
3. If fallback is intentional, emit at least one visibility signal:
   - structured log with context,
   - metric/event counter,
   - explicit response/header/UI state indicating degraded mode.
4. Preserve user-safe behavior while making failures diagnosable.
5. Add regression tests that fail if silent-swallow behavior returns.

---

## Workstream Instructions by Subagent

### Subagent A Instructions (SF-01, SF-14)

1. Refactor broad `except Exception` blocks in departure-fetch paths so outage/fetch errors are not translated into normal empty results by default.
2. Keep safe behavior for known non-fatal fallback paths, but add explicit observability for each fallback path.
3. For cache warmer lifecycle in `main.py`, decide and implement one explicit policy:
   - fail startup on warmer init failure, or
   - keep startup non-fatal but expose clear degraded-state signal.
4. Add/update tests proving:
   - true upstream failure no longer appears identical to valid empty departures,
   - startup/shutdown warmer failures are visible and asserted.

### Subagent B Instructions (SF-02, SF-04)

1. Split exception handling in harvester fetch and harvest flow by failure class (network/parsing/transient/internal).
2. Stop converting broad exceptions into empty updates / `0` success-like result without explicit failure signaling.
3. Ensure scheduler loop behavior remains resilient while still surfacing repeated failure conditions.
4. Add/update tests proving:
   - feed fetch failure path is distinguishable from valid empty feed,
   - `harvest_once` failure semantics are explicit and testable.

### Subagent C Instructions (SF-06, SF-07, SF-11, SF-12, SF-13)

1. Replace silent storage catches with explicit diagnostics path (at least controlled logging; telemetry if available).
2. Ensure storage failure behavior still avoids user crashes, but emits visible signal for debugging.
3. In cluster expansion path, retain functional map fallback while capturing and surfacing the cause.
4. Replace console-only warning for popup unmount with production-visible diagnostics path where available.
5. Add/update tests proving fallback behavior remains functional and diagnostics are emitted.

### Subagent D Instructions (SF-05)

1. Keep resilient parsing in `httpClient`, but stop erasing parse failure context.
2. Preserve raw error body and parsing error metadata in thrown error details.
3. Add/update tests proving malformed backend error payloads preserve diagnostic context.

### Subagent E Instructions (SF-03, SF-08, SF-09, SF-10)

1. Remove silent pass-through (`continue-on-error` / `|| true`) for mutation/security checks by default.
2. If a check must remain non-blocking temporarily, convert it to an explicit soft-fail pattern that still marks actionable warning status in CI summary.
3. Ensure SARIF/report upload behavior still runs with `if: always()` where needed, but does not mask scanner execution failures.
4. Validate workflow YAML syntax and job graph after edits.

---

## Execution Phases

### Phase 0 - Preparation (Integrator)

1. Create task board with SF-01..SF-14 status: `Todo`, `In Progress`, `Done`, `Deferred`.
2. Spawn Subagents A-E with exact ownership boundaries above.

### Phase 1 - High-risk backend error masking first

1. Subagent B completes SF-02/SF-04.
2. Subagent A completes SF-01.
3. Integrator runs targeted backend tests and resolves interface/behavior alignment.

### Phase 2 - Frontend hidden fallback paths

1. Subagent D completes SF-05.
2. Subagent C completes SF-06/SF-07/SF-11/SF-12/SF-13.
3. Integrator runs frontend unit tests and verifies UX does not regress.

### Phase 3 - CI reliability and security visibility

1. Subagent E completes SF-03/SF-08/SF-09/SF-10.
2. Integrator validates workflow semantics in PR and confirms failure visibility behavior.

### Phase 4 - Final integration and sign-off

1. Run full relevant test suites.
2. Confirm no ownership conflicts or dropped diagnostics.
3. Produce final remediation summary mapped to SF IDs.

---

## Verification Checklist

Backend:

- `pytest backend/tests -m "not integration"`
- Add focused tests for `transit_data` and harvester error semantics

Frontend:

- `cd frontend && npm run test -- --run`
- Add focused tests for `httpClient` and map/storage fallback diagnostics

CI config:

- Validate workflow edits via GitHub Actions on PR
- Confirm scanner failures are visible and not silently green

---

## Definition of Done

1. SF-01..SF-14 each marked `Done` or `Deferred` with explicit rationale.
2. No broad silent fallback remains in scoped files without diagnostics.
3. Tests exist for each changed fallback/error-handling path.
4. CI scanners and mutation tests no longer silently pass by default.
5. Final rollout note includes operational signals introduced (logs/metrics/headers/UI state).

---

## Suggested Subagent Kickoff Prompts

Use these prompts verbatim when spawning workers.

### Prompt - Subagent A

Implement SF-01 and SF-14 from `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`. You own only `backend/app/services/transit_data.py`, `backend/app/main.py`, and directly related backend tests. Do not edit any other files. Eliminate silent error masking while preserving safe behavior; add regression tests.

### Prompt - Subagent B

Implement SF-02 and SF-04 from `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`. You own only `backend/app/services/gtfs_realtime_harvester.py` and directly related backend tests. Do not edit any other files. Make harvester failures explicit and test-covered.

### Prompt - Subagent C

Implement SF-06, SF-07, SF-11, SF-12, and SF-13 from `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`. You own only `frontend/src/lib/recentSearches.ts`, `frontend/src/pages/HeatmapPage.tsx`, `frontend/src/components/features/heatmap/MapLibreHeatmap.tsx`, and directly related frontend tests. Do not edit any other files. Remove silent catches and keep user-safe fallbacks with diagnostics.

### Prompt - Subagent D

Implement SF-05 from `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`. You own only `frontend/src/services/httpClient.ts` and directly related tests. Do not edit any other files. Preserve resilience but keep parse failure diagnostics.

### Prompt - Subagent E

Implement SF-03, SF-08, SF-09, and SF-10 from `docs/plans/silent-fallbacks-remediation-plan-2026-02-17.md`. You own only `.github/workflows/ci.yml`. Do not edit any other files. Remove silent CI pass-through behavior while preserving report upload where appropriate.
