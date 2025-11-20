#!/usr/bin/env python3
"""
Load test fixtures into the database for migration testing.
This script inserts sample data that can be used to verify migrations work correctly.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.persistence.models import (
    DepartureObservation,
    DepartureStatus,
    IngestionRun,
    IngestionSource,
    IngestionStatus,
    Station,
    TransitLine,
    TransportMode,
)


async def load_fixtures():
    """Load sample data into the database."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.begin() as conn:
            print("Loading test fixtures...")

            # Check if data already exists
            result = await conn.execute(select(Station))
            if result.first():
                print("⚠️  Fixtures already loaded, skipping...")
                return

            # Insert sample station
            station_data = {
                "station_id": "de:09162:6",
                "name": "Marienplatz",
                "place": "München",
                "latitude": 48.137154,
                "longitude": 11.575677,
                "transport_modes": ["UBAHN", "SBAHN"],
                "timezone": "Europe/Berlin",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await conn.execute(Station.__table__.insert().values(station_data))
            print("✓ Inserted test station: Marienplatz")

            # Insert sample transit line
            line_data = {
                "line_id": "U3",
                "transport_mode": TransportMode.UBAHN,
                "operator": "MVG",
                "description": "U-Bahn Line 3",
                "color_hex": "#EC6726",
                "created_at": datetime.now(timezone.utc),
            }
            await conn.execute(TransitLine.__table__.insert().values(line_data))
            print("✓ Inserted test transit line: U3")

            # Insert sample ingestion run
            ingestion_data = {
                "job_name": "test_ingestion",
                "source": IngestionSource.MVG_DEPARTURES,
                "started_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc),
                "status": IngestionStatus.SUCCESS,
                "records_inserted": 1,
                "notes": "Test fixture data",
            }
            result = await conn.execute(
                IngestionRun.__table__.insert()
                .values(ingestion_data)
                .returning(IngestionRun.id)
            )
            ingestion_id = result.scalar_one()
            print(f"✓ Inserted test ingestion run: {ingestion_id}")

            # Insert sample departure
            departure_data = {
                "station_id": "de:09162:6",
                "line_id": "U3",
                "ingestion_run_id": ingestion_id,
                "direction": "Moosach",
                "destination": "Moosach",
                "planned_departure": datetime.now(timezone.utc),
                "delay_seconds": 120,
                "platform": "2",
                "transport_mode": TransportMode.UBAHN,
                "status": DepartureStatus.DELAYED,
                "source": "mvg",
                "created_at": datetime.now(timezone.utc),
            }
            await conn.execute(
                DepartureObservation.__table__.insert().values(departure_data)
            )
            print("✓ Inserted test departure observation")

            print("\n✅ All test fixtures loaded successfully!")

    finally:
        await engine.dispose()


async def verify_fixtures():
    """Verify that fixtures were loaded correctly."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.begin() as conn:
            print("\nVerifying test fixtures...")

            # Count stations
            result = await conn.execute(select(Station))
            station_count = len(result.all())
            print(f"✓ Stations: {station_count}")

            # Count transit lines
            result = await conn.execute(select(TransitLine))
            line_count = len(result.all())
            print(f"✓ Transit lines: {line_count}")

            # Count ingestion runs
            result = await conn.execute(select(IngestionRun))
            ingestion_count = len(result.all())
            print(f"✓ Ingestion runs: {ingestion_count}")

            # Count departures
            result = await conn.execute(select(DepartureObservation))
            departure_count = len(result.all())
            print(f"✓ Departure observations: {departure_count}")

            if station_count > 0 and line_count > 0 and departure_count > 0:
                print("\n✅ All fixtures verified!")
                return True
            else:
                print("\n❌ Fixture verification failed!")
                return False

    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    await load_fixtures()
    await verify_fixtures()


if __name__ == "__main__":
    asyncio.run(main())
