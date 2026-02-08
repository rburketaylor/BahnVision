"""Unit tests for heatmap cache key helpers."""

from app.services.heatmap_cache import (
    heatmap_cancellations_cache_key,
    heatmap_live_snapshot_cache_key,
    heatmap_overview_cache_key,
    normalize_transport_modes_for_cache_key,
)


def test_normalize_transport_modes_defaults_to_all():
    assert normalize_transport_modes_for_cache_key(None) == "all"
    assert normalize_transport_modes_for_cache_key("") == "all"
    assert normalize_transport_modes_for_cache_key(" , , ") == "all"


def test_normalize_transport_modes_is_case_insensitive_sorted_and_deduped():
    normalized = normalize_transport_modes_for_cache_key(" ubahn , BUS,ubahn , tram ")
    assert normalized == "BUS,TRAM,UBAHN"


def test_heatmap_cancellations_cache_key_uses_normalized_modes_and_default_range():
    cache_key = heatmap_cancellations_cache_key(
        time_range=None,
        transport_modes=" bus , UBAHN,bus",
        bucket_width_minutes=60,
        max_points=500,
    )

    assert cache_key == "heatmap:cancellations:24h:BUS,UBAHN:60:500"


def test_heatmap_overview_cache_key_uses_default_time_range_label():
    cache_key = heatmap_overview_cache_key(
        time_range=None,
        transport_modes=None,
        bucket_width_minutes=30,
        metrics="both",
    )

    assert cache_key == "heatmap:overview:default:all:30:both"


def test_heatmap_live_snapshot_cache_key_is_stable():
    assert heatmap_live_snapshot_cache_key() == "heatmap:live:snapshot:v1"
