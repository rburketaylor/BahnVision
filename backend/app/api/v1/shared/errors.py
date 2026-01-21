"""Shared error handling utilities for API endpoints.

This module provides standardized error response functions for common
error scenarios like not found resources.
"""

from fastapi import HTTPException, status


def stop_not_found(stop_id: str) -> HTTPException:
    """Create a standardized HTTP 404 exception for stops.

    Args:
        stop_id: The stop ID that was not found.

    Returns:
        An HTTPException with 404 status and detail message.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Stop '{stop_id}' not found",
    )


def station_not_found(station_id: str) -> HTTPException:
    """Create a standardized HTTP 404 exception for stations.

    Args:
        station_id: The station ID that was not found.

    Returns:
        An HTTPException with 404 status and detail message.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Station '{station_id}' not found",
    )


def resource_not_found(resource_type: str, resource_id: str) -> HTTPException:
    """Create a standardized HTTP 404 exception for any resource.

    Args:
        resource_type: The type of resource (e.g., "route", "trip").
        resource_id: The resource ID that was not found.

    Returns:
        An HTTPException with 404 status and detail message.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource_type.capitalize()} '{resource_id}' not found",
    )
