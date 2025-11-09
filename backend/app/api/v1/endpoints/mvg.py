from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status

from app.core.config import get_settings
from app.core.metrics import observe_cache_refresh, record_cache_event
from app.models.mvg import DeparturesResponse, RouteResponse, Station, StationSearchResponse
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import (
    MVGClient,
    MVGServiceError,
    RouteNotFoundError,
    StationNotFoundError,
    TransportType,
    parse_transport_types,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_CACHE_DEPARTURES = "mvg_departures"
_CACHE_STATION_SEARCH = "mvg_station_search"
_CACHE_STATION_LIST = "mvg_station_list"
_CACHE_ROUTE = "mvg_route"


def _ensure_aware_utc(value: datetime) -> datetime:
    """Treat naive datetimes as UTC and normalize all timestamps to UTC."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    background_tasks: BackgroundTasks,
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
            le=240,
            description="Walking time or delay in minutes to offset the schedule.",
        ),
    ] = 0,
    from_time: Annotated[
        datetime | None,
        Query(
            description="UTC ISO timestamp to start results from. Cannot be used together with offset. "
            "If provided, results are the next N departures starting at this time anchor.",
            alias="from",
        ),
    ] = None,
    window_minutes: Annotated[
        int | None,
        Query(
            ge=1,
            le=240,
            description="Optional window size in minutes for pagination stepping. "
            "Used by clients for page navigation, does not affect server response size.",
        ),
    ] = None,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> DeparturesResponse:
    """Retrieve next departures for the requested station."""
    assert client is not None  # For static type checkers.

    try:
        parsed_transport_types = parse_transport_types(transport_filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    # Validate mutual exclusivity of from_time and offset
    if from_time is not None and offset != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot specify both 'from' and 'offset' parameters. Use 'from' for time-based pagination or 'offset' for minute-based offset.",
        )

    # Convert from_time to offset if provided
    if from_time is not None:
        from_time = _ensure_aware_utc(from_time)
        now = datetime.now(timezone.utc)
        # Calculate offset minutes as ceiling of (from_time - now) / 60, clamped at 0
        delta_minutes = int((from_time - now).total_seconds() / 60)
        offset = max(0, delta_minutes)
        if offset > 240:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Offset derived from 'from' parameter exceeds maximum allowed value of 240 minutes.",
            )

    settings = get_settings()
    all_departures = []
    station_details = None
    partial_response = False

    if not parsed_transport_types:
        cache_key = _departures_cache_key(station, limit, offset, [])
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            record_cache_event(_CACHE_DEPARTURES, "hit")
            if cached_payload.get("__status") == "not_found":
                response.headers["X-Cache-Status"] = "hit"
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
                )
            response.headers["X-Cache-Status"] = "hit"
            return DeparturesResponse.model_validate(cached_payload)

        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_DEPARTURES, "stale_return")
            response.headers["X-Cache-Status"] = "stale-refresh"
            background_tasks.add_task(
                _background_refresh_departures,
                cache,
                client,
                cache_key,
                station,
                limit,
                offset,
                [],
                settings,
            )
            return DeparturesResponse.model_validate(stale_payload)

        record_cache_event(_CACHE_DEPARTURES, "miss")
        try:
            response_payload = await _refresh_departures_cache(
                cache=cache,
                cache_key=cache_key,
                client=client,
                station=station,
                limit=limit,
                offset=offset,
                transport_types=[],
                settings=settings,
            )
        except TimeoutError as exc:
            record_cache_event(_CACHE_DEPARTURES, "lock_timeout")
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(_CACHE_DEPARTURES, "stale_return")
                response.headers["X-Cache-Status"] = "stale"
                return DeparturesResponse.model_validate(stale_payload)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except StationNotFoundError as exc:
            record_cache_event(_CACHE_DEPARTURES, "not_found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except MVGServiceError as exc:
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(_CACHE_DEPARTURES, "stale_return")
                response.headers["X-Cache-Status"] = "stale"
                return DeparturesResponse.model_validate(stale_payload)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

        response.headers["X-Cache-Status"] = "miss"
        return response_payload

    for transport_type in parsed_transport_types:
        cache_key = _departures_cache_key(station, limit, offset, [transport_type])
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            record_cache_event(_CACHE_DEPARTURES, "hit")
            if cached_payload.get("__status") == "not_found":
                continue
            response.headers["X-Cache-Status"] = "hit"
            departures_response = DeparturesResponse.model_validate(cached_payload)
            if not station_details:
                station_details = departures_response.station
            all_departures.extend(departures_response.departures)
            continue

        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_DEPARTURES, "stale_return")
            response.headers["X-Cache-Status"] = "stale-refresh"
            background_tasks.add_task(
                _background_refresh_departures,
                cache,
                client,
                cache_key,
                station,
                limit,
                offset,
                [transport_type],
                settings,
            )
            departures_response = DeparturesResponse.model_validate(stale_payload)
            if not station_details:
                station_details = departures_response.station
            all_departures.extend(departures_response.departures)
            continue

        record_cache_event(_CACHE_DEPARTURES, "miss")
        try:
            response_payload = await _refresh_departures_cache(
                cache=cache,
                cache_key=cache_key,
                client=client,
                station=station,
                limit=limit,
                offset=offset,
                transport_types=[transport_type],
                settings=settings,
            )
            if not station_details:
                station_details = response_payload.station
            all_departures.extend(response_payload.departures)
        except TimeoutError as exc:
            record_cache_event(_CACHE_DEPARTURES, "lock_timeout")
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(_CACHE_DEPARTURES, "stale_return")
                response.headers["X-Cache-Status"] = "stale"
                departures_response = DeparturesResponse.model_validate(stale_payload)
                if not station_details:
                    station_details = departures_response.station
                all_departures.extend(departures_response.departures)
                continue
            # If we have some departures, we can return them
            if all_departures:
                partial_response = True
                break
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except StationNotFoundError as exc:
            record_cache_event(_CACHE_DEPARTURES, "not_found")
            # If we have some departures, we can return them
            if all_departures:
                partial_response = True
                break
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except MVGServiceError as exc:
            stale_payload = await cache.get_stale_json(cache_key)
            if stale_payload is not None and stale_payload.get("__status") != "not_found":
                record_cache_event(_CACHE_DEPARTURES, "stale_return")
                response.headers["X-Cache-Status"] = "stale"
                departures_response = DeparturesResponse.model_validate(stale_payload)
                if not station_details:
                    station_details = departures_response.station
                all_departures.extend(departures_response.departures)
                continue
            # If we have some departures, we can return them
            if all_departures:
                partial_response = True
                break
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc

    if not station_details:
        # This should not happen if we have departures
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Station not found"
        )

    all_departures.sort(key=lambda d: d.planned_time)
    if partial_response and "X-Cache-Status" not in response.headers:
        response.headers["X-Cache-Status"] = "miss"

    return DeparturesResponse(
        station=station_details,
        departures=all_departures[:limit],
        partial=partial_response,
    )


@router.get(
    "/routes/plan",
    response_model=RouteResponse,
    summary="Plan a route between two stations",
)
async def plan_route(
    origin: Annotated[
        str,
        Query(
            min_length=1,
            description="Origin station query (name or global station id).",
        ),
    ],
    destination: Annotated[
        str,
        Query(
            min_length=1,
            description="Destination station query (name or global station id).",
        ),
    ],
    response: Response,
    background_tasks: BackgroundTasks,
    departure_time: datetime | None = Query(
        default=None,
        description="Desired departure time (UTC). Omit to use current time.",
    ),
    arrival_time: datetime | None = Query(
        default=None,
        description="Desired arrival deadline (UTC). Only one of departure_time or arrival_time may be set.",
    ),
    transport_filters: list[str] = Query(
        default_factory=list,
        alias="transport_type",
        description="Optional list of transport type filters (e.g. 'UBAHN', 'bus').",
    ),
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> RouteResponse:
    """Plan a multi-leg MVG route between two stations."""
    assert client is not None

    if departure_time and arrival_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Specify either departure_time or arrival_time, not both.",
        )

    try:
        parsed_transport_types = parse_transport_types(transport_filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    settings = get_settings()
    cache_key = _route_cache_key(
        origin,
        destination,
        departure_time,
        arrival_time,
        parsed_transport_types,
    )

    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        record_cache_event(_CACHE_ROUTE, "hit")
        if cached_payload.get("__status") == "not_found":
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        response.headers["X-Cache-Status"] = "hit"
        return RouteResponse.model_validate(cached_payload)

    stale_payload = await cache.get_stale_json(cache_key)
    if stale_payload is not None and stale_payload.get("__status") != "not_found":
        record_cache_event(_CACHE_ROUTE, "stale_return")
        response.headers["X-Cache-Status"] = "stale-refresh"
        background_tasks.add_task(
            _background_refresh_route,
            cache,
            client,
            cache_key,
            origin,
            destination,
            departure_time,
            arrival_time,
            parsed_transport_types,
            settings,
        )
        return RouteResponse.model_validate(stale_payload)

    record_cache_event(_CACHE_ROUTE, "miss")
    try:
        response_payload = await _refresh_route_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            transport_types=parsed_transport_types,
            settings=settings,
        )
    except TimeoutError as exc:
        record_cache_event(_CACHE_ROUTE, "lock_timeout")
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_ROUTE, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return RouteResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except RouteNotFoundError as exc:
        record_cache_event(_CACHE_ROUTE, "not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_ROUTE, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return RouteResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response.headers["X-Cache-Status"] = "miss"
    return response_payload


async def _refresh_departures_cache(
    cache: CacheService,
    cache_key: str,
    client: MVGClient,
    station: str,
    limit: int,
    offset: int,
    transport_types: list[TransportType],
    settings,
) -> DeparturesResponse:
    """Refresh departures cache entry and return the latest payload."""
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            if cached_payload.get("__status") == "not_found":
                detail = cached_payload["detail"]
                record_cache_event(_CACHE_DEPARTURES, "refresh_cached_not_found")
                raise StationNotFoundError(detail)
            record_cache_event(_CACHE_DEPARTURES, "refresh_skip_hit")
            return DeparturesResponse.model_validate(cached_payload)

        start = time.perf_counter()
        try:
            station_details, departures_list = await client.get_departures(
                station_query=station,
                limit=limit,
                offset=offset,
                transport_types=transport_types or None,
            )
        except StationNotFoundError:
            detail = f"Station not found for query '{station}'."
            await cache.set_json(
                cache_key,
                {"__status": "not_found", "detail": detail},
                ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
                stale_ttl_seconds=settings.mvg_departures_cache_stale_ttl_seconds,
            )
            record_cache_event(_CACHE_DEPARTURES, "refresh_not_found")
            raise
        except MVGServiceError:
            record_cache_event(_CACHE_DEPARTURES, "refresh_error")
            raise

        response_payload = DeparturesResponse.from_dtos(station_details, departures_list)
        observe_cache_refresh(_CACHE_DEPARTURES, time.perf_counter() - start)
        await cache.set_json(
            cache_key,
            response_payload.model_dump(mode="json"),
            ttl_seconds=settings.mvg_departures_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_departures_cache_stale_ttl_seconds,
        )
        record_cache_event(_CACHE_DEPARTURES, "refresh_success")
        return response_payload


async def _background_refresh_departures(
    cache: CacheService,
    client: MVGClient,
    cache_key: str,
    station: str,
    limit: int,
    offset: int,
    transport_types: list[TransportType],
    settings,
) -> None:
    """Background task wrapper to refresh departures cache."""
    try:
        await _refresh_departures_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            station=station,
            limit=limit,
            offset=offset,
            transport_types=transport_types,
            settings=settings,
        )
    except StationNotFoundError:
        # No need to log at error level; cache already stores not-found marker.
        record_cache_event(_CACHE_DEPARTURES, "background_not_found")
    except MVGServiceError:
        record_cache_event(_CACHE_DEPARTURES, "background_error")
        logger.warning("MVG service error while refreshing departures cache.", exc_info=True)
    except TimeoutError:
        record_cache_event(_CACHE_DEPARTURES, "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(_CACHE_DEPARTURES, "background_unexpected_error")
        logger.exception("Unexpected error while refreshing departures cache.")


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
    background_tasks: BackgroundTasks,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=20,
            description="Maximum number of stations to return (default: 8).",
        ),
    ] = 8,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> StationSearchResponse:
    """Search MVG for station suggestions."""
    assert client is not None

    settings = get_settings()
    cache_key = _station_search_cache_key(query, limit)

    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        record_cache_event(_CACHE_STATION_SEARCH, "hit")
        if cached_payload.get("__status") == "not_found":
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=cached_payload["detail"]
            )
        response.headers["X-Cache-Status"] = "hit"
        return StationSearchResponse.model_validate(cached_payload)

    stale_payload = await cache.get_stale_json(cache_key)
    if stale_payload is not None and stale_payload.get("__status") != "not_found":
        record_cache_event(_CACHE_STATION_SEARCH, "stale_return")
        response.headers["X-Cache-Status"] = "stale-refresh"
        background_tasks.add_task(
            _background_refresh_station_search,
            cache,
            client,
            cache_key,
            query,
            limit,
            settings,
        )
        return StationSearchResponse.model_validate(stale_payload)

    record_cache_event(_CACHE_STATION_SEARCH, "miss")
    try:
        response_payload = await _refresh_station_search_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            query=query,
            limit=limit,
            settings=settings,
        )
    except TimeoutError as exc:
        record_cache_event(_CACHE_STATION_SEARCH, "lock_timeout")
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_STATION_SEARCH, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return StationSearchResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except StationNotFoundError as exc:
        record_cache_event(_CACHE_STATION_SEARCH, "not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_STATION_SEARCH, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return StationSearchResponse.model_validate(stale_payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response.headers["X-Cache-Status"] = "miss"
    return response_payload


@router.get(
    "/stations/list",
    response_model=list[Station],
    summary="Get all MVG stations (cached)",
)
async def list_stations(
    response: Response,
    background_tasks: BackgroundTasks,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> list[Station]:
    """Get the complete list of MVG stations."""
    assert client is not None

    settings = get_settings()
    cache_key = "mvg:stations:all"

    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        record_cache_event(_CACHE_STATION_LIST, "hit")
        response.headers["X-Cache-Status"] = "hit"
        return [Station.model_validate(station) for station in cached_payload]

    stale_payload = await cache.get_stale_json(cache_key)
    if stale_payload is not None:
        record_cache_event(_CACHE_STATION_LIST, "stale_return")
        response.headers["X-Cache-Status"] = "stale-refresh"
        background_tasks.add_task(
            _background_refresh_station_list,
            cache,
            client,
            cache_key,
            settings,
        )
        return [Station.model_validate(station) for station in stale_payload]

    record_cache_event(_CACHE_STATION_LIST, "miss")
    try:
        response_payload = await _refresh_station_list_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            settings=settings,
        )
    except TimeoutError as exc:
        record_cache_event(_CACHE_STATION_LIST, "lock_timeout")
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None:
            record_cache_event(_CACHE_STATION_LIST, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return [Station.model_validate(station) for station in stale_payload]
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None:
            record_cache_event(_CACHE_STATION_LIST, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return [Station.model_validate(station) for station in stale_payload]
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    response.headers["X-Cache-Status"] = "miss"
    return response_payload


async def _refresh_station_search_cache(
    cache: CacheService,
    cache_key: str,
    client: MVGClient,
    query: str,
    limit: int,
    settings,
) -> StationSearchResponse:
    """Refresh station search results in the cache."""
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            if cached_payload.get("__status") == "not_found":
                detail = cached_payload["detail"]
                record_cache_event(_CACHE_STATION_SEARCH, "refresh_cached_not_found")
                raise MVGServiceError(detail)
            record_cache_event(_CACHE_STATION_SEARCH, "refresh_skip_hit")
            return StationSearchResponse.model_validate(cached_payload)

        start = time.perf_counter()

        station_list_cache_key = "mvg:stations:all"
        station_list_payload = await cache.get_json(station_list_cache_key)
        if station_list_payload is None:
            all_stations = await _refresh_station_list_cache(
                cache=cache,
                cache_key=station_list_cache_key,
                client=client,
                settings=settings,
            )
        else:
            all_stations = [
                Station.model_validate(station) for station in station_list_payload
            ]

        query_lower = query.lower()
        stations: list[Station] = []
        for station in all_stations:
            if query_lower in station.name.lower() or query_lower in station.place.lower():
                stations.append(station)
                if len(stations) >= limit:
                    break
        if not stations:
            detail = f"No stations found for query '{query}'."
            await cache.set_json(
                cache_key,
                {"__status": "not_found", "detail": detail},
                ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
                stale_ttl_seconds=settings.mvg_station_search_cache_stale_ttl_seconds,
            )
            record_cache_event(_CACHE_STATION_SEARCH, "refresh_not_found")
            raise StationNotFoundError(detail)

        response_payload = StationSearchResponse.from_dtos(query, stations)
        observe_cache_refresh(_CACHE_STATION_SEARCH, time.perf_counter() - start)
        await cache.set_json(
            cache_key,
            response_payload.model_dump(mode="json"),
            ttl_seconds=settings.mvg_station_search_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_station_search_cache_stale_ttl_seconds,
        )
        record_cache_event(_CACHE_STATION_SEARCH, "refresh_success")
        return response_payload


async def _refresh_station_list_cache(
    cache: CacheService,
    cache_key: str,
    client: MVGClient,
    settings,
) -> list[Station]:
    """Refresh the complete station list cache."""
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            record_cache_event(_CACHE_STATION_LIST, "refresh_skip_hit")
            return [Station.model_validate(station) for station in cached_payload]

        start = time.perf_counter()
        stations = await client.get_all_stations()

        if not stations:
            stations = []

        station_dicts = [
            {
                "id": station.id,
                "name": station.name,
                "place": station.place,
                "latitude": station.latitude,
                "longitude": station.longitude,
            }
            for station in stations
        ]
        await cache.set_json(
            cache_key,
            station_dicts,
            ttl_seconds=settings.mvg_station_list_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_station_list_cache_stale_ttl_seconds,
        )
        observe_cache_refresh(_CACHE_STATION_LIST, time.perf_counter() - start)
        record_cache_event(_CACHE_STATION_LIST, "refresh_success")
        return stations


async def _background_refresh_station_search(
    cache: CacheService,
    client: MVGClient,
    cache_key: str,
    query: str,
    limit: int,
    settings,
) -> None:
    """Background refresh task for station search results."""
    try:
        await _refresh_station_search_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            query=query,
            limit=limit,
            settings=settings,
        )
    except StationNotFoundError:
        record_cache_event(_CACHE_STATION_SEARCH, "background_not_found")
        logger.debug("No stations found during background search refresh for query '%s'.", query)
    except TimeoutError:
        record_cache_event(_CACHE_STATION_SEARCH, "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(_CACHE_STATION_SEARCH, "background_unexpected_error")
        logger.exception("Unexpected error while refreshing station search cache.")


async def _background_refresh_station_list(
    cache: CacheService,
    client: MVGClient,
    cache_key: str,
    settings,
) -> None:
    """Background refresh task for the complete station list."""
    try:
        await _refresh_station_list_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            settings=settings,
        )
    except TimeoutError:
        record_cache_event(_CACHE_STATION_LIST, "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(_CACHE_STATION_LIST, "background_unexpected_error")
        logger.exception("Unexpected error while refreshing station list cache.")


async def _refresh_route_cache(
    cache: CacheService,
    cache_key: str,
    client: MVGClient,
    origin: str,
    destination: str,
    departure_time: datetime | None,
    arrival_time: datetime | None,
    transport_types: list[TransportType],
    settings,
) -> RouteResponse:
    """Refresh the MVG route cache for the requested journey."""
    async with cache.single_flight(
        cache_key,
        ttl_seconds=settings.cache_singleflight_lock_ttl_seconds,
        wait_timeout=settings.cache_singleflight_lock_wait_seconds,
        retry_delay=settings.cache_singleflight_retry_delay_seconds,
    ):
        cached_payload = await cache.get_json(cache_key)
        if cached_payload is not None:
            if cached_payload.get("__status") == "not_found":
                detail = cached_payload["detail"]
                record_cache_event(_CACHE_ROUTE, "refresh_cached_not_found")
                raise RouteNotFoundError(detail)
            record_cache_event(_CACHE_ROUTE, "refresh_skip_hit")
            return RouteResponse.model_validate(cached_payload)

        start = time.perf_counter()
        try:
            origin_dto, destination_dto, plans = await client.plan_route(
                origin_query=origin,
                destination_query=destination,
                departure_time=departure_time,
                arrival_time=arrival_time,
                transport_types=transport_types or None,
            )
        except RouteNotFoundError:
            detail = (
                f"No MVG routes available between '{origin}' and '{destination}'."
            )
            await cache.set_json(
                cache_key,
                {"__status": "not_found", "detail": detail},
                ttl_seconds=settings.valkey_cache_ttl_not_found_seconds,
                stale_ttl_seconds=settings.mvg_route_cache_stale_ttl_seconds,
            )
            record_cache_event(_CACHE_ROUTE, "refresh_not_found")
            raise
        except MVGServiceError:
            record_cache_event(_CACHE_ROUTE, "refresh_error")
            raise

        response_payload = RouteResponse.from_dtos(origin_dto, destination_dto, plans)
        observe_cache_refresh(_CACHE_ROUTE, time.perf_counter() - start)
        await cache.set_json(
            cache_key,
            response_payload.model_dump(mode="json"),
            ttl_seconds=settings.mvg_route_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_route_cache_stale_ttl_seconds,
        )
        record_cache_event(_CACHE_ROUTE, "refresh_success")
        return response_payload


async def _background_refresh_route(
    cache: CacheService,
    client: MVGClient,
    cache_key: str,
    origin: str,
    destination: str,
    departure_time: datetime | None,
    arrival_time: datetime | None,
    transport_types: list[TransportType],
    settings,
) -> None:
    """Background task wrapper for route refreshes."""
    try:
        await _refresh_route_cache(
            cache=cache,
            cache_key=cache_key,
            client=client,
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            transport_types=transport_types,
            settings=settings,
        )
    except RouteNotFoundError:
        record_cache_event(_CACHE_ROUTE, "background_not_found")
    except MVGServiceError:
        record_cache_event(_CACHE_ROUTE, "background_error")
        logger.warning("MVG service error while refreshing route cache.", exc_info=True)
    except TimeoutError:
        record_cache_event(_CACHE_ROUTE, "background_lock_timeout")
    except Exception:  # pragma: no cover - defensive logging
        record_cache_event(_CACHE_ROUTE, "background_unexpected_error")
        logger.exception("Unexpected error while refreshing route cache.")


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


def _route_cache_key(
    origin: str,
    destination: str,
    departure_time: datetime | None,
    arrival_time: datetime | None,
    transport_types: list[TransportType],
) -> str:
    origin_segment = origin.strip().lower()
    destination_segment = destination.strip().lower()
    if departure_time is not None:
        time_segment = f"dep:{int(departure_time.timestamp())}"
    elif arrival_time is not None:
        time_segment = f"arr:{int(arrival_time.timestamp())}"
    else:
        time_segment = "now"
    if transport_types:
        type_segment = "-".join(sorted({item.name for item in transport_types}))
    else:
        type_segment = "all"
    return f"mvg:route:{origin_segment}:{destination_segment}:{time_segment}:{type_segment}"
