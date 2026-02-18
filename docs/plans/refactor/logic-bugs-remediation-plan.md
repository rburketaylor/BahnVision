# Logic Bugs Remediation Plan (Execution + Subagent Ownership)

**Date:** 2026-02-16  
**Source:** `docs/plans/logic-bugs-analysis.md`  
**Goal:** Implement (or explicitly defer with rationale) every item listed in the analysis, with regression tests and any necessary docs/API/client updates.

---

## Verification Status (2026-02-17)

- [x] Phase 0 tracker + decision log exists in `docs/plans/logic-bugs-analysis.md`.
- [x] Phases 1-4 item outcomes are recorded as `Done` or `Deferred` in `docs/plans/logic-bugs-analysis.md`.
- [x] Phase 5 type/LSP triage outcomes are recorded (`T1`-`T4`).
- [ ] Phase 6 full-regression revalidation is only partially verified in this pass.
- [x] Frontend regression gate passed in this verification run: `cd frontend && npm run test -- --run` (234 passed).
- [x] Targeted backend regression suites passed in this verification run: `pytest backend/tests/api/v1/shared/test_rate_limit.py backend/tests/services/test_gtfs_realtime_harvester.py -q` (36 passed).
- [ ] Full backend gate `pytest backend/tests -m "not integration"` was started but did not return a completion result in this verification run.

---

## Coordination Rules (Avoiding Conflicts)

1. **Single owner per file.** Only the assigned subagent edits an owned file.
2. **Cross-cutting changes are coordinated.** If an item requires changes across owned files, owners coordinate via the integrator and sequence changes to avoid merge churn.
3. **Docs tracker is integrator-owned.** Only the integrator updates status tracking in the analysis doc (or a follow-up tracker section).

---

## Subagents and Owned Files

Each file below has exactly one owner subagent. Other subagents may read these files but treat them as read-only.

### Integrator (coordination + final validation)

**Owns**

- `docs/plans/logic-bugs-analysis.md`
- `docs/plans/logic-bugs-remediation-plan.md`

**Responsibilities**

- Convert analysis items into a tracked checklist (Done/Deferred + rationale).
- Maintain a “decision log” for items marked as _Suggestion/Trade-off_.
- Resolve cross-agent sequencing and integration issues.
- Run final regression/test pass and ensure “Definition of Done” is met.

---

### Subagent A — Backend Cache + Heatmap Endpoints (shared semantics)

**Owns**

- `backend/app/services/cache.py`
- `backend/app/api/v1/endpoints/heatmap.py`

**Primary items (from analysis)**

- Critical: #1, #5
- High: #13
- Medium: #22, #26, #34, #35

**Why grouped**

- Cache single-flight behavior and heatmap endpoints interact directly (locking, cache headers, and error handling).

---

### Subagent B — Backend GTFS Realtime/Harvester + Import Lock

**Owns**

- `backend/app/services/gtfs_realtime_harvester.py`
- `backend/app/services/gtfs_realtime.py`
- `backend/app/services/gtfs_import_lock.py`

**Primary items (from analysis)**

- Critical: #2, #3
- High: #8
- Medium: #23, #24, #25, #29

**Why grouped**

- Concurrency/locking and realtime harvesting semantics are tightly coupled and easier to validate together.

---

### Subagent C — Backend Persistence + Models (DB/schema correctness)

**Owns**

- `backend/app/persistence/repositories.py`
- `backend/app/models/gtfs.py`
- `backend/app/models/transit.py`
- `backend/alembic/` (migrations)
- `backend/alembic.ini`

**Primary items (from analysis)**

- Critical: #4
- Medium: #30, #32, #33

**Notes**

- Any schema-affecting changes must include an Alembic migration and be called out explicitly.

---

### Subagent D — Backend Jobs + Aggregation/Service Logic

**Owns**

- `backend/app/jobs/gtfs_scheduler.py`
- `backend/app/jobs/rt_processor.py`
- `backend/app/jobs/heatmap_cache_warmup.py`
- `backend/app/services/daily_aggregation_service.py`
- `backend/app/services/gtfs_feed.py`
- `backend/app/services/heatmap_service.py`
- `backend/app/services/gtfs_schedule.py`
- `backend/app/services/station_stats_service.py`
- `backend/app/services/transit_data.py`

**Primary items (from analysis)**

- High: #6, #9, #10
- Medium: #20, #21, #27, #28
- Low (only if encountered in owned files): #51, #52

**Why grouped**

- Operational loops, backoff behavior, and aggregation correctness are best validated in one cohesive workstream.

---

### Subagent E — Frontend Hooks + Services

**Owns**

- `frontend/src/services/endpoints/transitApi.ts`
- `frontend/src/services/httpClient.ts`
- `frontend/src/hooks/useAutoRefresh.ts`
- Any frontend component files _only if_ they are changed to address the owned items (avoid incidental refactors).

**Primary items (from analysis)**

- Medium: #16, #38, #39, #40
- High: #19
- Low: #18, #54, #55, #56, #64

**Notes**

- “Suggestion” items should be either implemented (low risk) or explicitly deferred with rationale.

---

### Optional Subagent F — Transit API Endpoints (recommended if we want strict ownership)

**Owns**

- `backend/app/api/v1/endpoints/health.py`
- `backend/app/api/v1/endpoints/transit/departures.py`
- `backend/app/api/v1/endpoints/transit/stops.py`

**Primary items (from analysis)**

- High: #15
- Low: #46, #47, #49
- Low: #48

**Alternative**

- If fewer subagents are preferred, assign this file to Subagent A (endpoints-focused) and keep Subagent C limited to persistence/models/migrations.

---

## Execution Phases (Sequenced to Reduce Risk)

### Phase 0 — Tracker setup (Integrator)

**Outcomes**

- Add a simple status tracker for every numbered item in `docs/plans/logic-bugs-analysis.md`: `Todo / In progress / Done / Deferred`.
- Create a small decision log for “Suggestion/Trade-off” items.

---

### Phase 1 — Critical fixes first (A, B, C)

**Subagent A**

- Fix cache single-flight lock behavior under Valkey failures (#1) and lock release correctness (#26).
- Add single-flight locking to `/overview` endpoint (#5).
- Fix heatmap exception handling so HTTP exceptions aren’t masked (#13).

**Subagent B**

- Address TOCTOU import-lock race (#2).
- Replace `threading.Lock` usage in async context with `asyncio.Lock` and adjust call sites (#3).

**Subagent C**

- Remove internal commits from repository methods and update callers so transactions compose properly (#4).

**Acceptance gate**

- Backend unit tests pass: `pytest backend/tests -m "not integration"`.

---

### Phase 2 — High severity (D, E, A, B)

**Subagent D**

- Guard against 0/negative timeout tight-loop CPU spinning (#9).
- Add backoff on unexpected processing errors to reduce hammering (#28).
- Fix warmup task creation race / reentrancy (#10).

**Subagent B**

- Fix negative delay classification (early arrivals) (#8).

**Subagent A**

- Address heatmap cache write failure reporting semantics (#34) and service initialization patterns (#35), if still relevant after Phase 1 refactors.

**Subagent E**

- Replace raw `fetch()` in `getMetrics()` with centralized `httpClient` (#19).
- Decide and implement a reentrancy guard in `useAutoRefresh` if overlap can occur (#16).

**Acceptance gates**

- Frontend tests pass: `cd frontend && npm run test -- --run`.
- Backend job-loop tests cover timeout/backoff paths where feasible.

---

### Phase 3 — Medium severity + schema correctness (D, B, C, A, E)

**Subagent D**

- Fix daily summary threshold logic to avoid `.days` truncation (#20).
- Align route type filtering logic between hourly/daily paths (#21).
- Make daily aggregation atomic (avoid delete-then-insert data loss) (#27).

**Subagent A**

- Reduce overhead from cache cleanup frequency (#22).

**Subagent B**

- Align Lua TTL fallback literal with effective TTL source-of-truth (#23).
- Increase hash length / reduce collision risk (#24).
- Fix cancelled aggregation semantics to allow “uncancel” when appropriate (#25).
- Reduce repeated file open/lock checks in import-lock status (#29).

**Subagent C**

- Add missing FK constraint for `parent_station` with Alembic migration (#30).
- Review conflict handling that may hide data issues (#32).
- Add GTFS-spec constraints to Pydantic models where appropriate (#33).

**Subagent E**

- Improve `httpClient` diagnostics (capture raw text on JSON parse failure; preserve cause) (#38).
- Confirm/adjust retry policy for status code 0 behavior (#39).
- Normalize query keys where it meaningfully reduces surprises (#40).

**Acceptance gates**

- Backend typecheck (if used in CI) stays clean: `mypy --config-file backend/mypy.ini backend/app`.
- Frontend lint + typecheck pass: `cd frontend && npm run lint` and `cd frontend && npm run type-check`.

---

### Phase 4 — Low severity + explicit “Suggestion” decisions (Integrator + relevant owners)

**Outcomes**

- For each remaining low severity and “Suggestion” item: implement if low risk; otherwise mark Deferred with a concrete revisit criterion.

---

### Phase 5 — Type/LSP issues validation (Integrator + owners)

**Outcomes**

- Re-run real project checks (mypy/TS) and only fix issues that are confirmed runtime-affecting (not ORM typing artifacts).
- Document any confirmed-artifact findings in the tracker to prevent repeated churn.

---

### Phase 6 — Final regression + optional stress testing (Integrator)

**Minimum checks**

- `pytest backend/tests`
- `cd frontend && npm run test -- --run`

**Optional (time/environment permitting)**

- `cd frontend && npm run test:e2e`
- Add/extend concurrency tests for cache single-flight behavior and Valkey-down scenarios.

---

## Definition of Done

- Every numbered item in `docs/plans/logic-bugs-analysis.md` is marked **Done** or **Deferred** with a short rationale and a clear revisit criterion for deferrals.
- Each **Done** item has a regression test (or a documented reason why a test is impractical).
- Backend + frontend tests/type/lint commands pass per repository guidelines.
