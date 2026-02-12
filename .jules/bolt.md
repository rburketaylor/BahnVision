## 2025-05-18 - [Optimization] Redundant Datetime Calculations in Loops
**Learning:** `interval_to_datetime` in `gtfs_schedule.py` performs a `datetime.combine` operation which is relatively expensive when called inside a tight loop (e.g., iterating over thousands of departures).
**Action:** When processing lists of objects with date/time fields derived from a common base date, calculate the base datetime (e.g., midnight) once outside the loop and pass it down. This avoids O(N) object creations.
