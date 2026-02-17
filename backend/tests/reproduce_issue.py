import asyncio
import sys
import os
from datetime import date
from sqlalchemy import select, union_all, literal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.gtfs_schedule import GTFSScheduleService
from app.models.gtfs import GTFSCalendar, GTFSCalendarDate
from app.persistence.models import Base

async def main():
    # Setup in-memory SQLite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Create test data
        cal = GTFSCalendar(
            service_id="service_1",
            monday=True, tuesday=True, wednesday=True, thursday=True, friday=True, saturday=False, sunday=False,
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        cd_add = GTFSCalendarDate(service_id="service_add", date=date(2024, 1, 1), exception_type=1)
        cd_remove = GTFSCalendarDate(service_id="service_1", date=date(2024, 1, 1), exception_type=2)

        session.add_all([cal, cd_add, cd_remove])
        await session.commit()

        service = GTFSScheduleService(session)

        # Test 1: Query for a Monday (should have service_1)
        print("Test 1: Query for Monday (2024-01-01)")
        active_ids = await service.get_active_service_ids(date(2024, 1, 1))
        print(f"Active IDs: {active_ids}")
        # Expect service_add (added via exception)
        # service_1 is removed via exception
        assert "service_add" in active_ids
        assert "service_1" not in active_ids

        # Test 2: Query for a Tuesday (2024-01-02)
        print("Test 2: Query for Tuesday (2024-01-02)")
        active_ids = await service.get_active_service_ids(date(2024, 1, 2))
        print(f"Active IDs: {active_ids}")
        # Expect service_1 (normal calendar)
        assert "service_1" in active_ids

    print("Success!")

if __name__ == "__main__":
    asyncio.run(main())
