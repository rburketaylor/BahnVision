"""
Shared dependency injection functions for API endpoints.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

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
