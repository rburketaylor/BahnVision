"""Shared cache header utilities for API endpoints.

This module provides utilities for setting HTTP cache headers consistently
across all endpoints.
"""

from fastapi import Response

from app.core.config import get_settings


def set_cache_header(
    response: Response,
    ttl_seconds: int,
    *,
    public: bool = True,
) -> None:
    """Set Cache-Control header on a response.

    Args:
        response: The FastAPI Response object.
        ttl_seconds: Time-to-live in seconds.
        public: Whether the cache is public (vs private).
    """
    visibility = "public" if public else "private"
    response.headers["Cache-Control"] = f"{visibility}, max-age={ttl_seconds}"


def set_transit_cache_header(
    response: Response, ttl_seconds: int | None = None
) -> None:
    """Set Cache-Control header for transit/GTFS endpoints.

    Uses the configured GTFS cache TTL if not specified.

    Args:
        response: The FastAPI Response object.
        ttl_seconds: Optional TTL override. Uses gtfs_stop_cache_ttl_seconds if not provided.
    """
    settings = get_settings()
    ttl = (
        ttl_seconds if ttl_seconds is not None else settings.gtfs_stop_cache_ttl_seconds
    )
    set_cache_header(response, ttl)


def set_station_search_cache_header(response: Response) -> None:
    """Set Cache-Control header for station search endpoints.

    Args:
        response: The FastAPI Response object.
    """
    settings = get_settings()
    set_cache_header(response, settings.transit_station_search_cache_ttl_seconds)


def set_schedule_cache_header(response: Response) -> None:
    """Set Cache-Control header for schedule/departures endpoints.

    Args:
        response: The FastAPI Response object.
    """
    settings = get_settings()
    set_cache_header(response, settings.gtfs_schedule_cache_ttl_seconds)


def set_stats_cache_header(response: Response, ttl_seconds: int = 300) -> None:
    """Set Cache-Control header for stats endpoints (shorter TTL).

    Stats have a shorter default TTL (5 minutes) than static GTFS data.

    Args:
        response: The FastAPI Response object.
        ttl_seconds: TTL in seconds (default: 300).
    """
    set_cache_header(response, ttl_seconds)
