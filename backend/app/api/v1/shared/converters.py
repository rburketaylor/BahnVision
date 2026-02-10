"""Shared model conversion utilities for API endpoints.

This module provides functions to convert between internal database models
and API response models.
"""

from typing import Any, Protocol

from app.models.transit import TransitStop


class StopLike(Protocol):
    """Protocol for objects that have stop-like attributes.

    Both GTFSStop ORM model and StopInfo dataclass satisfy this protocol.
    """

    stop_id: Any
    stop_name: Any
    stop_lat: Any
    stop_lon: Any
    zone_id: Any
    wheelchair_boarding: Any


def gtfs_stop_to_transit_stop(
    stop: StopLike,
    *,
    include_zone: bool = True,
    include_wheelchair: bool = True,
) -> TransitStop:
    """Convert a GTFS Stop model to a TransitStop API response model.

    Args:
        stop: The GTFSStop database model or StopInfo dataclass.
        include_zone: Whether to include zone_id in the response.
        include_wheelchair: Whether to include wheelchair_boarding in the response.

    Returns:
        A TransitStop model suitable for API responses.
    """
    return TransitStop(
        id=str(stop.stop_id),
        name=str(stop.stop_name),
        latitude=float(stop.stop_lat) if stop.stop_lat is not None else 0.0,
        longitude=float(stop.stop_lon) if stop.stop_lon is not None else 0.0,
        zone_id=stop.zone_id if include_zone else None,
        wheelchair_boarding=stop.wheelchair_boarding if include_wheelchair else 0,
    )
