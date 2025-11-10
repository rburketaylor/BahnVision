"""
Cache key generation functions for MVG endpoints.

This module provides standardized cache key generation functions
to ensure consistent caching across MVG endpoint modules.
"""

from datetime import datetime
from typing import List

from app.services.mvg_client import TransportType


def departures_cache_key(
    station: str,
    limit: int,
    offset: int,
    transport_types: List[TransportType],
) -> str:
    """Generate cache key for departures endpoint.

    Creates distinct cache keys based on transport type filters to ensure
    proper cache isolation between different filter combinations.

    Args:
        station: Station name or ID
        limit: Maximum number of departures to return
        offset: Time offset in minutes
        transport_types: List of transport type filters

    Returns:
        Standardized cache key string with transport type segment
    """
    normalized_station = station.strip().lower()

    if transport_types:
        # Create order-independent transport type segment for consistent cache keys
        type_segment = "-".join(sorted({t.name for t in transport_types}))
    else:
        type_segment = "all"

    return f"mvg:departures:{normalized_station}:{limit}:{offset}:{type_segment}"


def station_search_cache_key(query: str, limit: int) -> str:
    """Generate cache key for station search endpoint.

    Args:
        query: Search query string
        limit: Maximum number of results to return

    Returns:
        Standardized cache key string
    """
    normalized_query = query.strip().lower()
    return f"mvg:stations:search:{normalized_query}:{limit}"


def route_cache_key(
    origin: str,
    destination: str,
    departure_time: datetime | None,
    arrival_time: datetime | None,
    transport_types: List[TransportType],
) -> str:
    """Generate cache key for route planning endpoint.

    Args:
        origin: Origin station name or ID
        destination: Destination station name or ID
        departure_time: Desired departure time (UTC)
        arrival_time: Desired arrival time (UTC)
        transport_types: List of transport type filters

    Returns:
        Standardized cache key string
    """
    origin_segment = origin.strip().lower()
    destination_segment = destination.strip().lower()

    if departure_time is not None:
        time_segment = f"dep:{int(departure_time.timestamp())}"
    elif arrival_time is not None:
        time_segment = f"arr:{int(arrival_time.timestamp())}"
    else:
        time_segment = "now"

    if transport_types:
        type_segment = "-".join(sorted({item.name for item in transport_types}))
    else:
        type_segment = "all"

    return f"mvg:route:{origin_segment}:{destination_segment}:{time_segment}:{type_segment}"