import asyncio
import sys
import os
from datetime import date
from sqlalchemy import select, union_all, literal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.dialects import postgresql

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.gtfs_schedule import GTFSScheduleService, _get_weekday_column
from app.models.gtfs import GTFSCalendar, GTFSCalendarDate

async def main():
    # Use GTFSScheduleService logic to build query
    query_date = date(2024, 1, 1)
    weekday = query_date.strftime("%A").lower()

    c = aliased(GTFSCalendar, name="c")
    cd = aliased(GTFSCalendarDate, name="cd")

    weekday_col = _get_weekday_column(c, weekday)

    # 1. Get services active by calendar (range + weekday)
    stmt_cal = select(c.service_id, literal(0).label("exception_type")).where(
        c.start_date <= query_date,
        c.end_date >= query_date,
        weekday_col == True,  # noqa: E712
    )

    # 2. Get exceptions for today
    stmt_cd = select(cd.service_id, cd.exception_type).where(cd.date == query_date)

    # Combine into single query using UNION ALL
    union_stmt = union_all(stmt_cal, stmt_cd)

    # Compile to Postgres SQL
    dialect = postgresql.dialect()
    compiled = union_stmt.compile(dialect=dialect)
    print("Generated SQL:")
    print(str(compiled))
    print("\nParameters:")
    print(compiled.params)

if __name__ == "__main__":
    asyncio.run(main())
