# BahnVision Docs Overview

This directory centralises backend documentation. Start with the canonical tech spec in `docs/tech-spec.md`.

- `archive/` — historical backend docs (design doc, persistence branch plan, legacy tech spec). Use for context only.

No live architecture/product/operations subfolders live here today; add new backend-specific docs alongside this README and cross-link from `docs/tech-spec.md` when created.

Each subdirectory should own its README or index as content grows; cross-link updates belong in PR descriptions when docs move.

## Heatmap Live Mode

- The heatmap endpoint supports `time_range=live` to serve the latest GTFS-RT snapshot.
- Live responses include only currently impacted stations (delays/cancellations) and a `last_updated_at` timestamp.
- If no live snapshot exists (cold start or harvester stopped), the API returns HTTP 503 with a descriptive `detail` message.

## Heatmap Spatial Stratification

The heatmap uses **spatially stratified sampling** to ensure consistent network coverage across Germany, regardless of current disruption levels.

### Grid-Based Sampling

- The map is divided into virtual grid cells (~0.1° ≈ 10km per cell)
- **Tier 1 (Coverage)**: Each grid cell with data contributes at least one station (the most impacted in that cell)
- **Tier 2 (Density)**: Remaining slots are filled by the globally highest-impact stations
- This prevents the map from appearing empty during stable operations, while still highlighting problem areas

### Density Control

- `max_points` is bucketed by zoom level for cache stability:
  - Zoom < 10: 500 points
  - Zoom 10-11: 1000 points
  - Zoom ≥ 12: 2000 points
- `GRID_CELL_SIZE` constant controls grid resolution (default: 0.1°)

### Database

- Index `idx_gtfs_stops_location` on `(stop_lat, stop_lon)` supports efficient grid-based queries
- Uses PostgreSQL's `DISTINCT ON (grid_x, grid_y)` for tier-1 selection
