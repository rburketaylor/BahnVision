from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.persistence.repositories import TransitDataRepository


async def get_transit_repository(
    session: AsyncSession = Depends(get_session),
) -> TransitDataRepository:
    """FastAPI dependency that yields a configured TransitDataRepository."""
    return TransitDataRepository(session)
