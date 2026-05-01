# BahnVision Docs Overview

This directory centralises backend documentation. Start with the canonical tech spec in `docs/tech-spec.md`.

- `archive/` — historical backend docs (design doc, persistence branch plan, legacy tech spec). Use for context only.

No live architecture/product/operations subfolders live here today; add new backend-specific docs alongside this README and cross-link from `docs/tech-spec.md` when created.

Each subdirectory should own its README or index as content grows; cross-link updates belong in PR descriptions when docs move.

## Local Runtime Security Defaults

- Docker Compose runtime hardening (network isolation for Postgres/Valkey, optional host access profile, and observability credential requirements) is documented in `docs/local-setup.md` and `docs/runtime-configuration.md`.
- Keep backend-focused operational docs in sync with those shared runtime docs when changing service defaults.

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

## GTFS-RT Monitoring

See `backend/docs/gtfs-rt-monitoring.md` for comprehensive documentation of:

- Status endpoints (`/api/v1/system/ingestion-status`, `/api/v1/health`, `/api/v1/ready`)
- Prometheus metrics for GTFS-RT harvesting
- Grafana dashboard configuration
- Harvester status field interpretation
- Recommended metrics, dashboard panels, and alerting rules for realtime data monitoring

## Configuration Changes

The following environment variables were added or updated as part of the efficiency optimization work:

- `GTFS_STOP_TIMES_IMPORT_MODE` (default: `streaming`) — Stop_times import strategy. `streaming` uses Polars lazy `sink_csv` followed by a single PostgreSQL `COPY` for lowest memory usage and fastest throughput. `batched` uses the legacy eager `read_csv_batched` with parallel COPY tasks.
- `GTFS_STOP_TIMES_BATCH_SIZE` (default: `500000`) — Batch size used when importing GTFS `stop_times.txt` in **batched** mode. In **streaming** mode this may be used as the sink batch size if the Polars streaming engine supports it. Tune upward on hosts with more memory.
- `GTFS_FEED_ARCHIVE_RETENTION_COUNT` (default: `2`) — Number of downloaded GTFS archive ZIPs to retain after successful imports. Set to `0` to keep only the current archive.
- `FALLBACK_CACHE_MAX_ENTRIES` (default: `1024`) — Maximum number of entries in the in-process fallback cache when Valkey is unavailable.
- `GTFS_RT_RETENTION_ENABLED` (default: `False`) — Enable validated historical GTFS-RT hourly retention cleanup. Must remain `False` until daily rollup parity has been verified in production.
