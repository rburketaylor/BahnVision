import asyncio
from datetime import date
from sqlalchemy import select, literal, union_all
from sqlalchemy.orm import aliased
from app.models.gtfs import GTFSCalendar, GTFSCalendarDate
from app.services.gtfs_schedule import _get_weekday_column

def test_query_compilation():
    query_date = date(2025, 12, 8)
    weekday = query_date.strftime("%A").lower()

    c = aliased(GTFSCalendar, name="c")
    cd = aliased(GTFSCalendarDate, name="cd")

    weekday_col = _get_weekday_column(c, weekday)

    stmt_cal = select(c.service_id, literal(0).label("exception_type")).where(
        c.start_date <= query_date,
        c.end_date >= query_date,
        weekday_col == True,
    )

    stmt_cd = select(cd.service_id, cd.exception_type).where(cd.date == query_date)

    stmt_union = union_all(stmt_cal, stmt_cd)

    print("SQL Compiled successfully")
    print(str(stmt_union))

if __name__ == "__main__":
    test_query_compilation()
