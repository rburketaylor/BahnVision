from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.mvg import DeparturesResponse
from app.services.mvg_client import (
    MVGClient,
    MVGServiceError,
    StationNotFoundError,
    parse_transport_types,
)

router = APIRouter()


def get_client() -> MVGClient:
    """Instantiate a fresh MVG client per request."""
    return MVGClient()


@router.get(
    "/departures",
    response_model=DeparturesResponse,
    summary="Get upcoming departures for a station",
)
async def departures(
    station: Annotated[
        str,
        Query(
            ...,
            min_length=1,
            description="Station query (name or global station id such as 'de:09162:6').",
        ),
    ],
    transport_filters: list[str] = Query(
        default_factory=list,
        alias="transport_type",
        description="Filter by MVG transport types (e.g. 'UBAHN', 'S-Bahn'). "
        "Repeat the parameter for multiple filters.",
    ),
    limit: Annotated[
        int,
        Query(
            10,
            ge=1,
            le=40,
            description="Maximum number of departures to return (default: 10).",
        ),
    ] = 10,
    offset: Annotated[
        int,
        Query(
            0,
            ge=0,
            le=60,
            description="Walking time or delay in minutes to offset the schedule.",
        ),
    ] = 0,
    client: Annotated[MVGClient, Depends(get_client)] = Depends(get_client),
) -> DeparturesResponse:
    """Retrieve next departures for the requested station."""
    assert client is not None  # For static type checkers.

    try:
        parsed_transport_types = parse_transport_types(transport_filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    try:
        station_details, departures_list = await client.get_departures(
            station_query=station,
            limit=limit,
            offset=offset,
            transport_types=parsed_transport_types or None,
        )
    except StationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except MVGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return DeparturesResponse.from_dtos(station_details, departures_list)
