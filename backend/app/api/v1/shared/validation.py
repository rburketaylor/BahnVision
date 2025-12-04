"""Input validation utilities for MVG API endpoints."""

from datetime import datetime
from typing import List

from app.services.mvg_transport import TransportType


def validate_station_name(station: str) -> None:
    """Validate station name parameter."""
    if not station or len(station.strip()) < 1:
        raise ValueError("Station name must be at least 1 character long")
    return None


def validate_offset(offset: int) -> None:
    """Validate offset parameter."""
    if offset is not None and (offset < 0 or offset > 240):
        raise ValueError("Offset must be between 0 and 240 minutes")
    return None


def validate_transport_filters(transport_filters: List[str]) -> None:
    """Validate transport filter parameters."""
    if not transport_filters:
        return None

    # Validate each filter is a known transport type
    for filter_str in transport_filters:
        try:
            transport_type = TransportType(filter_str.upper())
            if transport_type:
                return None
        except ValueError:
            raise ValueError(
                f"Invalid transport filter: '{filter_str}'. "
                f"Valid options are: {[t.value for t in TransportType]}"
            )

    return None


def validate_offset_with_from_time(
    from_time: datetime | None,
    offset: int | None,
) -> None:
    """Validate offset parameter when used with from_time."""
    if from_time is not None and offset is not None:
        raise ValueError(
            "Cannot specify both 'from' and 'offset' parameters. "
            "Use 'from' for time-based pagination or 'offset' for minute-based offset."
        )
    return None


def validate_limit_with_offset(limit: int, offset: int | None) -> None:
    """Validate offset parameter when also using limit."""
    if offset is not None:
        if not (0 <= offset <= limit * 4):  # Allow up to 4 pages (4 * limit minutes)
            raise ValueError(
                f"Offset must be between 0 and {limit * 4} when using limit of {limit}"
            )
    return None
