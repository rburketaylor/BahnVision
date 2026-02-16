import asyncio
from datetime import date
from sqlalchemy import select, literal, union_all, cast, SmallInteger
from sqlalchemy.orm import aliased
from sqlalchemy.dialects import postgresql
from app.models.gtfs import GTFSCalendar, GTFSCalendarDate
from app.services.gtfs_schedule import _get_weekday_column

def compile_query():
    query_date = date(2025, 12, 8)
    weekday = query_date.strftime("%A").lower()

    c = aliased(GTFSCalendar, name="c")
    cd = aliased(GTFSCalendarDate, name="cd")

    weekday_col = _get_weekday_column(c, weekday)

    # Replicate the code in gtfs_schedule.py
    stmt_cal = select(
        c.service_id, cast(literal(0), SmallInteger).label("exception_type")
    ).where(
        c.start_date <= query_date,
        c.end_date >= query_date,
        weekday_col == True,
    )

    stmt_cd = select(cd.service_id, cd.exception_type).where(cd.date == query_date)

    stmt_union = union_all(stmt_cal, stmt_cd)

    # Compile with Postgres dialect
    try:
        compiled = stmt_union.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        print("Compilation successful:")
        print(str(compiled))
    except Exception as e:
        print(f"Compilation failed: {e}")

if __name__ == "__main__":
    compile_query()
