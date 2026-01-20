# Spatially Stratified Heatmap Sampling

## 1. Problem Statement

The current heatmap endpoint sorts stations by **"Impact Score"** (Cancellations + Delays) and truncates the list to a fixed `max_points` (e.g., 500–2000).

**Consequences:**

- In times of high system-wide stability, the map looks empty.
- During major disruptions in one region (e.g., Berlin S-Bahn), rural or healthy regions disappear entirely from the map as they are "pushed out" of the top-N list.

---

## 2. Proposed Solution: The "Grid Representative" Model

Instead of a global Top-N, we implement **Spatially Stratified Sampling**. We divide the map into a virtual grid. Each grid cell with any data is guaranteed at least one representative station on the map. The remaining capacity is filled with the highest-impact stations globally.

### Phase A: Backend Service Logic (`HeatmapService`)

Modify `_aggregate_station_data_from_db` to use a two-tiered selection strategy within a single SQL query:

1. **Virtual Gridding**: Use PostgreSQL `floor()` arithmetic on `stop_lat` and `stop_lon` to create bucket IDs (e.g., roughly 5km × 5km squares).

2. **Tier 1 (Coverage - Guaranteed)**: Select the "Primary Representative" for every grid cell that has observed departures.

3. **Tier 2 (Density - Impact)**: Select the remaining points (up to `max_points`) from the global pool, sorted by impact.

4. **SQL Implementation**: Use a Common Table Expression (CTE) with `ROW_NUMBER() OVER (PARTITION BY grid_x, grid_y ORDER BY total_departures DESC)` to identify representatives.

### Phase B: Frontend Filtering Alignment (`MapLibreHeatmap`)

Currently, the frontend filters out stations with 0 cancellations or 0 delays (Issue 1.C).

**Changes:**

- Modify `toGeoJSON()` in `MapLibreHeatmap.tsx` to allow "Healthy" points (0 impact) to be rendered.
- **Visual Styling**: Adjust the heatmap weight calculation so that healthy stations contribute a "Neutral" color (e.g., light blue/green) or a very low weight, ensuring they don't overpower the "Red" disaster zones.

### Phase C: Performance & Density Control

- **Zoom-Aware Gridding**: The grid resolution should scale with `zoom_level`. Low zoom (national view) = coarse grid; High zoom (city view) = fine grid.
- **Effective `max_points`**: Maintain the current `resolve_max_points` logic to ensure cache-key stability.
- **Cache Warmup**: Ensure the `HeatmapCacheWarmer` job continues to pre-calculate these stratified results in the background.

---

## 3. Technical Verification Points (For the Reviewing Agent)

| Point                       | Verification Required                                                                                                                                                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Complexity of Join**      | Verify if joining `RealtimeStationStats` and `GTFSStop` on the fly with `floor()` math is performant enough for PostgreSQL without a literal `grid_id` column. (Note: Total stations are < 20,000, so this should be trivial.) |
| **Window Function Support** | Confirm the project's SQLAlchemy/PostgreSQL version supports `OVER(PARTITION BY...)`.                                                                                                                                          |
| **UI Feedback**             | Determine if the "Healthy" stations should be visible as distinct dots or just subtle background heat.                                                                                                                         |
| **Issue 1.C Conflict**      | Ensure that including "Healthy" points doesn't break the user's ability to "Toggle Off Delays" (if the point has 0 delays but is shown for coverage, it should still respect the UI filter).                                   |

---

## 4. Expected Outcome

- **National View**: A solid "skeleton" of the German rail network is always visible, regardless of performance.
- **Local View**: Major clusters of delays still appear as intense "hotspots" in urban centers.
- **Performance**: Zero increase in API payload size; < 100ms impact on cold DB queries.

**Next Steps**: If verified, the implementation would begin by modifying `backend/app/services/heatmap_service.py` and the SQL generation logic within it.

---

## Plan Review: Spatially Stratified Heatmap Sampling

Overall, this is a well-thought-out plan that correctly identifies the core problem and proposes an appropriate solution. The following sections verify technical claims against the actual codebase.

### ✅ Technical Verification: Confirmed Correct

| Claim                              | Status     | Details                                                                                                                                                                                                                                                        |
| ---------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------------------------------------------- |
| **Window Function Support**        | ✅ Correct | The project uses SQLAlchemy 2.0.45 with asyncpg 0.31.0 on PostgreSQL. Window functions (`ROW_NUMBER() OVER (PARTITION BY...)`) are fully supported. SQLAlchemy's `func` module can express these via `func.row_number().over(partition_by=..., order_by=...)`. |
| **Station Count**                  | ✅ Correct | The claim that "total stations are < 20,000" is reasonable for GTFS Germany. The `floor()` arithmetic on lat/lon for virtual gridding should be trivial on this scale.                                                                                         |
| **`resolve_max_points` behavior**  | ✅ Correct | Correctly described (lines 98–114 of `heatmap_service.py`). The zoom-level-to-density bucketing is intentional for cache-key stability.                                                                                                                        |
| **Frontend filtering (Issue 1.C)** | ✅ Correct | The `toGeoJSON()` function (lines 220–234 of `MapLibreHeatmap.tsx`) filters out points where `cancellationRate > 0                                                                                                                                             |     | delayRate > 0` fails based on enabled metrics. |
| **`HeatmapCacheWarmer`**           | ✅ Correct | Exists and functions as described. It iterates over pre-defined `time_range` × `max_points` variants and explicitly stores results in cache.                                                                                                                   |

### ⚠️ Issues / Refinements to Consider

#### 1. Two-Query Strategy Already in Use

The plan proposes using a single CTE with `ROW_NUMBER()` for both tiers. However, the current implementation in `_aggregate_station_data_from_db` already uses a two-query strategy:

- **Query 1** (lines 383–422): Selects top-impacted stations with `.limit(max_points)`.
- **Query 2** (lines 441–471): Fetches per-route-type breakdown only for the selected station IDs.

**Decision Required:**

- Replace this with a single CTE approach (simpler, but Query 2 for by_transport breakdown would need restructuring).
- **Keep the two-query pattern** and just change Query 1 to the CTE-based tiered selection.

**Recommendation**: The latter is probably simpler and lower-risk.

#### 2. Grid Resolution Scaling (Zoom-Aware Gridding)

The plan mentions "Zoom-Aware Gridding" where grid resolution should scale with `zoom_level`. This is a significant detail that needs more specification:

- The backend currently receives `zoom_level` as a parameter but only uses it to resolve `max_points`.
- If grid cell size varies by zoom, you'll be multiplying cache key cardinality significantly (current warmup covers 3 `max_points` variants × N `time_ranges`; adding grid resolution would add another dimension).

**Recommendation**: Start with a fixed grid size (e.g., ~0.1° ≈ 10km at Germany's latitude) that works reasonably well across zoom levels, then iterate.

#### 3. Frontend "Healthy Point" Styling

The plan says healthy stations should render with "light blue/green" or very low weight. However:

- The current styling logic (`MapLibreHeatmap.tsx` lines 474–496, 588–602) uses an orange-to-red gradient for both the heatmap layer and markers.
- Adding a "healthy green/blue" color requires either:
  - A separate layer for healthy stations with different paint properties, or
  - Modifying the color expressions to use a diverging palette (blue → neutral → orange → red).

**Note**: This is a non-trivial UX/styling decision that should be prototyped first.

#### 4. Issue 1.C Conflict: Toggle Interaction

The plan correctly identifies this concern but doesn't resolve it. Specifically:

- If a station is included for "coverage" (0 cancellations, 0 delays), and the user toggles "Show only Delays", what happens?
  - Should the coverage station disappear (respecting the filter)?
  - Should it stay visible as a neutral/coverage indicator (breaking the filter semantic)?

**Recommendation**: Add a third UI state or toggle (e.g., "Show Coverage Skeleton") to make this behavior explicit to users.

#### 5. Performance Claim: "< 100ms impact on cold DB queries"

This is optimistic. The current queries don't use window functions, and adding `ROW_NUMBER() OVER (PARTITION BY floor(lat/0.05), floor(lon/0.05))` on ~10k–20k rows will add overhead. It should still be very fast on PostgreSQL with proper indexing, but:

- Verify there's an index on `(stop_lat, stop_lon)` in `GTFSStop` (or the computed grid columns, if you materialize them).
- The claim "zero increase in API payload size" is correct only if you still respect `max_points` total.

### 📝 Minor Clarifications / Naming Issues

1. **"Primary Representative" terminology**: The plan says Tier 1 selects the representative "by `total_departures DESC`". This means the **busiest** station in each grid cell, not the most impacted. Is that intentional? Consider whether "most impacted in grid cell" would be more consistent with the overall design goal.

2. The method name `_aggregate_station_data_from_db` is already quite long. Consider a separate helper like `_build_tiered_station_query()` to encapsulate the CTE logic.

---

## ✅ Summary: Proceed with Implementation

The plan is solid and addresses the stated problem correctly.

### Concrete Recommendations Before Implementation

1. **Clarify grid resolution strategy** (fixed vs zoom-aware) and document the tradeoff with cache cardinality.
2. **Prototype the frontend styling separately** to decide on healthy-point color treatment.
3. **Define explicit behavior** for how "coverage-only" stations interact with the metric toggles.
4. **Keep the two-query architecture** and only modify Query 1 with the CTE logic (lower risk).
5. **Add a brief index check** for `stop_lat/stop_lon` on `GTFSStop` before claiming performance numbers.
