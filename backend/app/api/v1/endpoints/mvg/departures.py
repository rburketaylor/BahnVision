"""
Departures endpoint for MVG API.

Provides real-time departure information with caching and stale fallback.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from app.api.v1.endpoints.mvg.shared.cache_keys import departures_cache_key
from app.api.v1.endpoints.mvg.shared.utils import ensure_aware_utc, get_client
from app.api.v1.shared.cache_manager import CacheManager
from app.api.v1.shared.mvg_protocols import DeparturesRefreshProtocol
from app.core.config import get_settings
from app.models.mvg import DeparturesResponse
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import MVGClient
from app.services.mvg_transport import parse_transport_types

router = APIRouter()

# Cache name for metrics
_CACHE_DEPARTURES = "mvg_departures"


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
    # Validate and parse transport types
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
        from_time = ensure_aware_utc(from_time)
        now = datetime.now(timezone.utc)
        now_utc = ensure_aware_utc(now)
        # Calculate offset minutes as ceiling of (from_time - now) / 60, clamped at 0
        delta_minutes = int((from_time - now_utc).total_seconds() / 60)
        offset = max(0, delta_minutes)
        if offset > 240:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Offset derived from 'from' parameter exceeds maximum allowed value of 240 minutes.",
            )

    # Setup cache manager with optimized protocol
    settings = get_settings()
    protocol = DeparturesRefreshProtocol(client, parsed_transport_types)
    cache_manager = CacheManager(protocol, cache, _CACHE_DEPARTURES)

    # Generate cache key that accounts for transport filters
    cache_key = departures_cache_key(station, limit, offset, parsed_transport_types)

    # Single unified call regardless of transport type filters
    return await cache_manager.get_cached_data(
        cache_key=cache_key,
        response=response,
        background_tasks=background_tasks,
        settings=settings,
        station=station,
        limit=limit,
        offset=offset,
    )
