from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.config import get_settings
from app.models.mvg import DeparturesResponse, StationSearchResponse
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
    response: Response,
    transport_filters: list[str] = Query(
        default_factory=list,
        alias="transport_type",
        description="Filter by MVG transport types (e.g. 'UBAHN', 'S-Bahn'). "
        "Repeat the parameter for multiple filters.",
    ),
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=40,
            description="Maximum number of departures to return (default: 10).",
        ),
    ] = 10,
    offset: Annotated[
        int,
        Query(
            ge=0,
            le=60,
            description="Walking time or delay in minutes to offset the schedule.",
        ),
    ] = 0,
    client: Annotated[MVGClient, Depends(get_client)] = Depends(get_client),
    cache: Annotated[CacheService, Depends(get_cache_service)] = Depends(get_cache_service),
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
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        response.headers["X-Cache-Status"] = "hit"
        return DeparturesResponse.model_validate(cached_payload)

    try:
        async with cache.single_flight(
            cache_key,
            ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
            wait_timeout=settings.cache_singleflight_lock_wait_seconds,
            retry_delay=settings.cache_singleflight_retry_delay_seconds,
        ):
            cached_payload = await cache.get_json(cache_key)
            if cached_payload is not None:
                if cached_payload.get("__status") == "not_found":
                    response.headers["X-Cache-Status"] = "hit"
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=cached_payload["detail"],
                    )
                response.headers["X-Cache-Status"] = "hit"
                return DeparturesResponse.model_validate(cached_payload)

            station_details, departures_list = await client.get_departures(
                station_query=station,
                limit=limit,
                offset=offset,
                transport_types=parsed_transport_types or None,
            )
    except TimeoutError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            response.headers["X-Cache-Status"] = "stale"
            return DeparturesResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except StationNotFoundError as exc:
        await cache.set_json(
            cache_key,
            {"__status": "not_found", "detail": str(exc)},
            ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            response.headers["X-Cache-Status"] = "stale"
            return DeparturesResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response_payload = DeparturesResponse.from_dtos(station_details, departures_list)

    await cache.set_json(
        cache_key,
        response_payload.model_dump(mode="json"),
        ttl_seconds=settings.mvg_departures_cache_ttl_seconds,
        stale_ttl_seconds=settings.mvg_departures_cache_stale_ttl_seconds,
    )

    response.headers["X-Cache-Status"] = "miss"
    return response_payload


@router.get(
    "/stations/search",
    response_model=StationSearchResponse,
    summary="Find stations matching a search query",
)
async def search_stations(
    query: Annotated[
        str,
        Query(
            min_length=1,
            description="Free-form search text for MVG stations (name or address).",
        ),
    ],
    response: Response,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=20,
            description="Maximum number of stations to return (default: 8).",
        ),
    ] = 8,
    client: Annotated[MVGClient, Depends(get_client)] = Depends(get_client),
    cache: Annotated[CacheService, Depends(get_cache_service)] = Depends(get_cache_service),
) -> StationSearchResponse:
    """Search MVG for station suggestions."""
    assert client is not None

    settings = get_settings()
    cache_key = _station_search_cache_key(query, limit)

    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        if cached_payload.get("__status") == "not_found":
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        response.headers["X-Cache-Status"] = "hit"
        return StationSearchResponse.model_validate(cached_payload)

    try:
        async with cache.single_flight(
            cache_key,
            ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
            wait_timeout=settings.cache_singleflight_lock_wait_seconds,
            retry_delay=settings.cache_singleflight_retry_delay_seconds,
        ):
            cached_payload = await cache.get_json(cache_key)
            if cached_payload is not None:
                if cached_payload.get("__status") == "not_found":
                    response.headers["X-Cache-Status"] = "hit"
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=cached_payload["detail"],
                    )
                response.headers["X-Cache-Status"] = "hit"
                return StationSearchResponse.model_validate(cached_payload)

            stations = await client.search_stations(query=query, limit=limit)
    except TimeoutError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            response.headers["X-Cache-Status"] = "stale"
            return StationSearchResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            response.headers["X-Cache-Status"] = "stale"
            return StationSearchResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    if not stations:
        detail = f"No stations found for query '{query}'."
        await cache.set_json(
            cache_key,
            {"__status": "not_found", "detail": detail},
            ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    response_payload = StationSearchResponse.from_dtos(query, stations)
    await cache.set_json(
        cache_key,
        response_payload.model_dump(mode="json"),
        ttl_seconds=settings.mvg_station_search_cache_ttl_seconds,
        stale_ttl_seconds=settings.mvg_station_search_cache_stale_ttl_seconds,
    )
    response.headers["X-Cache-Status"] = "miss"
    return response_payload


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


def _station_search_cache_key(query: str, limit: int) -> str:
    normalized_query = query.strip().lower()
    return f"mvg:stations:search:{normalized_query}:{limit}"
