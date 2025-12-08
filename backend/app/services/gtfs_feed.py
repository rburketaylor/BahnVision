import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import gtfs_kit as gk
import httpx
import pandas as pd
from pandas import DataFrame
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.gtfs import (
    GTFSFeedInfo,
)

logger = logging.getLogger(__name__)


def _clean_value(val):
    """Convert pandas NA/NaN values and numpy types to Python native types for PostgreSQL."""
    if val is None:
        return None
    if pd.isna(val):
        return None
    # Convert numpy types to Python native types
    if hasattr(val, "item"):
        return val.item()
    return val


def _escape_tsv(val) -> str:
    """Escape value for TSV format. Returns \\N for NULL."""
    if val is None:
        return "\\N"
    # Escape tabs, newlines, backslashes
    s = str(val)
    s = (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return s


class GTFSFeedImporter:
    """Import GTFS feed into PostgreSQL using gtfs-kit + COPY for speed."""

    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings
        self.storage_path = Path(settings.gtfs_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def import_feed(self, feed_url: Optional[str] = None) -> str:
        """Download, parse, and persist GTFS feed."""
        feed_url = feed_url or self.settings.gtfs_feed_url
        self._validate_feed_url(feed_url)

        # 1. Download feed
        feed_path = await self._download_feed(feed_url)

        return await self._import_from_path(feed_path, feed_url)

    async def import_from_path(self, feed_path: Path) -> str:
        """Import GTFS feed from a local file path."""
        return await self._import_from_path(feed_path, f"file://{feed_path}")

    def _validate_feed_url(self, feed_url: str) -> None:
        """Basic allowlist for feed URLs to avoid arbitrary downloads."""
        if not feed_url.startswith("http://") and not feed_url.startswith("https://"):
            raise ValueError("GTFS feed URL must be http(s)")

    async def _import_from_path(self, feed_path: Path, feed_url: str) -> str:
        """Internal method to import feed from path using fast COPY."""
        # 1. Load with gtfs-kit (in-memory Pandas DataFrames)
        logger.info(f"Loading GTFS feed from {feed_path}")
        feed = gk.read_feed(feed_path, dist_units="km")

        # 2. Generate feed_id for tracking
        feed_id = f"gtfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 3. Truncate all GTFS tables for clean import
        logger.info("Truncating existing GTFS data...")
        await self._truncate_all_tables()

        # 4. Persist using fast COPY
        logger.info(f"Persisting GTFS feed {feed_id} to database using COPY...")
        await self._copy_stops(feed.stops, feed_id)
        await self._copy_routes(feed.routes, feed_id)
        await self._copy_trips(feed.trips, feed_id)
        await self._copy_stop_times(feed.stop_times, feed_id)
        await self._copy_calendar(feed.calendar, feed.calendar_dates, feed_id)

        # 5. Record feed metadata
        await self._record_feed_info(feed, feed_id, feed_url)

        logger.info(f"Successfully imported GTFS feed {feed_id}")
        return feed_id

    async def _truncate_all_tables(self):
        """Truncate all GTFS tables for clean import."""
        # Drop foreign keys on stop_times for faster COPY (they'll be recreated after)
        await self.session.execute(
            text(
                "ALTER TABLE gtfs_stop_times DROP CONSTRAINT IF EXISTS gtfs_stop_times_stop_id_fkey"
            )
        )
        await self.session.execute(
            text(
                "ALTER TABLE gtfs_stop_times DROP CONSTRAINT IF EXISTS gtfs_stop_times_trip_id_fkey"
            )
        )

        # Drop indexes on stop_times for faster COPY (they'll be recreated after)
        await self.session.execute(
            text("DROP INDEX IF EXISTS idx_gtfs_stop_times_stop")
        )
        await self.session.execute(
            text("DROP INDEX IF EXISTS idx_gtfs_stop_times_trip")
        )
        await self.session.execute(
            text("DROP INDEX IF EXISTS idx_gtfs_stop_times_departure_lookup")
        )

        # Order matters due to foreign key constraints - truncate in reverse dependency order
        # Use CASCADE to handle any FK constraints
        await self.session.execute(
            text(
                "TRUNCATE TABLE gtfs_stop_times, gtfs_calendar_dates, gtfs_calendar, gtfs_trips, gtfs_routes, gtfs_stops, gtfs_feed_info CASCADE"
            )
        )
        await self.session.commit()
        logger.info("Truncated all GTFS tables (indexes and FKs dropped)")

        # Ensure logging mode matches configuration
        logging_mode = (
            "UNLOGGED" if self.settings.gtfs_use_unlogged_tables else "LOGGED"
        )
        for table in [
            "gtfs_stops",
            "gtfs_routes",
            "gtfs_trips",
            "gtfs_stop_times",
            "gtfs_calendar",
            "gtfs_calendar_dates",
            "gtfs_feed_info",
        ]:
            await self.session.execute(text(f"ALTER TABLE {table} SET {logging_mode}"))
        await self.session.commit()
        logger.info("GTFS tables set to %s mode", logging_mode)

    async def _get_asyncpg_conn(self):
        """Get raw asyncpg connection for COPY operations."""
        raw_conn = await self.session.connection()
        dbapi_conn = await raw_conn.get_raw_connection()
        # SQLAlchemy wraps asyncpg, need to get the actual driver connection
        return dbapi_conn.driver_connection

    async def _copy_stops(self, stops_df: DataFrame, feed_id: str):
        """Bulk insert stops using PostgreSQL COPY."""
        if stops_df is None or stops_df.empty:
            return

        logger.info(f"Preparing {len(stops_df)} stops for COPY...")

        # Build TSV data
        lines = []
        for row in stops_df.itertuples():
            line = "\t".join(
                [
                    _escape_tsv(row.stop_id),
                    _escape_tsv(row.stop_name),
                    _escape_tsv(_clean_value(getattr(row, "stop_lat", None))),
                    _escape_tsv(_clean_value(getattr(row, "stop_lon", None))),
                    _escape_tsv(_clean_value(getattr(row, "location_type", None)) or 0),
                    _escape_tsv(_clean_value(getattr(row, "parent_station", None))),
                    _escape_tsv(_clean_value(getattr(row, "platform_code", None))),
                    _escape_tsv(feed_id),
                ]
            )
            lines.append(line)

        tsv_data = "\n".join(lines)

        asyncpg_conn = await self._get_asyncpg_conn()
        await asyncpg_conn.copy_to_table(
            "gtfs_stops",
            source=io.BytesIO(tsv_data.encode("utf-8")),
            columns=[
                "stop_id",
                "stop_name",
                "stop_lat",
                "stop_lon",
                "location_type",
                "parent_station",
                "platform_code",
                "feed_id",
            ],
            format="text",
        )

        logger.info(f"Copied {len(stops_df)} stops")

    async def _copy_routes(self, routes_df: DataFrame, feed_id: str):
        """Bulk insert routes using PostgreSQL COPY."""
        if routes_df is None or routes_df.empty:
            return

        logger.info(f"Preparing {len(routes_df)} routes for COPY...")

        lines = []
        for row in routes_df.itertuples():
            line = "\t".join(
                [
                    _escape_tsv(row.route_id),
                    _escape_tsv(_clean_value(getattr(row, "agency_id", None))),
                    _escape_tsv(_clean_value(getattr(row, "route_short_name", None))),
                    _escape_tsv(_clean_value(getattr(row, "route_long_name", None))),
                    _escape_tsv(_clean_value(row.route_type)),
                    _escape_tsv(_clean_value(getattr(row, "route_color", None))),
                    _escape_tsv(feed_id),
                ]
            )
            lines.append(line)

        tsv_data = "\n".join(lines)

        asyncpg_conn = await self._get_asyncpg_conn()
        await asyncpg_conn.copy_to_table(
            "gtfs_routes",
            source=io.BytesIO(tsv_data.encode("utf-8")),
            columns=[
                "route_id",
                "agency_id",
                "route_short_name",
                "route_long_name",
                "route_type",
                "route_color",
                "feed_id",
            ],
            format="text",
        )

        logger.info(f"Copied {len(routes_df)} routes")

    async def _copy_trips(self, trips_df: DataFrame, feed_id: str):
        """Bulk insert trips using PostgreSQL COPY."""
        if trips_df is None or trips_df.empty:
            return

        logger.info(f"Preparing {len(trips_df)} trips for COPY...")

        lines = []
        for row in trips_df.itertuples():
            line = "\t".join(
                [
                    _escape_tsv(row.trip_id),
                    _escape_tsv(row.route_id),
                    _escape_tsv(row.service_id),
                    _escape_tsv(_clean_value(getattr(row, "trip_headsign", None))),
                    _escape_tsv(_clean_value(getattr(row, "direction_id", None))),
                    _escape_tsv(feed_id),
                ]
            )
            lines.append(line)

        tsv_data = "\n".join(lines)

        asyncpg_conn = await self._get_asyncpg_conn()
        await asyncpg_conn.copy_to_table(
            "gtfs_trips",
            source=io.BytesIO(tsv_data.encode("utf-8")),
            columns=[
                "trip_id",
                "route_id",
                "service_id",
                "trip_headsign",
                "direction_id",
                "feed_id",
            ],
            format="text",
        )

        logger.info(f"Copied {len(trips_df)} trips")

    async def _copy_stop_times(self, stop_times_df: DataFrame, feed_id: str):
        """Bulk insert stop times using PostgreSQL COPY via temp file for large datasets."""
        if stop_times_df is None or stop_times_df.empty:
            return

        logger.info(f"Preparing {len(stop_times_df)} stop times for COPY...")

        # Prepare DataFrame for TSV export - much faster than row-by-row
        df = stop_times_df.copy()

        # Clean string columns - escape special characters for TSV
        def clean_for_tsv(val):
            if pd.isna(val):
                return None
            val = _clean_value(val)  # Convert numpy types
            if isinstance(val, str):
                # Escape backslashes, tabs, newlines for TSV format
                return (
                    val.replace("\\", "\\\\")
                    .replace("\t", "\\t")
                    .replace("\n", "\\n")
                    .replace("\r", "\\r")
                )
            return val

        df["trip_id"] = df["trip_id"].apply(clean_for_tsv)
        df["stop_id"] = df["stop_id"].apply(clean_for_tsv)

        # Convert time columns to interval format
        df["arrival_time"] = df["arrival_time"].apply(
            lambda x: self._convert_time_to_interval(_clean_value(x))
        )
        df["departure_time"] = df["departure_time"].apply(
            lambda x: self._convert_time_to_interval(_clean_value(x))
        )

        # Clean and set defaults for optional columns
        df["pickup_type"] = df.get("pickup_type", 0).fillna(0).astype(int)
        df["drop_off_type"] = df.get("drop_off_type", 0).fillna(0).astype(int)
        df["stop_sequence"] = df["stop_sequence"].apply(_clean_value)
        df["feed_id"] = feed_id

        # Select and order columns for COPY
        export_df = df[
            [
                "trip_id",
                "stop_id",
                "arrival_time",
                "departure_time",
                "stop_sequence",
                "pickup_type",
                "drop_off_type",
                "feed_id",
            ]
        ]

        logger.info(f"Writing {len(export_df)} stop times to TSV buffer for COPY...")

        if export_df.empty:
            logger.info("No stop_times rows to copy; restoring indexes/FKs only")
        else:
            lines = []
            for row in export_df.itertuples(index=False):
                lines.append(
                    "\t".join(
                        [
                            _escape_tsv(row.trip_id),
                            _escape_tsv(row.stop_id),
                            _escape_tsv(row.arrival_time),
                            _escape_tsv(row.departure_time),
                            _escape_tsv(row.stop_sequence),
                            _escape_tsv(row.pickup_type),
                            _escape_tsv(row.drop_off_type),
                            _escape_tsv(row.feed_id),
                        ]
                    )
                )

            tsv_data = "\n".join(lines)

            asyncpg_conn = await self._get_asyncpg_conn()
            try:
                await asyncpg_conn.copy_to_table(
                    "gtfs_stop_times",
                    source=io.BytesIO(tsv_data.encode("utf-8")),
                    columns=[
                        "trip_id",
                        "stop_id",
                        "arrival_time",
                        "departure_time",
                        "stop_sequence",
                        "pickup_type",
                        "drop_off_type",
                        "feed_id",
                    ],
                    format="text",
                )
                logger.info(f"Copied {len(export_df)} stop times via asyncpg COPY")
            except Exception as exc:
                logger.error("COPY failed: %s", exc)
                raise

        # Recreate indexes and foreign keys after bulk load (even if empty)
        logger.info("Recreating indexes and foreign keys on stop_times...")
        await self.session.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_stop ON gtfs_stop_times(stop_id);
                CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_trip ON gtfs_stop_times(trip_id);
                CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_departure_lookup ON gtfs_stop_times(stop_id, departure_time);
                ALTER TABLE gtfs_stop_times ADD CONSTRAINT IF NOT EXISTS gtfs_stop_times_stop_id_fkey FOREIGN KEY (stop_id) REFERENCES gtfs_stops(stop_id);
                ALTER TABLE gtfs_stop_times ADD CONSTRAINT IF NOT EXISTS gtfs_stop_times_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES gtfs_trips(trip_id);
                """
            )
        )
        await self.session.commit()

    async def _copy_calendar(
        self, calendar_df: DataFrame, calendar_dates_df: DataFrame, feed_id: str
    ):
        """Bulk insert calendar data using PostgreSQL COPY."""
        asyncpg_conn = await self._get_asyncpg_conn()

        # Calendar
        if calendar_df is not None and not calendar_df.empty:
            logger.info(f"Preparing {len(calendar_df)} calendar records for COPY...")

            lines = []
            for row in calendar_df.itertuples():
                line = "\t".join(
                    [
                        _escape_tsv(row.service_id),
                        _escape_tsv(_clean_value(row.monday)),
                        _escape_tsv(_clean_value(row.tuesday)),
                        _escape_tsv(_clean_value(row.wednesday)),
                        _escape_tsv(_clean_value(row.thursday)),
                        _escape_tsv(_clean_value(row.friday)),
                        _escape_tsv(_clean_value(row.saturday)),
                        _escape_tsv(_clean_value(row.sunday)),
                        _escape_tsv(row.start_date),
                        _escape_tsv(row.end_date),
                        _escape_tsv(feed_id),
                    ]
                )
                lines.append(line)

            tsv_data = "\n".join(lines)

            await asyncpg_conn.copy_to_table(
                "gtfs_calendar",
                source=io.BytesIO(tsv_data.encode("utf-8")),
                columns=[
                    "service_id",
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                    "start_date",
                    "end_date",
                    "feed_id",
                ],
                format="text",
            )

            logger.info(f"Copied {len(calendar_df)} calendar records")

        # Calendar dates
        if calendar_dates_df is not None and not calendar_dates_df.empty:
            logger.info(
                f"Preparing {len(calendar_dates_df)} calendar date records for COPY..."
            )

            lines = []
            for row in calendar_dates_df.itertuples():
                line = "\t".join(
                    [
                        _escape_tsv(row.service_id),
                        _escape_tsv(row.date),
                        _escape_tsv(_clean_value(row.exception_type)),
                        _escape_tsv(feed_id),
                    ]
                )
                lines.append(line)

            tsv_data = "\n".join(lines)

            await asyncpg_conn.copy_to_table(
                "gtfs_calendar_dates",
                source=io.BytesIO(tsv_data.encode("utf-8")),
                columns=["service_id", "date", "exception_type", "feed_id"],
                format="text",
            )

            logger.info(f"Copied {len(calendar_dates_df)} calendar date records")

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

    async def _record_feed_info(self, feed: gk.Feed, feed_id: str, feed_url: str):
        """Record feed metadata."""
        feed_info = {
            "feed_id": feed_id,
            "feed_url": feed_url,
            "downloaded_at": datetime.now(timezone.utc),
            "feed_start_date": getattr(feed, "feed_info", {}).get("start_date"),
            "feed_end_date": getattr(feed, "feed_info", {}).get("end_date"),
            "stop_count": len(feed.stops) if feed.stops is not None else 0,
            "route_count": len(feed.routes) if feed.routes is not None else 0,
            "trip_count": len(feed.trips) if feed.trips is not None else 0,
        }

        await self.session.execute(insert(GTFSFeedInfo).values(feed_info))
        await self.session.commit()
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
