"""
Example of how shared caching patterns simplify endpoint implementations.

This file demonstrates the before/after comparison showing how ~520 lines of
duplicated cache handling code can be reduced to ~20 lines per endpoint.
"""

# BEFORE: Original endpoint implementation with duplicated patterns (~100 lines)
# ----------------------------------------------------------------------
"""
async def departures(
    station: str,
    response: Response,
    background_tasks: BackgroundTasks,
    transport_filters: list[str],
    limit: int = 10,
    offset: int = 0,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> DeparturesResponse:
    settings = get_settings()
    cache_key = _departures_cache_key(station, limit, offset, [])

    # Cache lookup pattern (20+ lines)
    cached_payload = await cache.get_json(cache_key)
    if cached_payload is not None:
        record_cache_event(_CACHE_DEPARTURES, "hit")
        if cached_payload.get("__status") == "not_found":
            response.headers["X-Cache-Status"] = "hit"
            raise HTTPException(status_code=404, detail=cached_payload["detail"])
        response.headers["X-Cache-Status"] = "hit"
        return DeparturesResponse.model_validate(cached_payload)

    stale_payload = await cache.get_stale_json(cache_key)
    if stale_payload is not None and stale_payload.get("__status") != "not_found":
        record_cache_event(_CACHE_DEPARTURES, "stale_return")
        response.headers["X-Cache-Status"] = "stale-refresh"
        background_tasks.add_task(_background_refresh_departures, ...)
        return DeparturesResponse.model_validate(stale_payload)

    record_cache_event(_CACHE_DEPARTURES, "miss")

    # Error handling pattern (30+ lines)
    try:
        response_payload = await _refresh_departures_cache(...)
    except TimeoutError as exc:
        record_cache_event(_CACHE_DEPARTURES, "lock_timeout")
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_DEPARTURES, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return DeparturesResponse.model_validate(stale_payload)
        raise HTTPException(status_code=503, detail=str(exc))
    except StationNotFoundError as exc:
        record_cache_event(_CACHE_DEPARTURES, "not_found")
        raise HTTPException(status_code=404, detail=str(exc))
    except MVGServiceError as exc:
        stale_payload = await cache.get_stale_json(cache_key)
        if stale_payload is not None and stale_payload.get("__status") != "not_found":
            record_cache_event(_CACHE_DEPARTURES, "stale_return")
            response.headers["X-Cache-Status"] = "stale"
            return DeparturesResponse.model_validate(stale_payload)
        raise HTTPException(status_code=502, detail=str(exc))

    response.headers["X-Cache-Status"] = "miss"
    return response_payload
"""

# AFTER: Simplified endpoint using shared patterns (~15 lines)
# ------------------------------------------------------------------
from fastapi import BackgroundTasks, Depends, Query, Response
from app.api.v1.shared.caching import CacheManager
from app.api.v1.shared.protocols import DeparturesRefreshProtocol
from app.services.cache import CacheService
from app.services.mvg_client import MVGClient, parse_transport_types
from app.core.config import get_settings


async def departures_simplified(
    station: str,
    response: Response,
    background_tasks: BackgroundTasks,
    transport_filters: list[str] = Query(default_factory=list, alias="transport_type"),
    limit: int = 10,
    offset: int = 0,
    client: MVGClient = Depends(get_client),
    cache: CacheService = Depends(get_cache_service),
) -> DeparturesResponse:
    """Simplified departures endpoint using shared caching patterns."""
    settings = get_settings()
    transport_types = parse_transport_types(transport_filters)
    cache_key = f"mvg:departures:{station}:{limit}:{offset}:{','.join(transport_types)}"

    # Create protocol and manager
    protocol = DeparturesRefreshProtocol(client)
    cache_manager = CacheManager(protocol, cache, "mvg_departures")

    # Single line handles all caching logic!
    return await cache_manager.get_cached_data(
        cache_key=cache_key,
        response=response,
        background_tasks=background_tasks,
        settings=settings,
        station=station,
        limit=limit,
        offset=offset,
        transport_types=transport_types,
    )


# BEFORE: Original cache refresh function (~50 lines)
# ----------------------------------------------------------------------
"""
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
"""

# AFTER: Protocol implementation replaces cache refresh (~20 lines)
# ------------------------------------------------------------------
class DeparturesRefreshProtocol(CacheRefreshProtocol[DeparturesResponse]):
    """Cache refresh protocol for departures endpoint."""

    def __init__(self, client: MVGClient):
        self.client = client

    def cache_name(self) -> str:
        return "mvg_departures"

    async def fetch_data(self, **kwargs: Any) -> DeparturesResponse:
        station = kwargs["station"]
        limit = kwargs["limit"]
        offset = kwargs["offset"]
        transport_types = kwargs.get("transport_types", [])

        station_details, departures_list = await self.client.get_departures(
            station_query=station,
            limit=limit,
            offset=offset,
            transport_types=transport_types or None,
        )
        return DeparturesResponse.from_dtos(station_details, departures_list)

    async def store_data(
        self,
        cache_key: str,
        data: DeparturesResponse,
        settings: Settings,
    ) -> None:
        await cache.set_json(
            cache_key,
            data.model_dump(mode="json"),
            ttl_seconds=settings.mvg_departures_cache_ttl_seconds,
            stale_ttl_seconds=settings.mvg_departures_cache_stale_ttl_seconds,
        )


# BEFORE: Original background refresh function (~15 lines)
# ----------------------------------------------------------------------
"""
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
    try:
        await _refresh_departures_cache(...)
    except StationNotFoundError:
        record_cache_event(_CACHE_DEPARTURES, "background_not_found")
    except MVGServiceError:
        record_cache_event(_CACHE_DEPARTURES, "background_error")
        logger.warning("MVG service error while refreshing departures cache.", exc_info=True)
    except TimeoutError:
        record_cache_event(_CACHE_DEPARTURES, "background_lock_timeout")
    except Exception:
        record_cache_event(_CACHE_DEPARTURES, "background_unexpected_error")
        logger.exception("Unexpected error while refreshing departures cache.")
"""

# AFTER: No longer needed - handled by shared execute_background_refresh function
# ----------------------------------------------------------------------
# The shared caching module handles all background refresh patterns automatically!