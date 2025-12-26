"""
Heatmap cache helpers.

Centralizes cache key generation so warmup jobs and API handlers stay in sync.
"""

from __future__ import annotations

from app.models.heatmap import TimeRangePreset


def _normalize_transport_modes_part(transport_modes: str | None) -> str:
    """Normalize the transport_modes query param for cache-key stability.

    Semantically identical requests should share a cache entry even if callers
    provide different ordering or whitespace.
    """
    if not transport_modes:
        return "all"

    parts = [p.strip().upper() for p in transport_modes.split(",")]
    parts = [p for p in parts if p]
    if not parts:
        return "all"

    # De-dupe while keeping stable ordering (sorted) for cache key stability.
    return ",".join(sorted(set(parts)))


def heatmap_cancellations_cache_key(
    *,
    time_range: TimeRangePreset | None,
    transport_modes: str | None,
    bucket_width_minutes: int,
    max_points: int,
) -> str:
    """Build the heatmap cancellations cache key.

    Note: The cache key uses a normalized transport_modes value and keys on the
    *effective* max_points (density), rather than raw zoom, to reduce cache-key
    cardinality across arbitrary zoom levels.
    """
    time_range_part = time_range or "24h"
    transport_part = _normalize_transport_modes_part(transport_modes)
    return f"heatmap:cancellations:{time_range_part}:{transport_part}:{bucket_width_minutes}:{max_points}"
