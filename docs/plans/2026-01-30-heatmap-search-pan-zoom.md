# Heatmap Search Pan/Zoom Notes

**Date:** 2026-01-30  
**Status:** Draft  
**Scope:** `frontend/src/pages/HeatmapPage.tsx`, `frontend/src/components/heatmap/*`

## Goal

Document a future enhancement where selecting a station in the heatmap search overlay pans/zooms the map (and optionally opens the station popup).

## Proposed UX

- Search remains a lightweight station picker with a "View Details" link.
- Optional enhancement: selecting a station pans/zooms the map to that stop.
- Optional enhancement: opening the popup when a station is selected.

## Implementation Sketch

- Pass `onStationSelect` from `HeatmapPage` to `HeatmapSearchOverlay`.
- Add a `focusStop` prop or imperative ref to `MapLibreHeatmap`:
  - `focusStop(stopId, lat, lon, zoom?: number)`
  - Optional: open popup by calling existing selection flow.
- Keep search-only link behavior as default if the pan/zoom API is not wired.

## Non-Goals

- No backend changes required.
- No changes to station search results or API.
