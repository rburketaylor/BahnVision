## 2025-05-24 - Redundant DateTime Calculations in Loops
**Learning:** `datetime.combine` inside loops processing database rows significantly impacts performance. Moving constant date calculations outside the loop yielded a ~5x speedup for the transformation function.
**Action:** Always check helper functions called in loops for constant calculations that can be lifted out.
