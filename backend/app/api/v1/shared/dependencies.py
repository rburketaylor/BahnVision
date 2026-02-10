"""
Shared dependency injection functions for API endpoints.
"""

from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.services.cache import CacheService, get_cache_service
from app.services.gtfs_schedule import GTFSScheduleService
from app.services.gtfs_realtime import GtfsRealtimeService
from app.services.transit_data import TransitDataService


async def get_transit_data_service(
    cache: CacheService = Depends(get_cache_service),
    db: AsyncSession = Depends(get_session),
) -> TransitDataService:
    """Create TransitDataService with dependencies."""
    gtfs_schedule = GTFSScheduleService(db)
    gtfs_realtime = GtfsRealtimeService(cache)
    return TransitDataService(cache, gtfs_schedule, gtfs_realtime, db)


async def require_admin_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    """Require a configured admin API key via X-API-Key or Bearer auth."""
    settings = get_settings()
    expected_key = settings.admin_api_key

    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured",
        )

    provided_key = x_api_key
    if not provided_key and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            provided_key = token.strip()

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin credentials",
        )

    if not compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin credentials",
        )
