"""Shared utilities for API v1 endpoints.

This package provides common utilities, constants, and helpers used across
multiple endpoint modules.
"""

from app.api.v1.shared.cache_headers import (
    set_cache_header,
    set_schedule_cache_header,
    set_stats_cache_header,
    set_station_search_cache_header,
    set_transit_cache_header,
)
from app.api.v1.shared.constants import (
    RATE_LIMIT_EXPENSIVE,
    RATE_LIMIT_HEATMAP_OVERVIEW,
    RATE_LIMIT_NEARBY,
    RATE_LIMIT_SEARCH,
    RATE_LIMIT_STANDARD,
    RateLimit,
)
from app.api.v1.shared.converters import gtfs_stop_to_transit_stop
from app.api.v1.shared.dependencies import get_transit_data_service
from app.api.v1.shared.errors import (
    resource_not_found,
    station_not_found,
    stop_not_found,
)

__all__ = [
    # Rate limiting
    "RateLimit",
    "RATE_LIMIT_STANDARD",
    "RATE_LIMIT_SEARCH",
    "RATE_LIMIT_EXPENSIVE",
    "RATE_LIMIT_NEARBY",
    "RATE_LIMIT_HEATMAP_OVERVIEW",
    # Cache headers
    "set_cache_header",
    "set_transit_cache_header",
    "set_station_search_cache_header",
    "set_schedule_cache_header",
    "set_stats_cache_header",
    # Error handling
    "stop_not_found",
    "station_not_found",
    "resource_not_found",
    # Model converters
    "gtfs_stop_to_transit_stop",
    # Dependencies
    "get_transit_data_service",
]
