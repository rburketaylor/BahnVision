import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import gtfs_kit as gk
import httpx
from pandas import DataFrame
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.gtfs import (
    GTFSFeedInfo,
    GTFSCalendar,
    GTFSCalendarDate,
    GTFSRoute,
    GTFSTrip,
    GTFSStop,
    GTFSStopTime,
)

logger = logging.getLogger(__name__)


class GTFSFeedImporter:
    """Import GTFS feed into PostgreSQL using gtfs-kit + SQLAlchemy."""

    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.storage_path = Path(settings.gtfs_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def import_feed(self, feed_url: Optional[str] = None) -> str:
        """Download, parse, and persist GTFS feed."""
        feed_url = feed_url or self.settings.gtfs_feed_url

        # 1. Download feed
        feed_path = await self._download_feed(feed_url)

        # 2. Load with gtfs-kit (in-memory Pandas DataFrames)
        logger.info(f"Loading GTFS feed from {feed_path}")
        feed = gk.read_feed(feed_path, dist_units="km")

        # 3. Generate feed_id for tracking
        feed_id = f"gtfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 4. Persist to PostgreSQL via SQLAlchemy
        logger.info(f"Persisting GTFS feed {feed_id} to database")
        await self._persist_stops(feed.stops, feed_id)
        await self._persist_routes(feed.routes, feed_id)
        await self._persist_trips(feed.trips, feed_id)
        await self._persist_stop_times(feed.stop_times, feed_id)
        await self._persist_calendar(feed.calendar, feed.calendar_dates, feed_id)

        # 5. Record feed metadata
        await self._record_feed_info(feed, feed_id, feed_url)

        logger.info(f"Successfully imported GTFS feed {feed_id}")
        return feed_id

    async def _download_feed(self, feed_url: str) -> Path:
        """Download GTFS feed ZIP file."""
        filename = f"gtfs_feed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        feed_path = self.storage_path / filename

        logger.info(f"Downloading GTFS feed from {feed_url}")

        async with httpx.AsyncClient(
            timeout=self.settings.gtfs_download_timeout_seconds
        ) as client:
            response = await client.get(feed_url)
            response.raise_for_status()

            with open(feed_path, "wb") as f:
                f.write(response.content)

        logger.info(f"Downloaded GTFS feed to {feed_path}")
        return feed_path

    async def _persist_stops(self, stops_df: DataFrame, feed_id: str):
        """Bulk insert stops from DataFrame."""
        if stops_df is None or stops_df.empty:
            return

        records = []
        for row in stops_df.itertuples():
            record = {
                "stop_id": row.stop_id,
                "stop_name": row.stop_name,
                "stop_lat": getattr(row, "stop_lat", None),
                "stop_lon": getattr(row, "stop_lon", None),
                "location_type": getattr(row, "location_type", 0),
                "parent_station": getattr(row, "parent_station", None),
                "platform_code": getattr(row, "platform_code", None),
                "feed_id": feed_id,
            }
            records.append(record)

        await self.session.execute(
            insert(GTFSStop)
            .values(records)
            .on_conflict_do_update(
                index_elements=["stop_id"],
                set_=dict(
                    stop_name=insert(GTFSStop).excluded.stop_name,
                    stop_lat=insert(GTFSStop).excluded.stop_lat,
                    stop_lon=insert(GTFSStop).excluded.stop_lon,
                    location_type=insert(GTFSStop).excluded.location_type,
                    parent_station=insert(GTFSStop).excluded.parent_station,
                    platform_code=insert(GTFSStop).excluded.platform_code,
                    feed_id=insert(GTFSStop).excluded.feed_id,
                    updated_at=datetime.utcnow(),
                ),
            )
        )
        logger.info(f"Persisted {len(records)} stops")

    async def _persist_routes(self, routes_df: DataFrame, feed_id: str):
        """Bulk insert routes from DataFrame."""
        if routes_df is None or routes_df.empty:
            return

        records = []
        for row in routes_df.itertuples():
            record = {
                "route_id": row.route_id,
                "agency_id": getattr(row, "agency_id", None),
                "route_short_name": getattr(row, "route_short_name", None),
                "route_long_name": getattr(row, "route_long_name", None),
                "route_type": row.route_type,
                "route_color": getattr(row, "route_color", None),
                "feed_id": feed_id,
            }
            records.append(record)

        await self.session.execute(
            insert(GTFSRoute)
            .values(records)
            .on_conflict_do_update(
                index_elements=["route_id"],
                set_=dict(
                    agency_id=insert(GTFSRoute).excluded.agency_id,
                    route_short_name=insert(GTFSRoute).excluded.route_short_name,
                    route_long_name=insert(GTFSRoute).excluded.route_long_name,
                    route_type=insert(GTFSRoute).excluded.route_type,
                    route_color=insert(GTFSRoute).excluded.route_color,
                    feed_id=insert(GTFSRoute).excluded.feed_id,
                ),
            )
        )
        logger.info(f"Persisted {len(records)} routes")

    async def _persist_trips(self, trips_df: DataFrame, feed_id: str):
        """Bulk insert trips from DataFrame."""
        if trips_df is None or trips_df.empty:
            return

        records = []
        for row in trips_df.itertuples():
            record = {
                "trip_id": row.trip_id,
                "route_id": row.route_id,
                "service_id": row.service_id,
                "trip_headsign": getattr(row, "trip_headsign", None),
                "direction_id": getattr(row, "direction_id", None),
                "feed_id": feed_id,
            }
            records.append(record)

        await self.session.execute(
            insert(GTFSTrip)
            .values(records)
            .on_conflict_do_update(
                index_elements=["trip_id"],
                set_=dict(
                    route_id=insert(GTFSTrip).excluded.route_id,
                    service_id=insert(GTFSTrip).excluded.service_id,
                    trip_headsign=insert(GTFSTrip).excluded.trip_headsign,
                    direction_id=insert(GTFSTrip).excluded.direction_id,
                    feed_id=insert(GTFSTrip).excluded.feed_id,
                ),
            )
        )
        logger.info(f"Persisted {len(records)} trips")

    async def _persist_stop_times(self, stop_times_df: DataFrame, feed_id: str):
        """Bulk insert stop times from DataFrame."""
        if stop_times_df is None or stop_times_df.empty:
            return

        records = []
        for row in stop_times_df.itertuples():
            record = {
                "trip_id": row.trip_id,
                "stop_id": row.stop_id,
                "arrival_time": self._convert_time_to_interval(
                    getattr(row, "arrival_time", None)
                ),
                "departure_time": self._convert_time_to_interval(
                    getattr(row, "departure_time", None)
                ),
                "stop_sequence": row.stop_sequence,
                "pickup_type": getattr(row, "pickup_type", 0),
                "drop_off_type": getattr(row, "drop_off_type", 0),
                "feed_id": feed_id,
            }
            records.append(record)

        # Delete existing stop_times for this trip to avoid duplicates
        trip_ids = list(set(record["trip_id"] for record in records))
        for trip_id in trip_ids:
            await self.session.execute(
                "DELETE FROM gtfs_stop_times WHERE trip_id = :trip_id",
                {"trip_id": trip_id},
            )

        await self.session.execute(insert(GTFSStopTime).values(records))
        logger.info(f"Persisted {len(records)} stop times")

    async def _persist_calendar(
        self, calendar_df: DataFrame, calendar_dates_df: DataFrame, feed_id: str
    ):
        """Persist calendar and calendar dates from DataFrames."""
        # Persist calendar
        if calendar_df is not None and not calendar_df.empty:
            records = []
            for row in calendar_df.itertuples():
                record = {
                    "service_id": row.service_id,
                    "monday": row.monday,
                    "tuesday": row.tuesday,
                    "wednesday": row.wednesday,
                    "thursday": row.thursday,
                    "friday": row.friday,
                    "saturday": row.saturday,
                    "sunday": row.sunday,
                    "start_date": row.start_date,
                    "end_date": row.end_date,
                    "feed_id": feed_id,
                }
                records.append(record)

            await self.session.execute(
                insert(GTFSCalendar)
                .values(records)
                .on_conflict_do_update(
                    index_elements=["service_id"],
                    set_=dict(
                        monday=insert(GTFSCalendar).excluded.monday,
                        tuesday=insert(GTFSCalendar).excluded.tuesday,
                        wednesday=insert(GTFSCalendar).excluded.wednesday,
                        thursday=insert(GTFSCalendar).excluded.thursday,
                        friday=insert(GTFSCalendar).excluded.friday,
                        saturday=insert(GTFSCalendar).excluded.saturday,
                        sunday=insert(GTFSCalendar).excluded.sunday,
                        start_date=insert(GTFSCalendar).excluded.start_date,
                        end_date=insert(GTFSCalendar).excluded.end_date,
                        feed_id=insert(GTFSCalendar).excluded.feed_id,
                    ),
                )
            )
            logger.info(f"Persisted {len(records)} calendar records")

        # Persist calendar dates
        if calendar_dates_df is not None and not calendar_dates_df.empty:
            records = []
            for row in calendar_dates_df.itertuples():
                record = {
                    "service_id": row.service_id,
                    "date": row.date,
                    "exception_type": row.exception_type,
                    "feed_id": feed_id,
                }
                records.append(record)

            await self.session.execute(
                insert(GTFSCalendarDate).values(records).on_conflict_do_nothing()
            )
            logger.info(f"Persisted {len(records)} calendar date records")

    async def _record_feed_info(self, feed: gk.Feed, feed_id: str, feed_url: str):
        """Record feed metadata."""
        feed_info = {
            "feed_id": feed_id,
            "feed_url": feed_url,
            "downloaded_at": datetime.utcnow(),
            "feed_start_date": getattr(feed, "feed_info", {}).get("start_date"),
            "feed_end_date": getattr(feed, "feed_info", {}).get("end_date"),
            "stop_count": len(feed.stops) if feed.stops is not None else 0,
            "route_count": len(feed.routes) if feed.routes is not None else 0,
            "trip_count": len(feed.trips) if feed.trips is not None else 0,
        }

        await self.session.execute(insert(GTFSFeedInfo).values(feed_info))
        logger.info(f"Recorded feed info for {feed_id}")

    def _convert_time_to_interval(self, time_str: Optional[str]) -> Optional[str]:
        """Convert GTFS time string (HH:MM:SS) to PostgreSQL interval format."""
        if time_str is None:
            return None

        try:
            # Handle times > 24h (e.g., 26:30:00 for 2:30 AM next day)
            hours, minutes, seconds = map(int, time_str.split(":"))
            return f"{hours} hours {minutes} minutes {seconds} seconds"
        except (ValueError, AttributeError):
            logger.warning(f"Invalid time format: {time_str}")
            return None
