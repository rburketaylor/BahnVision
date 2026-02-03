import asyncio
import logging
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional, cast

import httpx
import polars as pl
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.gtfs import (
    GTFSFeedInfo,
)

logger = logging.getLogger(__name__)


class _ConnectionContext:
    """Async context manager that yields a raw asyncpg connection.

    Manages the lifecycle of a pooled SQLAlchemy connection and yields
    the underlying asyncpg connection for COPY operations.
    """

    def __init__(self, engine):
        self._engine = engine
        self._sa_conn = None
        self._asyncpg_conn = None

    async def __aenter__(self):
        self._sa_conn = await self._engine.connect()
        dbapi_conn = await self._sa_conn.get_raw_connection()
        self._asyncpg_conn = dbapi_conn.driver_connection
        return self._asyncpg_conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._sa_conn.close()


def _clean_value(val):
    """Convert common NA/NaN values and numpy scalars to Python native types."""
    if val is None:
        return None

    try:
        if val != val:  # noqa: PLR0124 - NaN != NaN
            return None
    except Exception:
        pass

    # Convert numpy scalar types to Python native types when present.
    if hasattr(val, "item"):
        try:
            return val.item()
        except Exception:
            return val
    return val


class GTFSFeedImporter:
    """Import GTFS feed into PostgreSQL using Polars + PostgreSQL COPY."""

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
        """Internal method to import feed from path using fast COPY with parallelization."""
        logger.info(f"Loading GTFS feed from {feed_path}")

        if not feed_path.exists():
            raise FileNotFoundError(f"GTFS feed not found: {feed_path}")

        is_zip = feed_path.is_file() and zipfile.is_zipfile(feed_path)
        if not is_zip and not feed_path.is_dir():
            raise ValueError("GTFS feed must be a .zip file or a directory")

        # Generate feed_id for tracking
        feed_id = f"gtfs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Truncate all GTFS tables for clean import
        logger.info("Truncating existing GTFS data...")
        await self._truncate_all_tables()

        if is_zip:
            with zipfile.ZipFile(feed_path) as zf:
                stops_df = self._read_gtfs_table(zf, "stops.txt")
                routes_df = self._read_gtfs_table(zf, "routes.txt")
                trips_df = self._read_gtfs_table(zf, "trips.txt")
                calendar_df = self._read_gtfs_table(zf, "calendar.txt")
                calendar_dates_df = self._read_gtfs_table(zf, "calendar_dates.txt")
                feed_info_df = self._read_gtfs_table(zf, "feed_info.txt")

                logger.info(
                    f"Persisting GTFS feed {feed_id} to database using parallel COPY..."
                )

                # Phase 1: Parallel import of independent tables (stops, routes, calendar)
                # These have no dependencies on each other
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._copy_stops(stops_df, feed_id))
                        tg.create_task(self._copy_routes(routes_df, feed_id))
                        tg.create_task(
                            self._copy_calendar(calendar_df, calendar_dates_df, feed_id)
                        )
                except* Exception:  # type: ignore
                    # ExceptionGroup handling for Python 3.11+
                    logger.exception("Errors during parallel independent table import")
                    raise

                # Phase 2: Import dependent tables (trips depends on routes, calendar)
                await self._copy_trips(trips_df, feed_id)

                # Phase 3: Import stop_times (depends on trips, stops)
                await self._copy_stop_times_from_zip(zf, feed_id)
        else:
            stops_df = self._read_gtfs_table(feed_path, "stops.txt")
            routes_df = self._read_gtfs_table(feed_path, "routes.txt")
            trips_df = self._read_gtfs_table(feed_path, "trips.txt")
            calendar_df = self._read_gtfs_table(feed_path, "calendar.txt")
            calendar_dates_df = self._read_gtfs_table(feed_path, "calendar_dates.txt")
            feed_info_df = self._read_gtfs_table(feed_path, "feed_info.txt")

            logger.info(
                f"Persisting GTFS feed {feed_id} to database using parallel COPY..."
            )

            # Phase 1: Parallel import of independent tables
            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._copy_stops(stops_df, feed_id))
                    tg.create_task(self._copy_routes(routes_df, feed_id))
                    tg.create_task(
                        self._copy_calendar(calendar_df, calendar_dates_df, feed_id)
                    )
            except* Exception:  # type: ignore
                logger.exception("Errors during parallel independent table import")
                raise

            # Phase 2: Import dependent tables
            await self._copy_trips(trips_df, feed_id)

            # Phase 3: Import stop_times
            await self._copy_stop_times_from_path(feed_path, feed_id)

        feed_start_date, feed_end_date = self._resolve_feed_dates(
            feed_info_df, calendar_df
        )
        stop_count = 0 if stops_df is None else stops_df.height
        route_count = 0 if routes_df is None else routes_df.height
        trip_count = 0 if trips_df is None else trips_df.height

        await self._record_feed_info(
            feed_id=feed_id,
            feed_url=feed_url,
            feed_start_date=feed_start_date,
            feed_end_date=feed_end_date,
            stop_count=stop_count,
            route_count=route_count,
            trip_count=trip_count,
        )

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
        # Use explicit ALTER TABLE statements to avoid SQL injection concerns
        # (table names are hardcoded, logging mode is validated from settings)
        if self.settings.gtfs_use_unlogged_tables:
            await self.session.execute(text("ALTER TABLE gtfs_stops SET UNLOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_routes SET UNLOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_trips SET UNLOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_stop_times SET UNLOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_calendar SET UNLOGGED"))
            await self.session.execute(
                text("ALTER TABLE gtfs_calendar_dates SET UNLOGGED")
            )
            await self.session.execute(text("ALTER TABLE gtfs_feed_info SET UNLOGGED"))
            logger.info("GTFS tables set to UNLOGGED mode")
        else:
            await self.session.execute(text("ALTER TABLE gtfs_stops SET LOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_routes SET LOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_trips SET LOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_stop_times SET LOGGED"))
            await self.session.execute(text("ALTER TABLE gtfs_calendar SET LOGGED"))
            await self.session.execute(
                text("ALTER TABLE gtfs_calendar_dates SET LOGGED")
            )
            await self.session.execute(text("ALTER TABLE gtfs_feed_info SET LOGGED"))
            logger.info("GTFS tables set to LOGGED mode")
        await self.session.commit()

    def _get_asyncpg_conn(self):
        """Get raw asyncpg connection for COPY operations.

        Creates a dedicated connection for each COPY operation to support
        concurrent COPY operations in parallel tasks.
        """
        # Import here to avoid circular dependency
        from app.core.database import engine

        # Create and return a connection context that will acquire
        # a dedicated connection when entered
        return _ConnectionContext(engine)

    def _read_gtfs_table(
        self, source: zipfile.ZipFile | Path, filename: str
    ) -> pl.DataFrame | None:
        if isinstance(source, Path):
            path = source / filename
            if not path.exists():
                return None
            return pl.read_csv(path, null_values=[""], infer_schema_length=1000)

        member_name = filename
        try:
            source.getinfo(member_name)
        except KeyError:
            alt_member = next(
                (name for name in source.namelist() if name.endswith(f"/{filename}")),
                None,
            )
            if alt_member is None:
                return None
            member_name = alt_member

        with source.open(member_name) as f:
            return pl.read_csv(f, null_values=[""], infer_schema_length=1000)

    def _parse_gtfs_date_value(self, val) -> date | None:
        cleaned = _clean_value(val)
        if cleaned is None:
            return None

        # Sometimes datetime.datetime appears in test doubles; normalize to date.
        if isinstance(cleaned, datetime):
            return cleaned.date()

        if isinstance(cleaned, date):
            return cleaned

        if hasattr(cleaned, "date") and not isinstance(cleaned, str):
            try:
                return cleaned.date()
            except Exception:
                pass

        text_val = str(cleaned).strip()
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(text_val, fmt).date()
            except ValueError:
                continue
        return None

    def _resolve_feed_dates(
        self, feed_info_df: pl.DataFrame | None, calendar_df: pl.DataFrame | None
    ) -> tuple[date | None, date | None]:
        if feed_info_df is not None and not feed_info_df.is_empty():
            start_col = (
                "feed_start_date"
                if "feed_start_date" in feed_info_df.columns
                else "start_date"
            )
            end_col = (
                "feed_end_date"
                if "feed_end_date" in feed_info_df.columns
                else "end_date"
            )
            feed_start = (
                self._parse_gtfs_date_value(feed_info_df[start_col].to_list()[0])
                if start_col in feed_info_df.columns and feed_info_df.height >= 1
                else None
            )
            feed_end = (
                self._parse_gtfs_date_value(feed_info_df[end_col].to_list()[0])
                if end_col in feed_info_df.columns and feed_info_df.height >= 1
                else None
            )
            if feed_start or feed_end:
                return feed_start, feed_end

        if calendar_df is None or calendar_df.is_empty():
            return None, None

        start_val = calendar_df.select(pl.col("start_date").min()).to_series().to_list()
        end_val = calendar_df.select(pl.col("end_date").max()).to_series().to_list()
        feed_start = self._parse_gtfs_date_value(start_val[0]) if start_val else None
        feed_end = self._parse_gtfs_date_value(end_val[0]) if end_val else None
        return feed_start, feed_end

    async def _copy_polars_df(
        self, df: pl.DataFrame, table_name: str, columns: list[str]
    ) -> None:
        if df.is_empty():
            return

        conn_ctx = self._get_asyncpg_conn()
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                tmp_path = tmp.name

            df.write_csv(
                tmp_path,
                include_header=False,
                separator=",",
                quote_style="necessary",
            )

            async with conn_ctx as asyncpg_conn:
                with open(tmp_path, "rb") as f:
                    await asyncpg_conn.copy_to_table(
                        table_name,
                        source=f,
                        columns=columns,
                        format="csv",
                    )
        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    logger.warning("Failed to delete temp file: %s", tmp_path)

    async def _copy_stops(self, stops_df: pl.DataFrame | None, feed_id: str):
        """Bulk insert stops using PostgreSQL COPY."""
        if stops_df is None or stops_df.is_empty():
            return

        logger.info(f"Preparing {stops_df.height} stops for COPY...")

        df = stops_df
        if "location_type" not in df.columns:
            df = df.with_columns(pl.lit(0).alias("location_type"))
        for col in ["parent_station", "platform_code"]:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))

        export_df = df.with_columns(
            pl.col("location_type").fill_null(0).cast(pl.Int16),
            pl.lit(feed_id).alias("feed_id"),
        ).select(
            [
                "stop_id",
                "stop_name",
                "stop_lat",
                "stop_lon",
                "location_type",
                "parent_station",
                "platform_code",
                "feed_id",
            ]
        )

        await self._copy_polars_df(
            export_df,
            "gtfs_stops",
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
        )

        logger.info(f"Copied {stops_df.height} stops")

    async def _copy_routes(self, routes_df: pl.DataFrame | None, feed_id: str):
        """Bulk insert routes using PostgreSQL COPY."""
        if routes_df is None or routes_df.is_empty():
            return

        logger.info(f"Preparing {routes_df.height} routes for COPY...")

        df = routes_df
        for col in ["agency_id", "route_short_name", "route_long_name", "route_color"]:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))

        export_df = df.with_columns(pl.lit(feed_id).alias("feed_id")).select(
            [
                "route_id",
                "agency_id",
                "route_short_name",
                "route_long_name",
                "route_type",
                "route_color",
                "feed_id",
            ]
        )

        await self._copy_polars_df(
            export_df,
            "gtfs_routes",
            columns=[
                "route_id",
                "agency_id",
                "route_short_name",
                "route_long_name",
                "route_type",
                "route_color",
                "feed_id",
            ],
        )

        logger.info(f"Copied {routes_df.height} routes")

    async def _copy_trips(self, trips_df: pl.DataFrame | None, feed_id: str):
        """Bulk insert trips using PostgreSQL COPY."""
        if trips_df is None or trips_df.is_empty():
            return

        logger.info(f"Preparing {trips_df.height} trips for COPY...")

        df = trips_df
        if "trip_headsign" not in df.columns:
            df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias("trip_headsign"))
        if "direction_id" not in df.columns:
            df = df.with_columns(pl.lit(None).cast(pl.Int16).alias("direction_id"))
        else:
            df = df.with_columns(pl.col("direction_id").cast(pl.Int16, strict=False))

        export_df = df.with_columns(pl.lit(feed_id).alias("feed_id")).select(
            [
                "trip_id",
                "route_id",
                "service_id",
                "trip_headsign",
                "direction_id",
                "feed_id",
            ]
        )

        await self._copy_polars_df(
            export_df,
            "gtfs_trips",
            columns=[
                "trip_id",
                "route_id",
                "service_id",
                "trip_headsign",
                "direction_id",
                "feed_id",
            ],
        )

        logger.info(f"Copied {trips_df.height} trips")

    async def _copy_stop_times_batch(self, stop_times_df: pl.DataFrame, feed_id: str):
        if stop_times_df.is_empty():
            return

        df = stop_times_df
        for col in ["pickup_type", "drop_off_type"]:
            if col not in df.columns:
                df = df.with_columns(pl.lit(0).alias(col))

        export_df = df.with_columns(
            pl.col("arrival_time").cast(pl.Utf8).str.strip_chars().replace("", None),
            pl.col("departure_time").cast(pl.Utf8).str.strip_chars().replace("", None),
            pl.col("stop_sequence").cast(pl.Int32),
            pl.col("pickup_type").fill_null(0).cast(pl.Int8),
            pl.col("drop_off_type").fill_null(0).cast(pl.Int8),
            pl.lit(feed_id).alias("feed_id"),
        ).select(
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
        )

        await self._copy_polars_df(
            export_df,
            "gtfs_stop_times",
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
        )

    def _read_csv_batched(self, source, *, batch_size: int):
        schema = {
            "trip_id": pl.Utf8,
            "stop_id": pl.Utf8,
            "arrival_time": pl.Utf8,
            "departure_time": pl.Utf8,
            "stop_sequence": pl.Int32,
            "pickup_type": pl.Int8,
            "drop_off_type": pl.Int8,
        }

        read_csv_batched = pl.read_csv_batched
        try:
            return read_csv_batched(
                source,
                batch_size=batch_size,
                null_values=[""],
                infer_schema_length=1000,
                schema_overrides=schema,
            )
        except TypeError:
            legacy_read_csv = cast(Callable[..., Any], read_csv_batched)
            return legacy_read_csv(
                source,
                batch_size=batch_size,
                null_values=[""],
                infer_schema_length=1000,
                dtypes=schema,
            )

    async def _copy_stop_times_from_zip(
        self, zf: zipfile.ZipFile, feed_id: str, *, batch_size: int = 500_000
    ):
        member_name = "stop_times.txt"
        try:
            zf.getinfo(member_name)
        except KeyError:
            alt_member = next(
                (name for name in zf.namelist() if name.endswith("/stop_times.txt")),
                None,
            )
            if alt_member is None:
                logger.info("No stop_times.txt found in GTFS feed")
                await self._recreate_stop_times_indexes_and_fks()
                return
            member_name = alt_member

        # Extract stop_times.txt to a temp file since polars read_csv_batched
        # doesn't support ZipExtFile objects (requires file path or bytes)
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                tmp_path = tmp.name
                with zf.open(member_name) as f:
                    # Copy in chunks to avoid loading entire file into memory
                    while True:
                        chunk = f.read(8 * 1024 * 1024)  # 8MB chunks
                        if not chunk:
                            break
                        tmp.write(chunk)

            logger.info("Extracted stop_times.txt to temp file for processing")

            # Process batches in parallel with a semaphore to limit concurrency
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent COPY operations

            async def process_batch(batch_df: pl.DataFrame, batch_num: int) -> None:
                async with semaphore:
                    await self._copy_stop_times_batch(batch_df, feed_id)
                    if batch_num % 10 == 0:
                        logger.info("Copied %s stop_times batches...", batch_num)

            # Read all batches first (memory efficient, as we get lazy iterators)
            reader = self._read_csv_batched(tmp_path, batch_size=batch_size)

            # Collect batches and process them in parallel
            # Using a queue approach to avoid loading all batches into memory at once
            batch_tasks = []
            batch_count = 0
            while True:
                batches = reader.next_batches(1)
                if not batches:
                    break
                batch_count += 1
                batch_tasks.append(
                    asyncio.create_task(process_batch(batches[0], batch_count))
                )

                # Wait for some tasks to complete if we have many pending
                # This prevents memory buildup while maintaining parallelism
                if len(batch_tasks) >= 6:  # 2x the semaphore size
                    # Wait for at least half to complete before adding more
                    done, pending = await asyncio.wait(
                        batch_tasks, return_when=asyncio.FIRST_COMPLETED
                    )
                    batch_tasks = list(pending)

            # Wait for remaining tasks
            if batch_tasks:
                await asyncio.gather(*batch_tasks)

        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    logger.warning("Failed to delete temp file: %s", tmp_path)

        await self._recreate_stop_times_indexes_and_fks()

    async def _copy_stop_times_from_path(
        self, feed_path: Path, feed_id: str, *, batch_size: int = 500_000
    ):
        stop_times_path = feed_path / "stop_times.txt"
        if not stop_times_path.exists():
            logger.info("No stop_times.txt found at %s", stop_times_path)
            await self._recreate_stop_times_indexes_and_fks()
            return

        # Process batches in parallel with a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent COPY operations

        async def process_batch(batch_df: pl.DataFrame, batch_num: int) -> None:
            async with semaphore:
                await self._copy_stop_times_batch(batch_df, feed_id)
                if batch_num % 10 == 0:
                    logger.info("Copied %s stop_times batches...", batch_num)

        reader = self._read_csv_batched(str(stop_times_path), batch_size=batch_size)

        # Collect batches and process them in parallel
        batch_tasks = []
        batch_count = 0
        while True:
            batches = reader.next_batches(1)
            if not batches:
                break
            batch_count += 1
            batch_tasks.append(
                asyncio.create_task(process_batch(batches[0], batch_count))
            )

            # Wait for some tasks to complete if we have many pending
            if len(batch_tasks) >= 6:  # 2x the semaphore size
                done, pending = await asyncio.wait(
                    batch_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                batch_tasks = list(pending)

        # Wait for remaining tasks
        if batch_tasks:
            await asyncio.gather(*batch_tasks)

        await self._recreate_stop_times_indexes_and_fks()

    async def _recreate_stop_times_indexes_and_fks(self) -> None:
        logger.info("Recreating indexes and foreign keys on stop_times...")

        await self.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_stop ON gtfs_stop_times(stop_id)"
            )
        )
        await self.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_trip ON gtfs_stop_times(trip_id)"
            )
        )
        await self.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_departure_lookup ON gtfs_stop_times(stop_id, departure_time)"
            )
        )

        await self.session.execute(
            text(
                """
                DO $$
                BEGIN
                    ALTER TABLE gtfs_stop_times ADD CONSTRAINT gtfs_stop_times_stop_id_fkey
                        FOREIGN KEY (stop_id) REFERENCES gtfs_stops(stop_id);
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END $$;
                """
            )
        )
        await self.session.execute(
            text(
                """
                DO $$
                BEGIN
                    ALTER TABLE gtfs_stop_times ADD CONSTRAINT gtfs_stop_times_trip_id_fkey
                        FOREIGN KEY (trip_id) REFERENCES gtfs_trips(trip_id);
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END $$;
                """
            )
        )
        await self.session.commit()

    async def _copy_calendar(
        self,
        calendar_df: pl.DataFrame | None,
        calendar_dates_df: pl.DataFrame | None,
        feed_id: str,
    ):
        """Bulk insert calendar data using PostgreSQL COPY."""
        if calendar_df is not None and not calendar_df.is_empty():
            logger.info(f"Preparing {calendar_df.height} calendar records for COPY...")

            export_df = calendar_df.with_columns(
                pl.col("monday").cast(pl.Int8),
                pl.col("tuesday").cast(pl.Int8),
                pl.col("wednesday").cast(pl.Int8),
                pl.col("thursday").cast(pl.Int8),
                pl.col("friday").cast(pl.Int8),
                pl.col("saturday").cast(pl.Int8),
                pl.col("sunday").cast(pl.Int8),
                pl.coalesce(
                    [
                        pl.col("start_date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y%m%d", strict=False),
                        pl.col("start_date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y-%m-%d", strict=False),
                    ]
                ).alias("start_date"),
                pl.coalesce(
                    [
                        pl.col("end_date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y%m%d", strict=False),
                        pl.col("end_date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y-%m-%d", strict=False),
                    ]
                ).alias("end_date"),
                pl.lit(feed_id).alias("feed_id"),
            ).select(
                [
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
                ]
            )

            await self._copy_polars_df(
                export_df,
                "gtfs_calendar",
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
            )

            logger.info(f"Copied {calendar_df.height} calendar records")

        if calendar_dates_df is not None and not calendar_dates_df.is_empty():
            logger.info(
                f"Preparing {calendar_dates_df.height} calendar date records for COPY..."
            )

            export_df = calendar_dates_df.with_columns(
                pl.coalesce(
                    [
                        pl.col("date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y%m%d", strict=False),
                        pl.col("date")
                        .cast(pl.Utf8)
                        .str.strptime(pl.Date, "%Y-%m-%d", strict=False),
                    ]
                ).alias("date"),
                pl.col("exception_type").cast(pl.Int16),
                pl.lit(feed_id).alias("feed_id"),
            ).select(["service_id", "date", "exception_type", "feed_id"])

            await self._copy_polars_df(
                export_df,
                "gtfs_calendar_dates",
                columns=["service_id", "date", "exception_type", "feed_id"],
            )

            logger.info(f"Copied {calendar_dates_df.height} calendar date records")

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

    async def _record_feed_info(
        self,
        *,
        feed_id: str,
        feed_url: str,
        feed_start_date: date | None,
        feed_end_date: date | None,
        stop_count: int,
        route_count: int,
        trip_count: int,
    ):
        """Record feed metadata."""
        feed_info = {
            "feed_id": feed_id,
            "feed_url": feed_url,
            "downloaded_at": datetime.utcnow(),
            "feed_start_date": feed_start_date,
            "feed_end_date": feed_end_date,
            "stop_count": stop_count,
            "route_count": route_count,
            "trip_count": trip_count,
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
