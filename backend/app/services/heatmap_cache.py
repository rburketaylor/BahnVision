"""
Heatmap cache helpers.

Centralizes cache key generation so warmup jobs and API handlers stay in sync.
"""

from __future__ import annotations

from app.models.heatmap import TimeRangePreset


def heatmap_cancellations_cache_key(
    *,
    time_range: TimeRangePreset | None,
    transport_modes: str | None,
    bucket_width_minutes: int,
    zoom_level: int,
    max_points: int | None,
) -> str:
    """Build the heatmap cancellations cache key.

    Note: `transport_modes` is intentionally not normalized here; we key on the
    raw query param to ensure identical requests share the same cache entry.
    """
    time_range_part = time_range or "24h"
    transport_part = transport_modes or "all"
    max_points_part: str | int = max_points if max_points is not None else "default"
    return (
        f"heatmap:cancellations:{time_range_part}:{transport_part}:"
        f"{bucket_width_minutes}:{zoom_level}:{max_points_part}"
    )
