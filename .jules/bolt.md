## 2025-02-14 - Redundant datetime.combine in Loops
**Learning:** `datetime.combine` is surprisingly expensive when called repeatedly in a tight loop (e.g., for every row in a large result set).
**Action:** Pre-calculate constant datetimes (like midnight) outside of loops and pass them to helper functions or constructors.
