"""Tests for database engine and session lifecycle."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.core import database
from tests.service_availability import skip_if_no_postgres


@pytest.mark.integration
@pytest.mark.requires_postgres
@pytest.mark.asyncio
async def test_async_session_factory_executes_simple_query():
    """Test that async session factory can execute queries.

    This test requires a running PostgreSQL database.
    Uses a dedicated engine to avoid connection pool conflicts with other tests.
    """
    skip_if_no_postgres()

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings

    settings = get_settings()
    test_engine = create_async_engine(settings.database_url, pool_size=1)
    TestSessionFactory = async_sessionmaker(test_engine, expire_on_commit=False)

    try:
        async with TestSessionFactory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
            assert session.bind is test_engine
    finally:
        await test_engine.dispose()


def test_build_engine_uses_settings(monkeypatch):
    fake_settings = SimpleNamespace(
        database_url="postgresql+asyncpg://test:test@localhost:5432/testdb",
        database_echo=True,
        database_pool_size=7,
        database_max_overflow=2,
    )
    recorded = {}

    monkeypatch.setattr(database, "get_settings", lambda: fake_settings)

    def fake_create_async_engine(url, **kwargs):
        recorded["url"] = url
        recorded["kwargs"] = kwargs
        return "engine"

    monkeypatch.setattr(database, "create_async_engine", fake_create_async_engine)

    engine = database._build_engine()

    assert engine == "engine"
    assert recorded["url"] == fake_settings.database_url
    assert recorded["kwargs"]["echo"] is True
    assert recorded["kwargs"]["pool_size"] == 7
    assert recorded["kwargs"]["max_overflow"] == 2
