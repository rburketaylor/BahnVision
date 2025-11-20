"""Route planning endpoint for MVG API.

This module provides route planning functionality with caching and error handling.
It leverages shared infrastructure to minimize code duplication while maintaining
security, performance, and observability.
"""

from datetime import datetime
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

from app.api.v1.endpoints.mvg.shared.cache_keys import route_cache_key
from app.api.v1.shared.cache_manager import CacheManager
from app.api.v1.shared.protocols import RouteRefreshProtocol
from app.core.config import get_settings
from app.models.mvg import RouteResponse
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import (
    MVGClient,
    MVGServiceError,
    RouteNotFoundError,
)
from app.services.mvg_transport import parse_transport_types
from app.api.v1.endpoints.mvg.shared.utils import get_client

router = APIRouter()


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
    # Validate input parameters
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

    # Generate cache key
    cache_key = route_cache_key(
        origin=origin,
        destination=destination,
        departure_time=departure_time,
        arrival_time=arrival_time,
        transport_types=parsed_transport_types,
    )

    # Setup cache manager with route protocol
    route_protocol = RouteRefreshProtocol(client)
    cache_manager = CacheManager(
        protocol=route_protocol,
        cache=cache,
        cache_name="mvg_route",
    )

    # Get cached data with automatic refresh and error handling
    try:
        result = await cache_manager.get_cached_data(
            cache_key=cache_key,
            response=response,
            background_tasks=background_tasks,
            settings=get_settings(),
            origin=origin,
            destination=destination,
            departure_time=departure_time,
            arrival_time=arrival_time,
            transport_types=parsed_transport_types,
        )
        return result

    except RouteNotFoundError:
        # Cache manager already handles 404 responses with appropriate caching
        raise
    except MVGServiceError:
        # Cache manager already handles service errors with stale fallback
        raise
