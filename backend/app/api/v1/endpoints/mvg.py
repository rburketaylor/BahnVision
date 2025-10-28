from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.models.mvg import DeparturesResponse
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import (
    MVGClient,
    MVGServiceError,
    StationNotFoundError,
    TransportType,
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
            default=10,
            ge=1,
            le=40,
            description="Maximum number of departures to return (default: 10).",
        ),
    ],
    offset: Annotated[
        int,
        Query(
            default=0,
            ge=0,
            le=60,
            description="Walking time or delay in minutes to offset the schedule.",
        ),
    ],
    client: Annotated[MVGClient, Depends(get_client)],
    cache: Annotated[CacheService, Depends(get_cache_service)],
) -> DeparturesResponse:
    """Retrieve next departures for the requested station."""
    assert client is not None  # For static type checkers.

    try:
        parsed_transport_types = parse_transport_types(transport_filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    settings = get_settings()
    cache_key = _departures_cache_key(station, limit, offset, parsed_transport_types)

    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        if cached_payload.get("__status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        return DeparturesResponse.model_validate(cached_payload)

    try:
        station_details, departures_list = await client.get_departures(
            station_query=station,
            limit=limit,
            offset=offset,
            transport_types=parsed_transport_types or None,
        )
    except StationNotFoundError as exc:
        await cache.set_json(
            cache_key,
            {"__status": "not_found", "detail": str(exc)},
            ttl_seconds=settings.redis_cache_ttl_not_found_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except MVGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response = DeparturesResponse.from_dtos(station_details, departures_list)

    await cache.set_json(
        cache_key,
        response.model_dump(mode="json"),
        ttl_seconds=settings.redis_cache_ttl_seconds,
    )

    return response


def _departures_cache_key(
    station: str,
    limit: int,
    offset: int,
    transport_types: list[TransportType],
) -> str:
    normalized_station = station.strip().lower()
    if transport_types:
        type_segment = "-".join(sorted({item.name for item in transport_types}))
    else:
        type_segment = "all"
    return f"mvg:departures:{normalized_station}:{limit}:{offset}:{type_segment}"
