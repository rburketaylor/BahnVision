#!/usr/bin/env python3
"""
Reset database to a clean state for migration testing.
Drops all tables and ENUMs, then stamps alembic to base.
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def reset_database():
    """Drop all tables and ENUMs, reset alembic."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.begin() as conn:
            print("Resetting database to clean state...")

            # Drop alembic version table
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            print("✓ Dropped alembic_version table")

            # Drop all our tables (including GTFS tables)
            tables = [
                # Original tables
                "departure_weather_links",
                "weather_observations",
                "route_snapshots",
                "departure_observations",
                "transit_lines",
                "stations",
                "ingestion_runs",
                # GTFS tables
                "gtfs_stop_times",
                "gtfs_calendar_dates",
                "gtfs_calendar",
                "gtfs_trips",
                "gtfs_routes",
                "gtfs_stops",
                "gtfs_feed_info",
            ]

            for table in tables:
                # nosec: table names are hardcoded above, not user input
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                print(f"✓ Dropped table: {table}")

            # Drop all ENUMs
            enums = [
                "transport_mode",
                "departure_status",
                "weather_condition",
                "external_status",
                "ingestion_source",
                "ingestion_status",
            ]

            for enum in enums:
                # nosec: enum names are hardcoded above, not user input
                await conn.execute(text(f"DROP TYPE IF EXISTS {enum} CASCADE"))
                print(f"✓ Dropped enum: {enum}")

            print("\n✅ Database reset complete!")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset_database())
