# Logic Bugs Analysis (Current State)

**Original analysis date:** 2026-02-15  
**Last verification pass:** 2026-02-27  
**Execution plan:** `docs/plans/refactor/logic-bugs-remediation-plan.md`  
**Scope:** Backend services, API endpoints, data models, jobs, and frontend hooks/services/components.

---

## Purpose

This is the source of truth for logic-bug remediation status.

- Treat this file as the status ledger (what is Done vs Deferred and why).
- Treat the remediation plan as the execution playbook.
- Do not treat historical sections from older versions of this document as active work unless they appear in the tracker below.

---

## Verification Snapshot (2026-02-27)

### Current status counts

- Numbered findings: **43 total**
  - **42 Done**
  - **1 Deferred**
- Type/LSP triage findings: **4 total**
  - **4 Done**
  - **0 Deferred**

### Commands run in this verification pass

1. Backend non-integration regression suite

   - Command: `source .dev-env && pytest backend/tests -m "not integration"`
   - Result: **PASS** (`511 passed, 36 skipped, 8 deselected`)

2. Frontend unit/integration regression suite

   - Command: `source .dev-env && cd frontend && npm run test -- --run`
   - Result: **PASS** (`33 files, 236 tests`)

3. Backend type check gate

   - Command: `source .dev-env && python3 -m mypy --config-file backend/mypy.ini backend/app`
   - Result: **PASS** (no errors reported)

4. Typing triage targeted runtime anchors (T1/T3/T4)

   - Command: `source .dev-env && pytest backend/tests/jobs/test_gtfs_scheduler.py backend/tests/services/test_gtfs_realtime_harvester.py backend/tests/services/test_transit_data.py -q`
   - Result: **PASS** (`86 passed`)

5. Readiness endpoint targeted tests

   - Command: `source .dev-env && pytest backend/tests/api/v1/test_health.py -q`
   - Result: **BLOCKED in this environment** (`5 skipped`; fixture requires available Valkey)

6. Frontend UX regression anchors for deferred UI items
   - Command: `source .dev-env && cd frontend && npm run test -- --run src/tests/unit/HeatmapControls.test.tsx src/tests/unit/HeatmapLegend.test.tsx src/tests/unit/Dialog.test.tsx src/tests/unit/Select.test.tsx`
   - Result: **PASS** (`4 files, 28 tests`)

### Environment notes from this pass

- Backend runtime/tooling currently reports Python `3.13.7`.
- Backend container baseline in repo is Python `3.13` (`backend/Dockerfile:1`).
- Frontend tooling integrity is restored in this workspace (`vitest` and full frontend test suite runnable).

---

## Numbered Findings Tracker

**Status values:** `Todo` / `In progress` / `Done` / `Deferred`

|  ID | Finding (short)                                             | Severity | Owner | Status   | Notes                                                                                                 |
| --: | ----------------------------------------------------------- | -------- | ----- | -------- | ----------------------------------------------------------------------------------------------------- |
|   1 | Cache single-flight lock Valkey failure                     | CRITICAL | A     | Done     | Lock acquisition failure now fails closed (no false acquire).                                         |
|   2 | GTFS import lock TOCTOU race                                | CRITICAL | B     | Done     | Import-lock checks consolidated and distributed acquire made atomic with NX.                          |
|   3 | `threading.Lock` used in async context                      | CRITICAL | B     | Done     | Circuit-breaker lock moved to `asyncio.Lock` and call paths made async-safe.                          |
|   4 | Repository internal `commit()` breaks transactions          | CRITICAL | C     | Done     | Internal commits removed from station repository upserts; callers own transaction boundary.           |
|   5 | Missing single-flight lock in `/overview`                   | CRITICAL | A     | Done     | `/overview` now uses single-flight + cache recheck under lock.                                        |
|   6 | Coordinate calc division-by-near-zero risk                  | HIGH     | D     | Done     | Longitude delta now derived from clamped cosine latitude factor.                                      |
|   8 | Status classification ignores negative delays               | HIGH     | B     | Done     | Delay classification now normalizes negatives to on-time threshold behavior.                          |
|   9 | Zero/negative timeout can cause tight loop                  | HIGH     | D     | Done     | Processing loop clamps to safe minimum timeout.                                                       |
|  10 | Heatmap warmup task creation race                           | HIGH     | D     | Done     | Trigger path now lock-protected; task pointer cleanup made deterministic.                             |
|  13 | Heatmap exception handling masks HTTP errors                | HIGH     | A     | Done     | Explicit `TimeoutError` -> 503 and `HTTPException` passthrough added.                                 |
|  15 | Inconsistent `stop_id` validation (query vs path)           | HIGH     | F     | Done     | Query `stop_id` now enforces same regex + length constraints.                                         |
|  16 | `useAutoRefresh` reentrancy guard (suggestion)              | MEDIUM   | E     | Done     | Async overlap guard added for callback execution.                                                     |
|  18 | Departures row key includes realtime timestamp (suggestion) | LOW      | E     | Done     | Row key now uses stable schedule/domain fields only; realtime timestamp removed from key derivation.  |
|  19 | `getMetrics()` bypasses `httpClient`                        | HIGH     | E     | Done     | `getMetrics()` now uses centralized `httpClient.requestText()`.                                       |
|  20 | Daily summary threshold uses `.days` truncation             | MEDIUM   | D     | Done     | Threshold now uses total-seconds based helper.                                                        |
|  21 | Route type filter logic differs hourly vs daily             | MEDIUM   | D     | Done     | Route filters now canonicalized across hourly/daily paths.                                            |
|  22 | Cache cleanup called on every set                           | MEDIUM   | A     | Done     | Fallback cleanup throttled to periodic execution.                                                     |
|  23 | Lua script TTL literal hardcoded (keep aligned)             | MEDIUM   | B     | Done     | Lua fallback TTL now generated from Python TTL constant.                                              |
|  24 | Trip hash too short (collision risk)                        | MEDIUM   | B     | Done     | Hash upgraded to SHA-256 with longer prefix.                                                          |
|  25 | Cancelled aggregation monotonic (`or`)                      | MEDIUM   | B     | Done     | Aggregation now supports uncancel transitions and consistent marker updates.                          |
|  26 | Single-flight releases even when not acquired               | MEDIUM   | A     | Done     | Release now only occurs when lock was actually acquired.                                              |
|  27 | Non-atomic delete-then-insert aggregation                   | MEDIUM   | D     | Done     | Daily aggregation wrapped in transaction/nested transaction context.                                  |
|  28 | No backoff on processing errors                             | MEDIUM   | D     | Done     | Exponential error backoff added to RT loop.                                                           |
|  29 | Import lock check opens file every call                     | MEDIUM   | B     | Done     | Probe handle reused across checks.                                                                    |
|  30 | Missing FK constraint for `parent_station`                  | MEDIUM   | C     | Done     | ORM FK added and Alembic migration `add_gtfs_parent_station_fk` created.                              |
|  32 | Silent conflict handling hides data issues                  | MEDIUM   | C     | Done     | Conflict handling changed to upsert/update and explicit insert-count behavior.                        |
|  33 | Missing GTFS constraints on Pydantic ints                   | MEDIUM   | C     | Done     | `wheelchair_boarding` and `route_type` bounds added.                                                  |
|  34 | Cache write failure not reflected in headers                | MEDIUM   | A     | Done     | Heatmap endpoints now emit `X-Cache-Status: miss-write-failed` on cache write failure.                |
|  35 | Heatmap services initialized per refresh task               | MEDIUM   | A     | Done     | Per-key refresh dedupe prevents overlapping refresh task creation.                                    |
|  38 | Improve `httpClient` error diagnostics (suggestion)         | MEDIUM   | E     | Done     | Added request context diagnostics + non-JSON error detail extraction.                                 |
|  39 | Confirm retry policy for status code 0                      | MEDIUM   | E     | Done     | Existing policy retained and now covered by explicit test.                                            |
|  40 | Query key normalization (suggestion)                        | MEDIUM   | E     | Done     | `useHeatmap` now canonicalizes query-key params (omit undefined/empty, normalize transport mode set). |
|  46 | Time range parameter mutation                               | LOW      | F     | Done     | Endpoint now uses `effective_time_range` instead of mutating input parameter.                         |
|  47 | Coordinate bucketing precision trade-off                    | LOW      | F     | Done     | Added adaptive nearby cache bucket precision by radius.                                               |
|  48 | Missing `max_length` for `stop_id`                          | LOW      | F     | Done     | Added `max_length=128` for query `stop_id`.                                                           |
|  49 | Error response shape variation                              | LOW      | F     | Done     | `/ready` now always includes `errors` (`{}` on success), with docs/tests aligned to this contract.    |
|  51 | Hardcoded bucket width assumption                           | LOW      | D     | Done     | Daily aggregation source bucket width is now configurable input.                                      |
|  52 | Performance score magic numbers                             | LOW      | D     | Done     | Extracted weights/constants to named module-level constants.                                          |
|  53 | Exception group syntax requires Python 3.11+                | LOW      | D     | Deferred | Runtime baseline is Python 3.13 today; portability to <3.11 is not currently required.                |
|  54 | Optional memoization                                        | LOW      | E     | Done     | Added targeted memoization for derived data/handlers in `HeatmapControls` and `HeatmapLegend`.        |
|  55 | Optional exit animations                                    | LOW      | E     | Done     | `Dialog` overlay/content now define explicit close-state animation classes.                           |
|  56 | Optional error styling                                      | LOW      | E     | Done     | `SelectTrigger` now supports invalid-state visual styling via `aria-invalid`/`data-invalid`.          |
|  64 | Duplicate component locations                               | LOW      | E     | Done     | Legacy shims retained; canonical import policy documented (`features/heatmap/*` for new/edited code). |

---

## Type/LSP Findings Tracker

These are static-analysis triage findings; they require runtime relevance proof before changing behavior.

|  ID | File                                              | Finding (short)                           | Owner | Status | Notes                                                                                                               |
| --: | ------------------------------------------------- | ----------------------------------------- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------- |
|  T1 | `backend/app/jobs/gtfs_scheduler.py`              | SQLAlchemy truthiness typing artifact     | D     | Done   | `mypy` target passes; scheduler regression suite passes (`backend/tests/jobs/test_gtfs_scheduler.py`).              |
|  T2 | `backend/app/services/gtfs_feed.py`               | Possible `None` attribute typing artifact | D     | Done   | Connection-context close path now null-guarded.                                                                     |
|  T3 | `backend/app/services/gtfs_realtime_harvester.py` | Awaitable/None attribute typing issues    | B     | Done   | `mypy` target passes; harvester regression suite passes (`backend/tests/services/test_gtfs_realtime_harvester.py`). |
|  T4 | `backend/app/services/transit_data.py`            | Column vs value typing issues             | D     | Done   | `mypy` target passes; transit-data regression suite passes (`backend/tests/services/test_transit_data.py`).         |

---

## Deferred Findings Deep Dive (Current Code Evidence)

### #53 Python 3.11+ exception-group syntax

- Current code: `backend/app/services/gtfs_feed.py:139,173`
- Environment evidence: `backend/Dockerfile:1` uses Python `3.13`.
- Current decision: deferred as non-issue under supported runtime baseline.
- Reopen trigger: requirement to support Python `<3.11` in local/dev/CI/runtime images.

## Regression Anchors for Already-Closed High-Risk Items

Use these test areas as guards before touching related logic:

- Cache/single-flight safety: `backend/tests/services/test_cache_compatibility.py`
- Heatmap endpoint lock/cache behavior: `backend/tests/api/v1/test_heatmap.py`
- Realtime harvester import-lock + status aggregation: `backend/tests/services/test_gtfs_realtime_harvester.py`
- Processor timeout/backoff loop: `backend/tests/jobs/test_rt_processor.py`
- Schedule near-equator lon delta guard: `backend/tests/services/test_gtfs_schedule.py`
- Parent station FK/model correctness: `backend/tests/models/test_gtfs.py`
- Departures row-key stability: `frontend/src/tests/unit/DeparturesBoard.test.tsx`
- Heatmap query-key canonicalization: `frontend/src/tests/unit/useHeatmap.test.tsx`
- Heatmap controls/legend UX behavior: `frontend/src/tests/unit/HeatmapControls.test.tsx`, `frontend/src/tests/unit/HeatmapLegend.test.tsx`
- Dialog + select UX primitives: `frontend/src/tests/unit/Dialog.test.tsx`, `frontend/src/tests/unit/Select.test.tsx`

---

## Decision Log (Updated 2026-02-27)

- The old “Critical/High issues” narrative sections from earlier versions were removed from this version because they described already-remediated items as active defects.
- Deferred items now remaining in numbered tracker are intentionally deferred unless their listed reopen triggers are met: `#53`.
- This pass closed `#18`, `#40`, `#49`, `#54`, `#55`, `#56`, `#64`, and `T1/T3/T4` with implementation + test evidence.
- Frontend tooling and backend mypy gates are runnable again in this workspace.

---

_This document is intentionally status-focused and execution-safe for handoff. Use the remediation plan for implementation sequencing and handoff requirements._
