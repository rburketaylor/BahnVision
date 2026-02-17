# Codebase Logic Bugs and Issues Analysis

**Date:** 2026-02-15 (original)  
**Verification Pass:** 2026-02-16  
**Scope:** Backend services, API endpoints, data models, background jobs, and frontend components

---

## Executive Summary

This analysis identifies subtle logic bugs, race conditions, and architectural issues across the BahnVision codebase. The issues range from critical race conditions that can cause data corruption to minor inconsistencies in error handling.

### Verification Notes (2026-02-16)

This document was triaged against the current repository state on 2026-02-16.

- Incorrect/outdated claims were removed to avoid future confusion.
- Remaining items are either confirmed issues (reproducible from source) or explicitly framed as suggestions/trade-offs.

---

## Execution Tracker (Added 2026-02-16)

**Execution plan:** `docs/plans/logic-bugs-remediation-plan.md`  
**Status values:** `Todo` / `In progress` / `Done` / `Deferred`

### Numbered Findings Tracker

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
|  18 | Departures row key includes realtime timestamp (suggestion) | LOW      | E     | Deferred | Out of owned files and currently no row-local state regression.                                       |
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
|  40 | Query key normalization (suggestion)                        | MEDIUM   | E     | Deferred | TanStack structural hashing already handles object keys; broader change deferred as low-value risk.   |
|  46 | Time range parameter mutation                               | LOW      | F     | Done     | Endpoint now uses `effective_time_range` instead of mutating input parameter.                         |
|  47 | Coordinate bucketing precision trade-off                    | LOW      | F     | Done     | Added adaptive nearby cache bucket precision by radius.                                               |
|  48 | Missing `max_length` for `stop_id`                          | LOW      | F     | Done     | Added `max_length=128` for query `stop_id`.                                                           |
|  49 | Error response shape variation                              | LOW      | F     | Deferred | Standardizing all endpoint error payloads is broader API-contract work; no immediate client breakage. |
|  51 | Hardcoded bucket width assumption                           | LOW      | D     | Done     | Daily aggregation source bucket width is now configurable input.                                      |
|  52 | Performance score magic numbers                             | LOW      | D     | Done     | Extracted weights/constants to named module-level constants.                                          |
|  53 | Exception group syntax requires Python 3.11+                | LOW      | D     | Deferred | Runtime baseline is already Python 3.11+ (current CI/dev image uses 3.12+).                           |
|  54 | Optional memoization                                        | LOW      | E     | Deferred | No demonstrated render-performance issue in affected components.                                      |
|  55 | Optional exit animations                                    | LOW      | E     | Deferred | Pure UX enhancement; deferred to dedicated design pass.                                               |
|  56 | Optional error styling                                      | LOW      | E     | Deferred | No active form UX bug requiring immediate styling change.                                             |
|  64 | Duplicate component locations                               | LOW      | E     | Deferred | Structural cleanup deferred to avoid mixed-scope refactor.                                            |

### Type/LSP Findings Tracker (Non-numbered follow-ups)

These are static-analysis findings; treat them as **triage items** until confirmed runtime-affecting.

|  ID | File                                              | Finding (short)                           | Owner | Status   | Notes                                                                                        |
| --: | ------------------------------------------------- | ----------------------------------------- | ----- | -------- | -------------------------------------------------------------------------------------------- |
|  T1 | `backend/app/jobs/gtfs_scheduler.py`              | SQLAlchemy truthiness typing artifact     | D     | Deferred | Runtime behavior verified; static typing artifact only in current usage.                     |
|  T2 | `backend/app/services/gtfs_feed.py`               | Possible `None` attribute typing artifact | D     | Done     | Connection-context close path now null-guarded.                                              |
|  T3 | `backend/app/services/gtfs_realtime_harvester.py` | Awaitable/None attribute typing issues    | B     | Deferred | Not reproduced as runtime bug during this remediation pass; keep as typing-triage follow-up. |
|  T4 | `backend/app/services/transit_data.py`            | Column vs value typing issues             | D     | Deferred | Treated as SQLAlchemy/LSP false positives in current query result flow.                      |

### Decision Log (2026-02-16 Execution)

- Deferred `#18` because the proposed key-stability change is in a non-owned component path and no current row-local state bug was observed.
- Deferred `#40` because TanStack Query already value-hashes object keys; normalization would be low-value churn without a concrete bug.
- Deferred `#49` because error-shape standardization is a cross-endpoint API-contract effort and was not required to fix a current regression.
- Deferred `#53` because supported runtime already satisfies Python 3.11+ requirements.
- Deferred `#54/#55/#56/#64` as optional UX/structure work without evidence of correctness impact.
- Deferred `T1/T3/T4` as static-analysis artifacts pending dedicated typing cleanup.

---

## Critical Issues (Immediate Action Required)

### 1. Race Condition in Cache Single-Flight Lock

**File:** `backend/app/services/cache.py:220-233`  
**Severity:** CRITICAL

When Valkey is unavailable (exception thrown), all concurrent workers set `acquired = True` and proceed, defeating single-flight protection and causing cache stampedes.

```python
except Exception:
    # If Valkey is unavailable, allow the operation to proceed
    acquired = True  # BUG: All workers proceed!
    break
```

**Recommendation:** Return `False` on exception to trigger fallback behavior rather than allowing all workers through.

---

### 2. TOCTOU Race in GTFS Import Lock Check

**File:** `backend/app/services/gtfs_realtime_harvester.py:342-407`  
**Severity:** CRITICAL

The harvester checks the import lock at multiple points. Between checking the lock and performing database operations, an import could start, causing deadlocks.

**Recommendation:** Use a single atomic check at the start of the operation or use database-level locking.

---

### 3. Threading.Lock in Async Context

**File:** `backend/app/services/gtfs_realtime.py:168-213`  
**Severity:** CRITICAL

Uses `threading.Lock()` instead of `asyncio.Lock()`, blocking the entire event loop when circuit breaker state is checked.

```python
self._circuit_breaker_lock = threading.Lock()  # Wrong lock type

def _check_circuit_breaker(self) -> bool:
    with self._circuit_breaker_lock:  # Blocks event loop!
```

**Recommendation:** Use `asyncio.Lock()` and make methods async.

---

### 4. Transaction Boundary Violations in Repository

**File:** `backend/app/persistence/repositories.py:330,392`  
**Severity:** CRITICAL

Repository methods call `await self._session.commit()` internally, breaking transaction composition. Callers cannot compose multiple operations in a single transaction.

**Recommendation:** Remove internal commits from repository methods; let callers control transaction boundaries.

---

### 5. Missing Single-Flight Lock in Overview Endpoint

**File:** `backend/app/api/v1/endpoints/heatmap.py:564-715`  
**Severity:** CRITICAL

Unlike the `/cancellations` endpoint which uses `cache.single_flight()`, the `/overview` endpoint lacks this protection. Under high load, this causes multiple concurrent database queries for the same data.

**Recommendation:** Add single-flight locking similar to the cancellations endpoint.

---

## High Severity Issues

### Backend Services

#### 6. Division by Zero in Coordinate Calculation

**File:** `backend/app/services/gtfs_schedule.py:291`  
**Severity:** HIGH

While there's a guard for `lat != 0`, `abs(lat)` near zero produces extremely large `lon_delta`. This is likely irrelevant for typical Germany latitudes, but it is brittle if used elsewhere.

**Recommendation:** Add a minimum threshold for `lat` (e.g., `max(abs(lat), 0.01)`).

---

#### 8. Status Classification Doesn't Handle Negative Delays

**File:** `backend/app/services/gtfs_realtime_harvester.py:931-939`  
**Severity:** HIGH

Trips arriving early (negative delay where `abs(delay) >= 60`) are classified as `STATUS_UNKNOWN` instead of on-time.

---

#### 9. Infinite Loop Risk with Zero/Negative Timeout

**File:** `backend/app/jobs/rt_processor.py:82-89`  
**Severity:** HIGH

If `gtfs_rt_timeout_seconds` is set to 0 or negative, `asyncio.wait_for()` fails immediately, causing tight-loop CPU spinning.

---

#### 10. Race Condition in Heatmap Cache Warmup Task Creation

**File:** `backend/app/jobs/heatmap_cache_warmup.py:63-69`  
**Severity:** HIGH

Check-then-act pattern on `_task` is not atomic. Multiple rapid calls to `trigger()` can create overlapping tasks.

---

### API Endpoints

#### 13. Incorrect Exception Handling Masking HTTP Exceptions

**File:** `backend/app/api/v1/endpoints/heatmap.py:515-519`  
**Severity:** HIGH

Any exception (including validation errors, database connection errors) is caught and wrapped in a generic 500 error, masking important error details.

---

#### 15. Inconsistent stop_id Validation

**File:** `backend/app/api/v1/endpoints/transit/departures.py:71-77`  
**Severity:** HIGH

The query parameter `stop_id` lacks the pattern validation that the path parameter has, allowing invalid stop IDs to pass through.

---

### Frontend

#### 16. No Reentrancy Guard in useAutoRefresh Hook (Suggestion)

**File:** `frontend/src/hooks/useAutoRefresh.ts:28-43`  
**Severity:** MEDIUM

`useAutoRefresh` calls `callback` on mount (optional) and then on an interval, but does not prevent a previous callback execution from overlapping the next tick. This is only a problem if the callback triggers work that must not overlap (e.g., async fetch without deduplication).

---

#### 18. DeparturesBoard Key Includes `realtime_departure` (Suggestion)

**File:** `frontend/src/components/features/station/DeparturesBoard.tsx:16-25`  
**Severity:** LOW

The `getDepartureKey` function includes `realtime_departure` in the key. If this value changes, React treats it as a different element and remounts instead of updating. This is usually fine (no preserved row state), but if row-local state is added later, consider using a more stable key.

---

#### 19. Inconsistent HTTP Client Usage

**File:** `frontend/src/services/endpoints/transitApi.ts:188-197`  
**Severity:** HIGH

The `getMetrics()` method bypasses the centralized `httpClient` and uses raw `fetch()`, missing timeout handling and consistent header management.

---

## Medium Severity Issues

### Backend Services

#### 20. Imprecise Daily Summary Threshold Check

**File:** `backend/app/services/heatmap_service.py:757`  
**Severity:** MEDIUM

Uses `.days` which truncates. A time range of 2 days and 23 hours returns `.days = 2`, so daily summaries won't be used even though it's nearly 3 full days.

**Recommendation:** Use total seconds: `(to_time - from_time).total_seconds() >= (_DAILY_SUMMARY_THRESHOLD_DAYS * 86400)`

---

#### 21. Route Type Filter Logic Inconsistent

**File:** `backend/app/services/heatmap_service.py:663-696` vs `1320-1354`  
**Severity:** MEDIUM

The hourly and daily summary paths apply route type filtering differently (SQL vs Python).

---

#### 22. Cleanup Called After Every Set Operation

**File:** `backend/app/services/cache.py:491`  
**Severity:** MEDIUM

`cleanup_expired()` is called after every `set_json` call, creating unnecessary overhead for high-write scenarios.

---

#### 23. Lua Script TTL Hardcoded

**File:** `backend/app/services/gtfs_realtime_harvester.py:80-178`  
**Severity:** MEDIUM

The Lua script contains a numeric fallback TTL literal, but the effective TTL is passed in via ARGV. If the fallback value is meant to mirror the Python constant, keep them aligned.

---

#### 24. Cache Key Collision Risk

**File:** `backend/app/services/gtfs_realtime_harvester.py:1306`  
**Severity:** MEDIUM

Using only 12 characters of MD5 hash creates collision risk. With the birthday paradox, collisions become likely with ~16 million trips.

---

#### 25. Inconsistent Delay Aggregation Logic

**File:** `backend/app/services/gtfs_realtime_harvester.py:607-608,651-668`  
**Severity:** MEDIUM

Delay uses `max()` but cancelled uses `or`. Once `cancelled=True`, it can never become `False` even if a later update uncancels.

---

#### 26. Single-Flight Lock Always Releases Even When Not Acquired

**File:** `backend/app/services/cache.py:239-244`  
**Severity:** MEDIUM

If an exception occurs during acquisition and `acquired` is set to `True`, the lock will be incorrectly deleted even though this worker didn't create it.

---

#### 27. Non-Atomic Delete-and-Insert Pattern

**File:** `backend/app/services/daily_aggregation_service.py:184-207`  
**Severity:** MEDIUM

If the insert fails after the delete succeeds, data is lost for that day.

---

#### 28. No Backoff on Processing Errors

**File:** `backend/app/jobs/rt_processor.py:77-78`  
**Severity:** MEDIUM

Unexpected exceptions only log the error, then immediately continue to the next iteration with the same timeout, hammering the service without backoff.

---

#### 29. File Lock Check Opens File Every Time

**File:** `backend/app/services/gtfs_import_lock.py:153-172`  
**Severity:** MEDIUM

This opens, locks, unlocks, and closes a file every time `is_import_in_progress()` is called, which is expensive.

---

### Data Models

#### 30. Missing Foreign Key Constraint

**File:** `backend/app/models/gtfs.py:29`  
**Severity:** MEDIUM

`GTFSStop.parent_station` is defined without a ForeignKey constraint to `gtfs_stops.stop_id`, despite being a self-referential relationship.

---

#### 32. Silent Conflict Handling May Hide Data Issues

**File:** `backend/app/persistence/repositories.py:267-274`  
**Severity:** MEDIUM

`link_departure_weather()` uses `on_conflict_do_nothing()` which silently ignores duplicate links, potentially masking bugs.

---

#### 33. Missing Validation Constraints on Pydantic Models

**File:** `backend/app/models/transit.py:22-25,36-42`  
**Severity:** MEDIUM

`wheelchair_boarding` and `route_type` use unconstrained `int` without GTFS spec validation.

---

### API Endpoints

#### 34. Cache Write Failure Not Handled Consistently

**File:** `backend/app/api/v1/endpoints/heatmap.py:705-713`  
**Severity:** MEDIUM

Cache write failures are logged but not reflected in response headers. The endpoint still sets `X-Cache-Status=miss`, so clients cannot distinguish “miss then cached” vs “miss with cache write failure”.

---

#### 35. Service Initialization on Every Background Refresh

**File:** `backend/app/api/v1/endpoints/heatmap.py:246-248`  
**Severity:** MEDIUM

A new `GTFSScheduleService` and `HeatmapService` are created for each background refresh task, not leveraging connection pooling.

---

### Frontend

#### 38. Improve httpClient Error Diagnostics (Suggestion)

**File:** `frontend/src/services/httpClient.ts:50,85-88`  
**Severity:** MEDIUM

The client prioritizes returning a structured `ApiError`. If richer diagnostics are desired (for debugging production failures), consider capturing raw response text when JSON parsing fails and preserving original errors as a `cause`.

---

#### 39. Confirm Retry Policy for Status Code 0 (Suggestion)

**File:** `frontend/src/hooks/useStationSearch.ts:21-33`  
**Severity:** MEDIUM

The hook retries “status 0” network failures while not retrying most 4xx errors. This is a reasonable policy; confirm it matches the intended UX and backend load expectations.

---

#### 40. Query Key Normalization (Suggestion)

**File:** `frontend/src/hooks/useHeatmap.ts:23`  
**Severity:** MEDIUM

Query keys include the raw `params` object. TanStack Query hashes keys by value, but normalizing the key to stable primitives (and stripping undefineds) can make behavior clearer and avoid surprises when params objects are constructed differently.

---

## Low Severity Issues

### Backend

46. **Time Range Parameter Mutation** (`stops.py:410`) - Mutates `time_range` parameter from "live" to "1h"
47. **Coordinate Bucketing Precision Trade-off** (`stops.py:283-284`) - Uses 3 decimal places for cache bucketing (intentional simplification)
48. **Missing max_length for stop_id** (`departures.py:71-77`)
49. **Error Response Shape Variation** (`health.py:69-77`) - Failure responses include extra `errors` fields; standardize only if clients need a fixed schema
50. **Hardcoded Bucket Width Assumption** (`daily_aggregation_service.py:115,152`)
51. **Performance Score Magic Numbers** (`station_stats_service.py:231-234`)
52. **Exception Group Syntax Only Works in Python 3.11+** (`gtfs_feed.py:136-141`)

### Frontend

54. **Optional Memoization** (`HeatmapControls.tsx`, `HeatmapLegend.tsx`) - Consider `useCallback`/`useMemo` only if renders become expensive
55. **Optional Exit Animations** (`dialog.tsx`) - Add explicit exit animation classes if desired
56. **Optional Error Styling** (`select.tsx`) - Add error styles if forms need it
57. **Duplicate Component Locations** - `components/heatmap/` vs `components/features/heatmap/`

---

## Recommendations by Priority

### Immediate (Critical)

1. Fix single-flight lock race condition in cache service
2. Fix import lock TOCTOU race in GTFS harvester
3. Replace threading.Lock with asyncio.Lock in realtime service
4. Remove internal commits from repository methods
5. Add single-flight locking to heatmap overview endpoint

### Short-term (High)

6. Implement backoff strategies for error loops
7. Fix cache stampede behavior when Valkey is down
8. Add size limits to fallback cache
9. Add reentrancy guards where needed (frontend/background jobs)

### Medium-term

11. Standardize error response formats
12. Improve input validation consistency
13. Add proper fallback for exception groups
14. Optimize cleanup frequency in cache service
15. Document magic numbers in calculations

---

## Testing Recommendations

1. Add stress tests for concurrent cache access
2. Test GTFS import behavior during crashes
3. Verify transaction rollback scenarios
4. Test frontend behavior with rapid user interactions
5. Add chaos testing for Valkey failures

---

## Existing Type Errors and LSP Issues

The following type errors were detected by the Language Server Protocol (LSP) during file operations. These are static-analysis findings; verify them against runtime behavior before treating them as production bugs.

### Backend Type Errors

#### 1. Invalid Conditional Operand in GTFS Scheduler

**File:** `backend/app/jobs/gtfs_scheduler.py:108:24`  
**Error:** `Invalid conditional operand of type "ColumnElement[bool] | Literal[False]"`

```
Method __bool__ for type "ColumnElement[bool]" returns type "NoReturn" rather than "bool"
```

**Note:** This appears to be a typing artifact (ORM attributes vs SQLAlchemy expressions). Confirm the code path is using actual model instances, not `ColumnElement`s, before changing logic.

---

#### 2. None Attribute Access in GTFS Feed

**File:** `backend/app/services/gtfs_feed.py:42:29`  
**Error:** `"close" is not a known attribute of "None"`

**Note:** This is often a typing artifact from “initialized to None, later assigned”. Confirm whether the attribute can be `None` at the call site.

---

#### 3. Awaitable Issues in GTFS Realtime Harvester

**File:** `backend/app/services/gtfs_realtime_harvester.py`

**Errors:**

- Line 1011: `"object" is not awaitable` - Attempting to await a non-coroutine object
- Line 1378: `"copy_to_table" is not a known attribute of "None"` - Calling method on potentially None object

**Note:** These frequently come from incomplete type stubs for third-party async clients and connections. Validate the concrete types returned in this code path before changing logic.

---

#### 4. Column Type Conversion Errors in Transit Data

**File:** `backend/app/services/transit_data.py`

**Multiple Errors:** Lines 468, 513, 514, 586, 677

```
Argument of type "Column[int]" cannot be assigned to parameter "x" of type "ConvertibleToInt"
Argument of type "Column[Decimal]" cannot be assigned to parameter "x" of type "ConvertibleToFloat"
```

**Note:** ORM instance attribute typing can look like `Column[...]` to the LSP. Confirm whether these are real `Column` objects or loaded values from query results.

---

## Additional Technical Debt

### Backend

1. **Python 3.11+ Dependency:** Exception group syntax (`except*`) only works in Python 3.11+
2. **PostgreSQL-Specific Features:** Using `postgresql_nulls_not_distinct=True` which may not port to other databases
3. **Hardcoded Time Constants:** Multiple magic numbers for timeouts, intervals, and TTLs
4. **Missing Type Annotations:** Several functions lack proper return type hints

### Frontend

1. **Mixed Import Paths:** Duplicate component structures in `components/heatmap/` and `components/features/heatmap/`
2. **Accessibility Audit (Suggestion):** Confirm dynamic components have appropriate keyboard/ARIA behavior
3. **Error Boundary Audit (Suggestion):** Confirm async UI flows surface failures consistently

---

## Removed Incorrect/Outdated Items (2026-02-16)

The following items were removed from the main list because the claim was not supported by the current codebase (or the referenced file/line did not match the described behavior):

- #7 (stale read after flush on upsert)
- #11 (stale import lock from crash)
- #12 (inconsistent import lock state)
- #14 (missing stats raises station_not_found)
- #17 (recent searches localStorage race)
- #31 (datetime.utcnow usage in `backend/app/models/gtfs.py`)
- #36 (limiter initialization race)
- #37 (harvester status None crash)
- #41-45 (frontend race/cleanup claims in hooks and MapLibre components)

---

_Originally generated by automated analysis; corrected and triaged on 2026-02-16 by manual source inspection._
