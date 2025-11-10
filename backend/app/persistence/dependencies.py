from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.persistence.repositories import StationRepository, TransitDataRepository


async def get_transit_repository(
    session: AsyncSession = Depends(get_session),
) -> TransitDataRepository:
    """FastAPI dependency that yields a configured TransitDataRepository."""
    return TransitDataRepository(session)


async def get_station_repository(
    session: AsyncSession = Depends(get_session),
) -> StationRepository:
    """FastAPI dependency that yields a configured StationRepository."""
    return StationRepository(session)
