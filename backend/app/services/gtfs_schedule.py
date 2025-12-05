import logging
from datetime import datetime, time
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gtfs import (
    GTFSStop,
    GTFSRoute,
)

logger = logging.getLogger(__name__)


class ScheduledDeparture:
    """Represents a scheduled departure from a stop."""

    def __init__(
        self,
        departure_time: time,
        trip_headsign: str,
        route_short_name: str,
        route_long_name: str,
        route_type: int,
        route_color: Optional[str],
        stop_name: str,
        trip_id: str,
        route_id: str,
        arrival_time: Optional[time] = None,
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


class GTFSScheduleService:
    """Query scheduled departures from PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_stop_departures(
        self,
        stop_id: str,
        from_time: datetime,
        limit: int = 20,
    ) -> List[ScheduledDeparture]:
        """Get scheduled departures for a stop."""
        # First verify stop exists
        stop = await self._get_stop(stop_id)
        if not stop:
            raise StopNotFoundError(f"Stop {stop_id} not found in GTFS feed")

        # Determine which service_ids are active today
        today = from_time.date()
        weekday = today.strftime("%A").lower()  # 'monday', 'tuesday', etc.

        query = text(
            f"""
            SELECT 
                st.departure_time,
                st.arrival_time,
                t.trip_headsign,
                r.route_short_name,
                r.route_long_name,
                r.route_type,
                r.route_color,
                s.stop_name,
                t.trip_id,
                r.route_id
            FROM gtfs_stop_times st
            JOIN gtfs_trips t ON st.trip_id = t.trip_id
            JOIN gtfs_routes r ON t.route_id = r.route_id
            JOIN gtfs_stops s ON st.stop_id = s.stop_id
            JOIN gtfs_calendar c ON t.service_id = c.service_id
            LEFT JOIN gtfs_calendar_dates cd 
                ON t.service_id = cd.service_id AND cd.date = :today
            WHERE st.stop_id = :stop_id
              AND c.start_date <= :today AND c.end_date >= :today
              AND (
                  -- Regular service day
                  (c.{weekday} = true AND (cd.exception_type IS NULL OR cd.exception_type != 2))
                  -- Or added via calendar_dates
                  OR cd.exception_type = 1
              )
              AND st.departure_time >= :from_interval
            ORDER BY st.departure_time
            LIMIT :limit
        """
        )

        result = await self.session.execute(
            query,
            {
                "stop_id": stop_id,
                "today": today,
                "from_interval": time_to_interval(from_time),
                "limit": limit,
            },
        )

        departures = []
        for row in result:
            # Convert interval back to time
            departure_time = interval_to_time(row.departure_time)
            arrival_time = (
                interval_to_time(row.arrival_time) if row.arrival_time else None
            )
            if departure_time:
                # Create a copy of the row with the converted time
                row_dict = dict(row._mapping)
                row_dict["departure_time"] = departure_time
                row_dict["arrival_time"] = arrival_time
                departures.append(
                    ScheduledDeparture.from_row(type("Row", (), row_dict))
                )

        return departures

    async def get_departures_for_stop(
        self,
        stop_id: str,
        from_time: datetime,
        limit: int = 20,
    ) -> List[ScheduledDeparture]:
        """Alias for get_stop_departures to maintain API compatibility."""
        return await self.get_stop_departures(stop_id, from_time, limit)

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
        lon_delta = radius_km / (111.0 * abs(lat)) if lat != 0 else radius_km / 111.0

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

    async def _get_stop(self, stop_id: str) -> Optional[GTFSStop]:
        """Get stop by ID."""
        stmt = select(GTFSStop).where(GTFSStop.stop_id == stop_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


def time_to_interval(dt: datetime) -> str:
    """Convert datetime time to PostgreSQL interval format."""
    t = dt.time()
    return f"{t.hour} hours {t.minute} minutes {t.second} seconds"


def interval_to_time(interval_value) -> Optional[time]:
    """Convert PostgreSQL interval (timedelta) to time object."""
    if interval_value is None:
        return None

    try:
        from datetime import timedelta

        # PostgreSQL returns interval as timedelta
        if isinstance(interval_value, timedelta):
            total_seconds = int(interval_value.total_seconds())
            hours = (total_seconds // 3600) % 24  # Handle >24h by wrapping around
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return time(hour=hours, minute=minutes, second=seconds)

        # Fallback: try parsing as string
        if isinstance(interval_value, str):
            # Parse interval like "2 hours 30 minutes 0 seconds"
            parts = interval_value.split()
            hours = minutes = seconds = 0

            i = 0
            while i < len(parts):
                if i + 1 < len(parts):
                    value = int(parts[i])
                    unit = parts[i + 1]

                    if "hour" in unit:
                        hours = value % 24  # Handle >24h by wrapping around
                    elif "minute" in unit:
                        minutes = value
                    elif "second" in unit:
                        seconds = value

                    i += 2
                else:
                    i += 1

            return time(hour=hours, minute=minutes, second=seconds)

        logger.warning(f"Unknown interval type: {type(interval_value)}")
        return None

    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid interval format: {interval_value}, error: {e}")
        return None
