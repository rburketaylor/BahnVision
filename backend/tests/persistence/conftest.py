"""Shared fixtures for persistence integration tests.

These tests require a running PostgreSQL database. They will be automatically
skipped if the database is not available.
"""

from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Check if database is available at module load time
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision",
)


def _check_db_available() -> bool:
    """Check if database is reachable and has required tables."""
    import asyncio

    async def _try_connect():
        try:
            engine = create_async_engine(TEST_DATABASE_URL)
            async with engine.connect() as conn:
                # Check not just connection, but that tables exist
                result = await conn.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'stations'
                        )
                        """
                    )
                )
                tables_exist = result.scalar()
            await engine.dispose()
            return tables_exist
        except Exception:
            return False

    try:
        return asyncio.get_event_loop().run_until_complete(_try_connect())
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(_try_connect())


# Cache the result to avoid repeated connection attempts
_DB_AVAILABLE: bool | None = None


def is_db_available() -> bool:
    """Check database availability (cached)."""
    global _DB_AVAILABLE
    if _DB_AVAILABLE is None:
        _DB_AVAILABLE = _check_db_available()
    return _DB_AVAILABLE


# Skip marker for all tests in this directory
pytestmark = pytest.mark.integration


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if database is not available."""
    if is_db_available():
        return

    skip_no_db = pytest.mark.skip(
        reason="Database not available - skipping integration test"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_no_db)


async def _truncate_tables(engine) -> None:
    """Truncate all tables for clean test state."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                TRUNCATE TABLE
                    departure_weather_links,
                    weather_observations,
                    departure_observations,
                    route_snapshots,
                    ingestion_runs,
                    transit_lines,
                    stations
                RESTART IDENTITY CASCADE
                """
            )
        )


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for integration tests.

    Automatically truncates tables before and after each test.
    """
    if not is_db_available():
        pytest.skip("Database not available")

    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await _truncate_tables(engine)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await _truncate_tables(engine)
    await engine.dispose()
