# Frontend Heatmap Audit & Fix Plan

**Date:** 2026-01-25  
**Status:** Draft  
**Scope:** `frontend/src/pages/HeatmapPage.tsx` and `frontend/src/components/heatmap/*` (MapLibre heatmap)

## Summary

The heatmap UI is functional but has several correctness and UX issues in its current “overview points + on-demand station details” architecture. The most impactful problems are: metric toggles not affecting the visualization, a likely heatmap rendering bug due to clustering, and a broken retry path in the map error boundary.

## Findings

### 1) Metric toggles don’t affect overview visualization (high)

- `HeatmapPage` uses `useHeatmapOverview` and passes only `time_range` + `transport_modes` (no enabled metrics), so toggling cancellations/delays does not change the API request or returned points (`frontend/src/pages/HeatmapPage.tsx:86`).
- `overviewToGeoJSON` explicitly assumes “filtering by metric happens at API level”, but no metric selector exists in the `getHeatmapOverview` request shape (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:344`, `frontend/src/services/endpoints/transitApi.ts:164`).

**Impact:** UI controls appear to work (title/legend/stats change), but the map content likely remains unchanged, which is misleading.

### 2) Transport filter UX is inconsistent (medium)

- “None” sets `selectedTransportModes` to `[]` (`frontend/src/components/heatmap/HeatmapControls.tsx:78`).
- An empty list is interpreted as “all selected” for each badge and the UI displays “Showing all transport types” (`frontend/src/components/heatmap/HeatmapControls.tsx:215`, `frontend/src/components/heatmap/HeatmapControls.tsx:236`).

**Impact:** Users cannot express “no transport types”; “All” and “None” are confusingly equivalent.

### 3) Heatmap layer likely breaks at low zoom due to clustering (high)

- The map source driving the heatmap layer is configured with `cluster: true` (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:595`).
- The heatmap layer reads `['get', 'intensity']` as its weight from that clustered source (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:623`).
- Cluster features do not have per-point `intensity` (only cluster metadata like `point_count` and any `clusterProperties` such as `intensity_sum`).

**Impact:** The heatmap can be blank or incorrect at zooms where most points are clustered.

### 4) Map “Retry” path may not recreate the map (high)

- The error boundary `onReset` removes the map and only updates `mapKey` (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:1152`).
- Map initialization is in an effect that only reruns on theme change (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:528`), so pressing Retry can leave the UI in a “no map” state.

**Impact:** Users can get stuck if the map initialization fails once.

### 5) Overview-point detection uses falsy checks (medium)

- `isOverviewPoint` is determined via `!props.cancellation_rate && !props.delay_rate && props.intensity !== undefined` (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:867`).
- Legitimate `0` values are falsy and will be treated as “missing”, misclassifying full-data points as overview points.

**Impact:** Clicking a station with 0% cancels/delays can incorrectly trigger “loading details…” flow.

### 6) Full-data validation contradicts types (medium)

- `HeatmapDataPoint.delayed_count` is optional (`frontend/src/types/heatmap.ts:39`), but `validateHeatmapData` requires `typeof point?.delayed_count === 'number'` (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:202`).

**Impact:** Cancellation-only responses (no delay fields) can be filtered out and render as “no data”.

### 7) Search overlay isn’t integrated with map navigation (medium)

- `HeatmapSearchOverlay` supports `onStationSelect` and claims it can zoom the map, but `HeatmapPage` mounts it without props (`frontend/src/pages/HeatmapPage.tsx:277`).
- `MapLibreHeatmap` has no prop/imperative API for “fly to this stop”.

**Impact:** Search works as a station picker + link, but does not actually drive the map view.

### 8) Global console.warn suppression is not restored (low)

- `setupWebGLWarningSuppression` overwrites `console.warn` in development and never restores it on unmount (`frontend/src/components/heatmap/MapLibreHeatmap.tsx:402`).

**Impact:** Can hide other warnings in dev sessions; hard to debug unrelated issues.

## Plan (Proposed Fixes)

### Phase 1 — Correctness fixes (must-do)

1. **Metric toggles:** Define the intended behavior for overview points:
   - **Preferred:** add an API param (e.g., `metrics=cancellations|delays|both`) or equivalent, and plumb it through `useHeatmapOverview` → `getHeatmapOverview` → backend.
   - **Fallback:** fetch both metrics and filter client-side consistently (may increase payload).
2. **Heatmap rendering:** Separate clustered vs non-clustered sources:
   - Use a non-clustered source for the heatmap layer.
   - Keep a clustered source for cluster circles/count labels and point markers.
3. **Retry:** Make retry re-run map initialization reliably (e.g., include `mapKey` in the init effect dependencies or refactor init into a function invoked by both the effect and retry).
4. **Overview detection:** Replace falsy checks with explicit “property exists + is number” checks.
5. **Validation:** Align `validateHeatmapData` with `HeatmapDataPoint` types (allow missing delay fields).

### Phase 2 — UX coherence (should-do)

1. **Transport filter semantics:**
   - Decide whether `[]` means “all” or “none” and make the UI + API behavior consistent.
   - If `[]` means “all”, relabel “None” to “Reset” (or remove it) and add a real “none” state if needed.
2. **Search → map integration:**
   - Pass `onStationSelect` from `HeatmapPage` to `HeatmapSearchOverlay`.
   - Add a `flyToStop`/`focusStop` capability in `MapLibreHeatmap` (prop callback or imperative ref) so selecting a stop pans/zooms the map.

### Phase 3 — Cleanup & hardening (nice-to-have)

1. Restore `console.warn` on unmount (dev-only).
2. Remove unused style-transition state or implement actual style transitions.
3. Consider consolidating or documenting map style configuration (currently uses CARTO style URLs, not `config.mapTileUrl`).

## Acceptance Criteria

- Toggling cancellations/delays changes the data shown on the map (not just legend/title).
- Heatmap rendering is visible and stable at country-level zoom (clusters should not blank the heatmap layer).
- Retry after a map initialization error restores a working map.
- Transport filter UI behavior matches what is actually sent to the API and rendered.
- Selecting a station in search pans/zooms the map and (optionally) opens that station’s details.

## Test Plan

- Unit tests:
  - Add/adjust tests around overview metric filtering and map-layer source setup (`frontend/src/tests/unit/MapLibreHeatmap.test.tsx`).
  - Add a regression test for Retry recreating the map.
  - Add tests for transport filter semantics (“All” vs “None”).
- Manual checks:
  - Verify heatmap is visible at zoom ~6 and remains visible while zooming.
  - Toggle metrics and confirm points/heatmap change accordingly.
  - Use search to focus a station and confirm the map moves.
