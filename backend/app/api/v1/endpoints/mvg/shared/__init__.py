"""
Shared utilities and infrastructure for MVG API endpoints.

This module provides common functionality used across MVG endpoint modules,
including utility functions, cache key generation, and shared dependencies.
"""

from .cache_keys import (
    departures_cache_key,
    route_cache_key,
    station_search_cache_key,
)
from .utils import ensure_aware_utc, get_client

__all__ = [
    "ensure_aware_utc",
    "get_client",
    "departures_cache_key",
    "route_cache_key",
    "station_search_cache_key",
]
