"""
Shared utility functions for MVG endpoints.

This module contains common utility functions that are used across
different MVG endpoint modules to avoid code duplication.
"""

from datetime import datetime, timezone

from fastapi import Depends

from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import MVGClient


def ensure_aware_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and normalize all timestamps to UTC.

    Args:
        value: A datetime that may be naive or timezone-aware

    Returns:
        A timezone-aware datetime in UTC
    """
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_client(
    cache_service: CacheService = Depends(get_cache_service),
) -> MVGClient:
    """Instantiate a fresh MVG client per request."""
    return MVGClient(cache_service=cache_service)
