# BahnVision Docs Overview

This directory centralises backend documentation. Start with the canonical tech spec in `docs/tech-spec.md`.

- `archive/` — historical backend docs (design doc, persistence branch plan, legacy tech spec). Use for context only.

No live architecture/product/operations subfolders live here today; add new backend-specific docs alongside this README and cross-link from `docs/tech-spec.md` when created.

Each subdirectory should own its README or index as content grows; cross-link updates belong in PR descriptions when docs move.

## Heatmap Live Mode

- The heatmap endpoint supports `time_range=live` to serve the latest GTFS-RT snapshot.
- Live responses include only currently impacted stations (delays/cancellations) and a `last_updated_at` timestamp.
- If no live snapshot exists (cold start or harvester stopped), the API returns HTTP 503 with a descriptive `detail` message.
