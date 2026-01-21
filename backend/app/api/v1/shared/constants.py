"""Shared constants for API endpoints.

This module defines common rate limit values and other constants used
across multiple endpoints to maintain consistency.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimit:
    """Rate limit configuration for endpoints."""

    value: str
    """The rate limit string (e.g., '60/minute')."""

    @property
    def per_minute(self) -> int:
        """Extract requests per minute from the limit string."""
        parts = self.value.split("/")
        return int(parts[0]) if parts[1].startswith("minute") else 0


# Rate limit constants for different endpoint types
RATE_LIMIT_SEARCH = RateLimit("60/minute")
"""Rate limit for search endpoints (e.g., stop search)."""

RATE_LIMIT_STANDARD = RateLimit("60/minute")
"""Rate limit for standard read endpoints."""

RATE_LIMIT_EXPENSIVE = RateLimit("30/minute")
"""Rate limit for expensive/endpoints (e.g., heatmap, trends)."""

RATE_LIMIT_HEATMAP_OVERVIEW = RateLimit("30/minute")
"""Rate limit for heatmap overview endpoint."""

RATE_LIMIT_NEARBY = RateLimit("30/minute")
"""Rate limit for nearby stops endpoint (more expensive)."""
