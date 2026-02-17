import asyncio
from datetime import date
from sqlalchemy import Column, String, Boolean, Date, SmallInteger, select, union_all, literal, cast
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, aliased

Base = declarative_base()

class GTFSCalendar(Base):
    __tablename__ = "gtfs_calendar"
    service_id = Column(String(64), primary_key=True)
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    feed_id = Column(String(32))

class GTFSCalendarDate(Base):
    __tablename__ = "gtfs_calendar_dates"
    service_id = Column(String(64), primary_key=True)
    date = Column(Date, primary_key=True)
    exception_type = Column(SmallInteger, nullable=False)
    feed_id = Column(String(32))

def _get_weekday_column(calendar, weekday):
    return getattr(calendar, weekday)

async def main():
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

        # Reimplement logic inline
        query_date = date(2024, 1, 1)
        weekday = query_date.strftime("%A").lower()

        c = aliased(GTFSCalendar, name="c")
        cd = aliased(GTFSCalendarDate, name="cd")

        weekday_col = _get_weekday_column(c, weekday)

        # 1. Get services active by calendar (range + weekday)
        stmt_cal = select(c.service_id, cast(literal(0), SmallInteger).label("exception_type")).where(
            c.start_date <= query_date,
            c.end_date >= query_date,
            weekday_col == True,
        )

        # 2. Get exceptions for today
        stmt_cd = select(cd.service_id, cd.exception_type).where(cd.date == query_date)

        # Combine into single query using UNION ALL
        union_stmt = union_all(stmt_cal, stmt_cd)

        # Execute query
        result = await session.execute(union_stmt)
        rows = result.all()

        print(f"Rows: {rows}")

        active_services = set()
        added = set()
        removed = set()

        for service_id, exception_type in rows:
            if exception_type == 1:
                added.add(service_id)
            elif exception_type == 2:
                removed.add(service_id)
            else:
                active_services.add(service_id)

        active_ids = list((active_services - removed) | added)
        print(f"Active IDs: {active_ids}")

        assert "service_add" in active_ids
        assert "service_1" not in active_ids

    print("Success!")

if __name__ == "__main__":
    asyncio.run(main())
