from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base class for SQLAlchemy models."""


def _build_engine() -> AsyncEngine:
    """Create an async SQLAlchemy engine using application settings."""
    settings = get_settings()

    # Use getattr fallbacks to keep compatibility with lightweight test doubles.
    pool_timeout = getattr(settings, "database_pool_timeout_seconds", 30.0)
    pool_recycle = getattr(settings, "database_pool_recycle_seconds", 1800)
    pool_pre_ping = getattr(settings, "database_pool_pre_ping", True)

    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )


engine: AsyncEngine = _build_engine()
"""Shared async engine instance."""

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async SQLAlchemy session."""
    async with AsyncSessionFactory() as session:
        yield session
