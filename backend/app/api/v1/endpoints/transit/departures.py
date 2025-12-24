"""
Departures endpoint for Transit API.

Provides real-time departure information using GTFS static + real-time data.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.v1.shared.dependencies import get_transit_data_service
from app.api.v1.shared.rate_limit import limiter
from app.core.config import get_settings
from app.models.transit import (
    TransitDeparture,
    TransitDeparturesResponse,
    TransitStop,
)
from app.services.transit_data import DepartureInfo, TransitDataService

router = APIRouter()

# Cache name for metrics
_CACHE_TRANSIT_DEPARTURES = "transit_departures"


def _departure_info_to_response(dep: DepartureInfo) -> TransitDeparture:
    """Convert internal DepartureInfo to API response model."""
    # Convert alert objects to strings
    alerts = []
    for alert in dep.alerts or []:
        if hasattr(alert, "header_text"):
            alerts.append(alert.header_text)
        elif isinstance(alert, str):
            alerts.append(alert)

    return TransitDeparture(
        trip_id=dep.trip_id,
        route_id=dep.route_id,
        route_short_name=dep.route_short_name,
        route_long_name=dep.route_long_name,
        headsign=dep.trip_headsign,
        stop_id=dep.stop_id,
        stop_name=dep.stop_name,
        scheduled_departure=dep.scheduled_departure,
        scheduled_arrival=dep.scheduled_arrival,
        realtime_departure=dep.real_time_departure,
        realtime_arrival=dep.real_time_arrival,
        departure_delay_seconds=dep.departure_delay_seconds,
        arrival_delay_seconds=dep.arrival_delay_seconds,
        schedule_relationship=dep.schedule_relationship.value,
        vehicle_id=dep.vehicle_id,
        alerts=alerts,
    )


@router.get(
    "/departures",
    response_model=TransitDeparturesResponse,
    summary="Get upcoming departures for a stop",
    description="Returns scheduled departures with real-time updates when available.",
)
@limiter.limit("60/minute")
async def get_departures(
    request: Request,
    stop_id: Annotated[
        str,
        Query(
            min_length=1,
            description="GTFS stop_id to get departures for.",
        ),
    ],
    response: Response,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=50,
            description="Maximum number of departures to return (default: 10).",
        ),
    ] = 10,
    offset_minutes: Annotated[
        int,
        Query(
            ge=0,
            le=240,
            description="Walking time or delay in minutes to offset the schedule.",
        ),
    ] = 0,
    include_realtime: Annotated[
        bool,
        Query(
            description="Whether to include real-time updates (default: true).",
        ),
    ] = True,
    transit_service: TransitDataService = Depends(get_transit_data_service),
) -> TransitDeparturesResponse:
    """Retrieve departures for the requested stop with real-time data."""
    # Get stop info first to validate the stop exists
    stop_info = await transit_service.get_stop_info(stop_id)
    if not stop_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop '{stop_id}' not found",
        )

    # Get departures
    departures = await transit_service.get_departures_for_stop(
        stop_id=stop_id,
        limit=limit,
        offset_minutes=offset_minutes,
        include_real_time=include_realtime,
    )

    # Convert to response models
    transit_stop = TransitStop(
        id=stop_info.stop_id,
        name=stop_info.stop_name,
        latitude=stop_info.stop_lat,
        longitude=stop_info.stop_lon,
        zone_id=stop_info.zone_id,
        wheelchair_boarding=stop_info.wheelchair_boarding,
    )

    transit_departures = [_departure_info_to_response(dep) for dep in departures]

    # Set cache headers
    settings = get_settings()
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.gtfs_schedule_cache_ttl_seconds}"
    )

    realtime_available = include_realtime and transit_service.is_realtime_available()

    return TransitDeparturesResponse(
        stop=transit_stop,
        departures=transit_departures,
        realtime_available=realtime_available,
    )
