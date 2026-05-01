import math
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, List, Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.gtfs import (
    GTFSStop,
    GTFSRoute,
    GTFSStopTime,
    GTFSTrip,
    GTFSCalendar,
    GTFSCalendarDate,
)
from app.services.cache import CacheService, get_cache_service

logger = logging.getLogger(__name__)


class ScheduledDeparture:
    """Represents a scheduled departure from a stop with concrete datetimes."""

    def __init__(
        self,
        departure_time: datetime,
        trip_headsign: str,
        route_short_name: str,
        route_long_name: str,
        route_type: int,
        route_color: Optional[str],
        stop_name: str,
        trip_id: str,
        route_id: str,
        arrival_time: Optional[datetime] = None,
    ):
        self.departure_time = departure_time
        self.trip_headsign = trip_headsign
        self.route_short_name = route_short_name
        self.route_long_name = route_long_name
        self.route_type = route_type
        self.route_color = route_color
        self.stop_name = stop_name
        self.trip_id = trip_id
        self.route_id = route_id
        self.arrival_time = arrival_time or departure_time

    @classmethod
    def from_row(cls, row) -> "ScheduledDeparture":
        """Create from database row."""
        return cls(
            departure_time=row.departure_time,
            trip_headsign=row.trip_headsign or "",
            route_short_name=row.route_short_name or "",
            route_long_name=row.route_long_name or "",
            route_type=row.route_type,
            route_color=row.route_color,
            stop_name=row.stop_name,
            trip_id=row.trip_id,
            route_id=row.route_id,
            arrival_time=getattr(row, "arrival_time", None),
        )


class StopNotFoundError(Exception):
    """Raised when a stop is not found in GTFS data."""

    pass


def _get_weekday_column(calendar: Any, weekday: str):
    """Get the appropriate weekday column from GTFSCalendar model.

    This returns the SQLAlchemy column object, not a string,
    allowing safe use in query construction without string interpolation.
    """
    weekday_attrs = {
        "monday": calendar.monday,
        "tuesday": calendar.tuesday,
        "wednesday": calendar.wednesday,
        "thursday": calendar.thursday,
        "friday": calendar.friday,
        "saturday": calendar.saturday,
        "sunday": calendar.sunday,
    }
    column = weekday_attrs.get(weekday)
    if column is None:
        raise ValueError(f"Invalid weekday: {weekday}")
    return column


class GTFSScheduleService:
    """Query scheduled departures from PostgreSQL."""

    def __init__(
        self,
        session: AsyncSession,
        cache_service: CacheService | None = None,
    ):
        self.session = session
        self._cache = cache_service or get_cache_service()

    def _active_service_ids_cache_key(self, query_date: date) -> str:
        return f"gtfs:schedule:active_service_ids:v1:{query_date.isoformat()}"

    def _active_service_ids_cache_ttl_seconds(self, query_date: date) -> int:
        expiry = datetime.combine(
            query_date + timedelta(days=1), time(0, 0), tzinfo=timezone.utc
        )
        ttl_seconds = int((expiry - datetime.now(timezone.utc)).total_seconds())
        if ttl_seconds <= 0:
            return 24 * 60 * 60
        return ttl_seconds

    async def get_active_service_ids(self, query_date: date) -> List[str]:
        """Get active service_ids for a specific date.

        Combines calendar range/weekday checks with calendar_dates exceptions
        to return a flat list of valid service_ids. This avoids complex joins
        in the main departures query.
        """
        cache_key = self._active_service_ids_cache_key(query_date)
        try:
            cached_service_ids = await self._cache.get_json(cache_key)
            if cached_service_ids is not None:
                return [str(service_id) for service_id in cached_service_ids]
        except Exception as cache_error:
            logger.warning(
                "Failed to read active service IDs from cache for %s: %s",
                query_date,
                cache_error,
            )

        weekday = query_date.strftime("%A").lower()

        c = aliased(GTFSCalendar, name="c")
        cd = aliased(GTFSCalendarDate, name="cd")

        weekday_col = _get_weekday_column(c, weekday)

        # 1. Get services active by calendar (range + weekday)
        stmt_cal = select(c.service_id).where(
            c.start_date <= query_date,
            c.end_date >= query_date,
            weekday_col == True,  # noqa: E712
        )

        # 2. Get exceptions for today
        stmt_cd = select(cd.service_id, cd.exception_type).where(cd.date == query_date)

        # Execute queries
        cal_result = await self.session.execute(stmt_cal)
        active_cal = set(cal_result.scalars().all())

        cd_result = await self.session.execute(stmt_cd)
        exceptions = cd_result.all()  # List of (service_id, exception_type)

        # Apply exceptions
        added = {row.service_id for row in exceptions if row.exception_type == 1}
        removed = {row.service_id for row in exceptions if row.exception_type == 2}

        active_service_ids = list((active_cal - removed) | added)

        try:
            await self._cache.set_json(
                cache_key,
                active_service_ids,
                ttl_seconds=self._active_service_ids_cache_ttl_seconds(query_date),
            )
        except Exception as cache_error:
            logger.warning(
                "Failed to cache active service IDs for %s: %s",
                query_date,
                cache_error,
            )

        return active_service_ids

    async def get_stop_departures(
        self,
        stop_id: str,
        from_time: datetime,
        limit: int = 20,
        validate_existence: bool = True,
    ) -> List[ScheduledDeparture]:
        """Get scheduled departures for a stop.

        Args:
            stop_id: The ID of the stop to get departures for.
            from_time: The start time for the departures window.
            limit: The maximum number of departures to return.
            validate_existence: Whether to verify the stop exists before querying departures.
                Set to False if stop existence is already validated or not required.
                Defaults to True for backward compatibility.
        """
        # Get stop_ids (self + children) first to avoid joining gtfs_stops in the main query.
        # This is significantly faster for PostgreSQL than joining and filtering on OR condition.
        stops_stmt = select(GTFSStop.stop_id, GTFSStop.stop_name).where(
            or_(GTFSStop.stop_id == stop_id, GTFSStop.parent_station == stop_id)
        )
        stops_result = await self.session.execute(stops_stmt)
        stops_data = stops_result.all()

        if not stops_data:
            if validate_existence:
                raise StopNotFoundError(f"Stop {stop_id} not found in GTFS feed")
            return []

        stop_map = {row.stop_id: row.stop_name for row in stops_data}
        target_stop_ids = list(stop_map.keys())

        # Determine which service_ids are active today
        today = from_time.date()

        # Optimization: Pre-fetch active service IDs to simplify main query
        # This removes 2 joins and complex OR conditions from the hot path
        active_service_ids = await self.get_active_service_ids(today)

        if not active_service_ids:
            return []

        # Use aliases for clarity in the query
        st = aliased(GTFSStopTime, name="st")
        t = aliased(GTFSTrip, name="t")
        r = aliased(GTFSRoute, name="r")

        from_seconds = time_to_seconds(from_time)

        # Build the query using SQLAlchemy ORM
        # Optimization: Filter by stop_id IN (...) instead of joining GTFSStop
        query = (
            select(
                st.departure_seconds,
                st.arrival_seconds,
                t.trip_headsign,
                r.route_short_name,
                r.route_long_name,
                r.route_type,
                r.route_color,
                st.stop_id,
                t.trip_id,
                r.route_id,
            )
            .select_from(st)
            .join(t, st.trip_id == t.trip_id)
            .join(r, t.route_id == r.route_id)
            .where(
                st.stop_id.in_(target_stop_ids),
                st.departure_seconds >= from_seconds,
                t.service_id.in_(active_service_ids),
            )
            .order_by(st.departure_seconds)
            .limit(limit)
        )

        result = await self.session.execute(query)

        # Optimization: Pre-calculate midnight to avoid repeated datetime.combine calls
        service_midnight = datetime.combine(today, time(0, 0), tzinfo=timezone.utc)

        departures = []
        for row in result:
            departure_dt = seconds_to_datetime(
                today, row.departure_seconds, base_datetime=service_midnight
            )
            arrival_dt = (
                seconds_to_datetime(
                    today, row.arrival_seconds, base_datetime=service_midnight
                )
                if row.arrival_seconds is not None
                else None
            )

            if departure_dt:
                departures.append(
                    ScheduledDeparture(
                        departure_time=departure_dt,
                        trip_headsign=row.trip_headsign or "",
                        route_short_name=row.route_short_name or "",
                        route_long_name=row.route_long_name or "",
                        route_type=row.route_type,
                        route_color=row.route_color,
                        stop_name=stop_map.get(row.stop_id, ""),
                        trip_id=row.trip_id,
                        route_id=row.route_id,
                        arrival_time=arrival_dt,
                    )
                )

        return departures

    async def get_departures_for_stop(
        self,
        stop_id: str,
        from_time: datetime,
        limit: int = 20,
        validate_existence: bool = True,
    ) -> List[ScheduledDeparture]:
        """Alias for get_stop_departures to maintain API compatibility."""
        return await self.get_stop_departures(
            stop_id, from_time, limit, validate_existence=validate_existence
        )

    async def search_stops(
        self,
        query: str,
        limit: int = 10,
    ) -> List[GTFSStop]:
        """Search for stops by name."""
        stmt = (
            select(GTFSStop).where(GTFSStop.stop_name.ilike(f"%{query}%")).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_stops(self, limit: int = 10000) -> List[GTFSStop]:
        """Get all stops (up to limit).

        Used for heatmap generation where we need station coordinates.
        """
        stmt = select(GTFSStop).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_nearby_stops(
        self,
        lat: float,
        lon: float,
        radius_km: float = 1.0,
        limit: int = 10,
    ) -> List[GTFSStop]:
        """Find stops within radius of given coordinates."""
        # Simple bounding box query (for more accurate distance, use PostGIS)
        lat_delta = radius_km / 111.0  # Approximate km to degrees
        safe_cos_lat = max(abs(math.cos(math.radians(lat))), 0.01)
        lon_delta = radius_km / (111.0 * safe_cos_lat)

        stmt = (
            select(GTFSStop)
            .where(
                GTFSStop.stop_lat.between(lat - lat_delta, lat + lat_delta),
                GTFSStop.stop_lon.between(lon - lon_delta, lon + lon_delta),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_route_details(self, route_id: str) -> Optional[GTFSRoute]:
        """Get route details."""
        stmt = select(GTFSRoute).where(GTFSRoute.route_id == route_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_stop_by_id(self, stop_id: str) -> Optional[GTFSStop]:
        """Get stop by ID."""
        stmt = select(GTFSStop).where(GTFSStop.stop_id == stop_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


def time_to_seconds(dt: datetime) -> int:
    """Convert datetime time to seconds since service midnight."""
    t = dt.time()
    return t.hour * 3600 + t.minute * 60 + t.second


def seconds_to_datetime(
    service_date: date, seconds_value, base_datetime: Optional[datetime] = None
) -> Optional[datetime]:
    """Convert seconds since service midnight to a concrete UTC datetime.

    Handles GTFS times that extend beyond 24h by adding the full timedelta to
    the service day midnight instead of wrapping to a time-of-day.

    Args:
        service_date: The date of service.
        seconds_value: Seconds since service midnight.
        base_datetime: Optional pre-calculated midnight datetime to avoid
            recalculating it for every call.
    """
    if seconds_value is None:
        return None

    try:
        total_seconds = int(seconds_value)
        delta = timedelta(seconds=total_seconds)

        if base_datetime:
            return base_datetime + delta

        service_midnight = datetime.combine(
            service_date, time(0, 0), tzinfo=timezone.utc
        )
        return service_midnight + delta

    except (TypeError, ValueError) as exc:
        logger.warning(
            "Invalid seconds value of type %s: %s",
            type(seconds_value).__name__,
            exc,
        )
        return None
