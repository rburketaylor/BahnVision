import asyncio
import csv
import io
import inspect
import logging
import tempfile
import zipfile
from datetime import date, datetime, timezone
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
from app.services.cache import get_cache_service
from app.services.gtfs_import_progress import (
    GTFSImportProgressTrackerProtocol,
    NoOpGTFSImportProgressTracker,
)

logger = logging.getLogger(__name__)


class GTFSFeedValidationError(ValueError):
    """Raised when a GTFS feed is incomplete before final table replacement."""


_REQUIRED_STATIC_COLUMNS: dict[str, set[str]] = {
    "stops.txt": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    "routes.txt": {"route_id", "route_type"},
    "trips.txt": {"trip_id", "route_id", "service_id"},
    "calendar.txt": {
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
    },
    "calendar_dates.txt": {"service_id", "date", "exception_type"},
    "stop_times.txt": {
        "trip_id",
        "stop_id",
        "arrival_time",
        "departure_time",
        "stop_sequence",
    },
}


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
        if self._sa_conn is not None:
            await self._sa_conn.close()
            self._sa_conn = None
            self._asyncpg_conn = None


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


def _parse_gtfs_time_to_seconds(time_value: Any) -> int | None:
    """Parse a GTFS HH:MM:SS value into seconds since service midnight."""
    cleaned = _clean_value(time_value)
    if cleaned is None:
        return None

    try:
        parts = str(cleaned).strip().split(":")
    except Exception:
        return None

    if len(parts) != 3 or not all(part.strip() for part in parts):
        return None

    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None

    if hours < 0 or not 0 <= minutes <= 59 or not 0 <= seconds <= 59:
        return None

    return hours * 3600 + minutes * 60 + seconds


def _gtfs_time_to_seconds_expr(column_name: str) -> pl.Expr:
    """Parse GTFS HH:MM:SS strings into seconds using native Polars expressions."""
    cleaned = pl.col(column_name).str.strip_chars()
    pattern = r"^(\d+):(\d+):(\d+)$"
    hours = cleaned.str.extract(pattern, 1).cast(pl.Int32, strict=False)
    minutes = cleaned.str.extract(pattern, 2).cast(pl.Int32, strict=False)
    seconds = cleaned.str.extract(pattern, 3).cast(pl.Int32, strict=False)

    return (
        pl.when(
            hours.is_not_null() & minutes.is_between(0, 59) & seconds.is_between(0, 59)
        )
        .then((hours * 3600) + (minutes * 60) + seconds)
        .otherwise(None)
        .cast(pl.Int32)
    )


class GTFSFeedImporter:
    """Import GTFS feed into PostgreSQL using Polars + PostgreSQL COPY."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        progress_tracker: GTFSImportProgressTrackerProtocol | None = None,
    ):
        self.session = session
        self.settings = settings
        self.progress_tracker = progress_tracker or NoOpGTFSImportProgressTracker()
        self.storage_path = Path(settings.gtfs_storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def import_feed(self, feed_url: Optional[str] = None) -> str:
        """Download, parse, and persist GTFS feed."""
        feed_url = feed_url or self.settings.gtfs_feed_url
        try:
            await self.progress_tracker.start(
                phase="download",
                message="Downloading GTFS feed",
                percent=0,
            )
            self._validate_feed_url(feed_url)

            # 1. Download feed
            feed_path = await self._download_feed(feed_url)

            return await self._import_from_path(feed_path, feed_url)
        except Exception as exc:
            await self.progress_tracker.fail(exc)
            raise

    async def import_from_path(self, feed_path: Path) -> str:
        """Import GTFS feed from a local file path."""
        try:
            await self.progress_tracker.start(
                phase="read",
                message="Reading GTFS feed",
                percent=5,
            )
            return await self._import_from_path(feed_path, f"file://{feed_path}")
        except Exception as exc:
            await self.progress_tracker.fail(exc)
            raise

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
        stop_times_batch_size = self.settings.gtfs_stop_times_batch_size

        final_load_started = False
        try:
            await self.progress_tracker.update(
                phase="read",
                message="Reading GTFS static tables",
                percent=10,
            )
            if is_zip:
                with zipfile.ZipFile(feed_path) as zf:
                    stops_df = self._read_gtfs_table(zf, "stops.txt")
                    routes_df = self._read_gtfs_table(zf, "routes.txt")
                    trips_df = self._read_gtfs_table(zf, "trips.txt")
                    calendar_df = self._read_gtfs_table(zf, "calendar.txt")
                    calendar_dates_df = self._read_gtfs_table(zf, "calendar_dates.txt")
                    feed_info_df = self._read_gtfs_table(zf, "feed_info.txt")

                    await self.progress_tracker.update(
                        phase="validate",
                        message="Validating GTFS feed",
                        percent=20,
                    )
                    self._validate_static_feed_content(
                        zf,
                        stops_df=stops_df,
                        routes_df=routes_df,
                        trips_df=trips_df,
                        calendar_df=calendar_df,
                        calendar_dates_df=calendar_dates_df,
                    )

                    logger.info("Truncating existing GTFS data...")
                    await self.progress_tracker.update(
                        phase="truncate",
                        message="Replacing existing GTFS tables",
                        percent=25,
                    )
                    await self._truncate_all_tables()
                    final_load_started = True

                    logger.info(
                        f"Persisting GTFS feed {feed_id} to database using parallel COPY..."
                    )

                    # Phase 1: Parallel import of independent tables (stops, routes, calendar)
                    # These have no dependencies on each other
                    await self.progress_tracker.update(
                        phase="copy_core",
                        message="Copying stops, routes, and calendar tables",
                        percent=35,
                    )
                    try:
                        async with asyncio.TaskGroup() as tg:
                            tg.create_task(self._copy_stops(stops_df))
                            tg.create_task(self._copy_routes(routes_df))
                            tg.create_task(
                                self._copy_calendar(calendar_df, calendar_dates_df)
                            )
                    except* Exception:  # type: ignore
                        # ExceptionGroup handling for Python 3.11+
                        logger.exception(
                            "Errors during parallel independent table import"
                        )
                        raise

                    # Phase 2: Import dependent tables (trips depends on routes, calendar)
                    await self.progress_tracker.update(
                        phase="copy_trips",
                        message="Copying trips.txt",
                        percent=45,
                    )
                    await self._copy_trips(trips_df)

                    # Phase 3: Import stop_times (depends on trips, stops)
                    import_mode = self.settings.gtfs_stop_times_import_mode
                    logger.info(
                        "Using GTFS stop_times import_mode=%s (batch_size=%s)",
                        import_mode,
                        stop_times_batch_size,
                    )
                    await self.progress_tracker.update(
                        phase="copy_stop_times",
                        message="Copying stop_times.txt",
                        percent=50,
                        rows_processed=0,
                        rows_total=None,
                    )
                    if import_mode == "batched":
                        await self._copy_stop_times_from_zip(
                            zf, batch_size=stop_times_batch_size
                        )
                    else:
                        await self._copy_stop_times_streaming_from_zip(zf)
            else:
                stops_df = self._read_gtfs_table(feed_path, "stops.txt")
                routes_df = self._read_gtfs_table(feed_path, "routes.txt")
                trips_df = self._read_gtfs_table(feed_path, "trips.txt")
                calendar_df = self._read_gtfs_table(feed_path, "calendar.txt")
                calendar_dates_df = self._read_gtfs_table(
                    feed_path, "calendar_dates.txt"
                )
                feed_info_df = self._read_gtfs_table(feed_path, "feed_info.txt")

                await self.progress_tracker.update(
                    phase="validate",
                    message="Validating GTFS feed",
                    percent=20,
                )
                self._validate_static_feed_content(
                    feed_path,
                    stops_df=stops_df,
                    routes_df=routes_df,
                    trips_df=trips_df,
                    calendar_df=calendar_df,
                    calendar_dates_df=calendar_dates_df,
                )

                logger.info("Truncating existing GTFS data...")
                await self.progress_tracker.update(
                    phase="truncate",
                    message="Replacing existing GTFS tables",
                    percent=25,
                )
                await self._truncate_all_tables()
                final_load_started = True

                logger.info(
                    f"Persisting GTFS feed {feed_id} to database using parallel COPY..."
                )

                # Phase 1: Parallel import of independent tables
                await self.progress_tracker.update(
                    phase="copy_core",
                    message="Copying stops, routes, and calendar tables",
                    percent=35,
                )
                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._copy_stops(stops_df))
                        tg.create_task(self._copy_routes(routes_df))
                        tg.create_task(
                            self._copy_calendar(calendar_df, calendar_dates_df)
                        )
                except* Exception:  # type: ignore
                    logger.exception("Errors during parallel independent table import")
                    raise

                # Phase 2: Import dependent tables
                await self.progress_tracker.update(
                    phase="copy_trips",
                    message="Copying trips.txt",
                    percent=45,
                )
                await self._copy_trips(trips_df)

                # Phase 3: Import stop_times
                import_mode = self.settings.gtfs_stop_times_import_mode
                logger.info(
                    "Using GTFS stop_times import_mode=%s (batch_size=%s)",
                    import_mode,
                    stop_times_batch_size,
                )
                await self.progress_tracker.update(
                    phase="copy_stop_times",
                    message="Copying stop_times.txt",
                    percent=50,
                    rows_processed=0,
                    rows_total=None,
                )
                if import_mode == "batched":
                    await self._copy_stop_times_from_path(
                        feed_path, batch_size=stop_times_batch_size
                    )
                else:
                    await self._copy_stop_times_streaming_from_path(feed_path)

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

            await self.progress_tracker.update(
                phase="analyze",
                message="Analyzing GTFS tables",
                percent=93,
            )
            await self._analyze_gtfs_tables()

            try:
                await self.progress_tracker.update(
                    phase="cleanup",
                    message="Cleaning up GTFS import artifacts",
                    percent=97,
                )
                await self._cleanup_gtfs_archives(feed_path)
            except Exception:
                logger.exception("Failed to clean up GTFS archives after import")

            try:
                cache = get_cache_service()
                deleted = await cache.delete_pattern(
                    "gtfs:schedule:active_service_ids:*"
                )
                if deleted:
                    logger.info(
                        "Invalidated %d active-service cache keys after import",
                        deleted,
                    )
            except Exception:
                logger.exception(
                    "Failed to invalidate active-service cache after import"
                )

            logger.info(f"Successfully imported GTFS feed {feed_id}")
            await self.progress_tracker.succeed(message=f"Imported GTFS feed {feed_id}")
            return feed_id
        except Exception as exc:
            await self.progress_tracker.fail(exc)
            if final_load_started:
                try:
                    await self._recreate_stop_times_indexes_and_fks()
                except Exception:
                    logger.exception(
                        "Failed to restore stop_times indexes/FKs after import error"
                    )
            raise

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

        # Order matters due to foreign key constraints - truncate all static GTFS
        # tables together without cascading into realtime history.
        await self.session.execute(
            text(
                "TRUNCATE TABLE gtfs_stop_times, gtfs_calendar_dates, gtfs_calendar, gtfs_trips, gtfs_routes, gtfs_stops, gtfs_feed_info"
            )
        )
        await self.session.commit()
        logger.info("Truncated all GTFS tables (indexes and FKs dropped)")

        # Ensure logging mode matches configuration
        # Use explicit ALTER TABLE statements to avoid SQL injection concerns
        # (table names are hardcoded, logging mode is validated from settings)
        await self._set_gtfs_table_persistence_mode(
            use_unlogged=self.settings.gtfs_use_unlogged_tables
        )

    async def _get_gtfs_table_persistence(self, table_name: str) -> str | None:
        result = await self.session.execute(
            text(
                "SELECT relpersistence FROM pg_class WHERE oid = to_regclass(:table_name)"
            ),
            {"table_name": table_name},
        )
        current_mode = result.scalar_one_or_none()
        if inspect.isawaitable(current_mode):
            current_mode = await cast(Any, current_mode)
        return current_mode

    async def _set_gtfs_table_persistence_mode(self, *, use_unlogged: bool) -> None:
        desired_mode = "u" if use_unlogged else "p"
        desired_label = "UNLOGGED" if use_unlogged else "LOGGED"
        tables = [
            "gtfs_stops",
            "gtfs_routes",
            "gtfs_trips",
            "gtfs_stop_times",
            "gtfs_calendar",
            "gtfs_calendar_dates",
            "gtfs_feed_info",
        ]

        altered_tables: list[str] = []
        for table_name in tables:
            current_mode = await self._get_gtfs_table_persistence(table_name)
            if current_mode == desired_mode:
                continue

            await self.session.execute(
                text(f"ALTER TABLE {table_name} SET {desired_label}")
            )
            altered_tables.append(table_name)

        if altered_tables:
            logger.info(
                "GTFS tables set to %s mode: %s",
                desired_label,
                ", ".join(altered_tables),
            )
        else:
            logger.info("GTFS tables already in %s mode", desired_label)
        await self.session.commit()

    async def _analyze_gtfs_tables(self) -> None:
        logger.info("Running ANALYZE on GTFS tables after import...")
        for table_name in [
            "gtfs_stops",
            "gtfs_routes",
            "gtfs_trips",
            "gtfs_stop_times",
            "gtfs_calendar",
            "gtfs_calendar_dates",
            "gtfs_feed_info",
        ]:
            await self.session.execute(text(f"ANALYZE {table_name}"))
        await self.session.commit()

    async def _cleanup_gtfs_archives(self, current_feed_path: Path | None) -> None:
        retention_count = self.settings.gtfs_feed_archive_retention_count
        current_archive_path = (
            current_feed_path.resolve() if current_feed_path is not None else None
        )

        for part_file in self.storage_path.glob("*.part"):
            if not part_file.is_file():
                continue
            try:
                part_file.unlink(missing_ok=True)
            except Exception:
                logger.warning(
                    "Failed to delete stale GTFS archive part file: %s", part_file
                )

        zip_files = [path for path in self.storage_path.glob("*.zip") if path.is_file()]
        if not zip_files:
            return

        zip_files.sort(
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )

        keep_paths = {path.resolve() for path in zip_files[: max(retention_count, 0)]}
        if current_archive_path is not None:
            keep_paths.add(current_archive_path)

        for archive_path in zip_files:
            if archive_path.resolve() in keep_paths:
                continue
            try:
                archive_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("Failed to delete stale GTFS archive: %s", archive_path)

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

    def _find_gtfs_zip_member(
        self, source: zipfile.ZipFile, filename: str
    ) -> str | None:
        try:
            source.getinfo(filename)
            return filename
        except KeyError:
            return next(
                (name for name in source.namelist() if name.endswith(f"/{filename}")),
                None,
            )

    def _read_gtfs_header(
        self, source: zipfile.ZipFile | Path, filename: str
    ) -> list[str] | None:
        if isinstance(source, Path):
            path = source / filename
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                return next(csv.reader(f), None)

        member_name = self._find_gtfs_zip_member(source, filename)
        if member_name is None:
            return None
        with source.open(member_name) as f:
            wrapper = io.TextIOWrapper(f, encoding="utf-8-sig", newline="")
            try:
                return next(csv.reader(wrapper), None)
            finally:
                wrapper.detach()

    def _validate_columns(
        self,
        *,
        filename: str,
        columns: set[str],
        required: set[str],
    ) -> None:
        missing = required - columns
        if missing:
            raise GTFSFeedValidationError(
                f"{filename} is missing required columns: {', '.join(sorted(missing))}"
            )

    def _validate_required_table(
        self, *, filename: str, df: pl.DataFrame | None
    ) -> None:
        if df is None or df.is_empty():
            raise GTFSFeedValidationError(f"{filename} is required and cannot be empty")
        self._validate_columns(
            filename=filename,
            columns=set(df.columns),
            required=_REQUIRED_STATIC_COLUMNS[filename],
        )

    def _validate_static_feed_content(
        self,
        source: zipfile.ZipFile | Path,
        *,
        stops_df: pl.DataFrame | None,
        routes_df: pl.DataFrame | None,
        trips_df: pl.DataFrame | None,
        calendar_df: pl.DataFrame | None,
        calendar_dates_df: pl.DataFrame | None,
    ) -> None:
        """Validate source feed content before replacing final GTFS tables."""
        self._validate_required_table(filename="stops.txt", df=stops_df)
        self._validate_required_table(filename="routes.txt", df=routes_df)
        self._validate_required_table(filename="trips.txt", df=trips_df)
        assert routes_df is not None
        assert trips_df is not None

        service_ids: set[str] = set()
        if calendar_df is not None and not calendar_df.is_empty():
            self._validate_columns(
                filename="calendar.txt",
                columns=set(calendar_df.columns),
                required=_REQUIRED_STATIC_COLUMNS["calendar.txt"],
            )
            service_ids.update(str(value) for value in calendar_df["service_id"])

        if calendar_dates_df is not None and not calendar_dates_df.is_empty():
            self._validate_columns(
                filename="calendar_dates.txt",
                columns=set(calendar_dates_df.columns),
                required=_REQUIRED_STATIC_COLUMNS["calendar_dates.txt"],
            )
            service_ids.update(str(value) for value in calendar_dates_df["service_id"])

        if not service_ids:
            raise GTFSFeedValidationError(
                "calendar.txt or calendar_dates.txt is required and cannot be empty"
            )

        route_ids_series = routes_df["route_id"].cast(pl.Utf8).unique()
        unknown_route_ids = (
            trips_df.filter(~pl.col("route_id").cast(pl.Utf8).is_in(route_ids_series))
            .select(pl.col("route_id").cast(pl.Utf8).unique().sort())
            .to_series()
            .to_list()
        )
        if unknown_route_ids:
            preview = ", ".join(unknown_route_ids[:5])
            raise GTFSFeedValidationError(
                f"trips.txt references missing route_id values: {preview}"
            )

        service_ids_series = pl.Series("service_id", sorted(service_ids), dtype=pl.Utf8)
        unknown_service_ids = (
            trips_df.filter(
                ~pl.col("service_id").cast(pl.Utf8).is_in(service_ids_series)
            )
            .select(pl.col("service_id").cast(pl.Utf8).unique().sort())
            .to_series()
            .to_list()
        )
        if unknown_service_ids:
            preview = ", ".join(unknown_service_ids[:5])
            raise GTFSFeedValidationError(
                f"trips.txt references missing service_id values: {preview}"
            )

        stop_times_header = self._read_gtfs_header(source, "stop_times.txt")
        if stop_times_header is None:
            raise GTFSFeedValidationError(
                "stop_times.txt is required and cannot be empty"
            )
        self._validate_columns(
            filename="stop_times.txt",
            columns=set(stop_times_header),
            required=_REQUIRED_STATIC_COLUMNS["stop_times.txt"],
        )

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

    async def _copy_stops(self, stops_df: pl.DataFrame | None):
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
        ).select(
            [
                "stop_id",
                "stop_name",
                "stop_lat",
                "stop_lon",
                "location_type",
                "parent_station",
                "platform_code",
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
            ],
        )

        logger.info(f"Copied {stops_df.height} stops")

    async def _copy_routes(self, routes_df: pl.DataFrame | None):
        """Bulk insert routes using PostgreSQL COPY."""
        if routes_df is None or routes_df.is_empty():
            return

        logger.info(f"Preparing {routes_df.height} routes for COPY...")

        df = routes_df
        for col in ["agency_id", "route_short_name", "route_long_name", "route_color"]:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Utf8).alias(col))

        export_df = df.select(
            [
                "route_id",
                "agency_id",
                "route_short_name",
                "route_long_name",
                "route_type",
                "route_color",
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
            ],
        )

        logger.info(f"Copied {routes_df.height} routes")

    async def _copy_trips(self, trips_df: pl.DataFrame | None):
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

        export_df = df.select(
            [
                "trip_id",
                "route_id",
                "service_id",
                "trip_headsign",
                "direction_id",
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
            ],
        )

        logger.info(f"Copied {trips_df.height} trips")

    async def _copy_stop_times_batch(self, stop_times_df: pl.DataFrame):
        if stop_times_df.is_empty():
            return

        df = stop_times_df
        for col in ["pickup_type", "drop_off_type"]:
            if col not in df.columns:
                df = df.with_columns(pl.lit(0).alias(col))

        export_df = df.with_columns(
            _gtfs_time_to_seconds_expr("arrival_time").alias("arrival_seconds"),
            _gtfs_time_to_seconds_expr("departure_time").alias("departure_seconds"),
            pl.col("stop_sequence").cast(pl.Int32),
            pl.col("pickup_type").fill_null(0).cast(pl.Int8),
            pl.col("drop_off_type").fill_null(0).cast(pl.Int8),
        ).select(
            [
                "trip_id",
                "stop_id",
                "arrival_seconds",
                "departure_seconds",
                "stop_sequence",
                "pickup_type",
                "drop_off_type",
            ]
        )

        await self._copy_polars_df(
            export_df,
            "gtfs_stop_times",
            columns=[
                "trip_id",
                "stop_id",
                "arrival_seconds",
                "departure_seconds",
                "stop_sequence",
                "pickup_type",
                "drop_off_type",
            ],
        )

    def _stream_stop_times_to_temp_csv(
        self, source_path: str | Path, output_path: str
    ) -> None:
        """Transform stop_times.txt using lazy streaming and write to a headerless CSV."""
        lf = pl.scan_csv(source_path, null_values=[""], infer_schema_length=1000)
        available_cols = set(lf.collect_schema().names())

        pickup_expr = (
            pl.col("pickup_type").fill_null(0).cast(pl.Int8)
            if "pickup_type" in available_cols
            else pl.lit(0).cast(pl.Int8)
        )
        drop_off_expr = (
            pl.col("drop_off_type").fill_null(0).cast(pl.Int8)
            if "drop_off_type" in available_cols
            else pl.lit(0).cast(pl.Int8)
        )

        lf.select(
            pl.col("trip_id"),
            pl.col("stop_id"),
            _gtfs_time_to_seconds_expr("arrival_time").alias("arrival_seconds"),
            _gtfs_time_to_seconds_expr("departure_time").alias("departure_seconds"),
            pl.col("stop_sequence").cast(pl.Int32),
            pickup_expr.alias("pickup_type"),
            drop_off_expr.alias("drop_off_type"),
        ).sink_csv(
            output_path,
            include_header=False,
            separator=",",
            null_value="",
        )

    _STOP_TIMES_COPY_COLUMNS = [
        "trip_id",
        "stop_id",
        "arrival_seconds",
        "departure_seconds",
        "stop_sequence",
        "pickup_type",
        "drop_off_type",
    ]

    async def _streaming_copy_to_db(self, csv_path: str) -> None:
        """COPY a transformed CSV into gtfs_stop_times via asyncpg."""
        conn_ctx = self._get_asyncpg_conn()
        async with conn_ctx as asyncpg_conn:
            with open(csv_path, "rb") as f:
                await asyncpg_conn.copy_to_table(
                    "gtfs_stop_times",
                    source=f,
                    columns=self._STOP_TIMES_COPY_COLUMNS,
                    format="csv",
                )

    @staticmethod
    def _cleanup_temp_files(*paths: str | None) -> None:
        for p in paths:
            if p is not None:
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    logger.warning("Failed to delete temp file: %s", p)

    async def _finalize_streaming_stop_times(self) -> None:
        """Rebuild PK and indexes after a successful streaming COPY.

        Intentionally not called on COPY failure: the import aborts and the
        next import cycle re-truncates + rebuilds from scratch.
        """
        await self.progress_tracker.update(
            phase="rebuild_indexes",
            message="Rebuilding stop_times indexes",
            percent=88,
        )
        await self._recreate_stop_times_indexes_and_fks()

    async def _drop_stop_times_pkey(self) -> None:
        """Drop PK on stop_times for faster COPY (recreated by _finalize_streaming_stop_times)."""
        await self.session.execute(
            text(
                "ALTER TABLE gtfs_stop_times DROP CONSTRAINT IF EXISTS gtfs_stop_times_pkey"
            )
        )

    async def _copy_stop_times_streaming_from_path(self, feed_path: Path) -> None:
        stop_times_path = feed_path / "stop_times.txt"
        if not stop_times_path.exists():
            logger.info("No stop_times.txt found at %s", stop_times_path)
            await self._finalize_streaming_stop_times()
            return

        await self._drop_stop_times_pkey()

        await self.progress_tracker.update(
            phase="copy_stop_times",
            message="Copying stop_times.txt (streaming)",
            percent=50.0,
            rows_processed=None,
            rows_total=None,
        )

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                tmp_path = tmp.name

            await asyncio.to_thread(
                self._stream_stop_times_to_temp_csv,
                str(stop_times_path),
                tmp_path,
            )

            await self._streaming_copy_to_db(tmp_path)

            await self.progress_tracker.update(
                phase="copy_stop_times",
                message="Copying stop_times.txt (streaming)",
                percent=85.0,
                rows_processed=None,
                rows_total=None,
            )
        finally:
            self._cleanup_temp_files(tmp_path)

        await self._finalize_streaming_stop_times()

    async def _copy_stop_times_streaming_from_zip(self, zf: zipfile.ZipFile) -> None:
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
                await self._finalize_streaming_stop_times()
                return
            member_name = alt_member

        await self._drop_stop_times_pkey()

        extracted_path: str | None = None
        transformed_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                extracted_path = tmp.name
                with zf.open(member_name) as f:
                    while True:
                        chunk = f.read(8 * 1024 * 1024)
                        if not chunk:
                            break
                        tmp.write(chunk)

            logger.info(
                "Extracted stop_times.txt to temp file for streaming processing"
            )
            await self.progress_tracker.update(
                phase="copy_stop_times",
                message="Copying stop_times.txt (streaming)",
                percent=50.0,
                rows_processed=None,
                rows_total=None,
            )

            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".csv", delete=False
            ) as tmp:
                transformed_path = tmp.name

            await asyncio.to_thread(
                self._stream_stop_times_to_temp_csv,
                extracted_path,
                transformed_path,
            )

            await self._streaming_copy_to_db(transformed_path)

            await self.progress_tracker.update(
                phase="copy_stop_times",
                message="Copying stop_times.txt (streaming)",
                percent=85.0,
                rows_processed=None,
                rows_total=None,
            )
        finally:
            self._cleanup_temp_files(extracted_path, transformed_path)

        await self._finalize_streaming_stop_times()

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

    def _count_csv_data_rows(self, path: str | Path) -> int:
        line_count = 0
        with open(path, "rb") as f:
            for _line in f:
                line_count += 1
        return max(line_count - 1, 0)

    def _stop_times_percent(self, rows_processed: int, rows_total: int | None) -> float:
        if not rows_total:
            return 50.0
        return 50.0 + (min(rows_processed, rows_total) / rows_total) * 35.0

    async def _wait_for_stop_times_batch_tasks(
        self,
        batch_tasks: set[asyncio.Task[None]],
        *,
        return_when: str,
    ) -> set[asyncio.Task[None]]:
        done, pending = await asyncio.wait(batch_tasks, return_when=return_when)
        try:
            for task in done:
                task.result()
        except BaseException:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            raise
        return set(pending)

    async def _copy_stop_times_from_zip(
        self, zf: zipfile.ZipFile, *, batch_size: int = 500_000
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
                await self.progress_tracker.update(
                    phase="rebuild_indexes",
                    message="Rebuilding stop_times indexes",
                    percent=88,
                    rows_processed=0,
                    rows_total=0,
                )
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
            rows_total = self._count_csv_data_rows(tmp_path)
            await self.progress_tracker.update(
                phase="copy_stop_times",
                message="Copying stop_times.txt",
                percent=self._stop_times_percent(0, rows_total),
                rows_processed=0,
                rows_total=rows_total,
            )

            # Process batches in parallel with a semaphore to limit concurrency
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent COPY operations
            rows_copied = 0
            rows_lock = asyncio.Lock()

            async def process_batch(batch_df: pl.DataFrame, batch_num: int) -> None:
                nonlocal rows_copied
                async with semaphore:
                    await self._copy_stop_times_batch(batch_df)
                    async with rows_lock:
                        rows_copied += batch_df.height
                        await self.progress_tracker.update(
                            phase="copy_stop_times",
                            message="Copying stop_times.txt",
                            percent=self._stop_times_percent(rows_copied, rows_total),
                            rows_processed=rows_copied,
                            rows_total=rows_total,
                        )
                    if batch_num % 10 == 0:
                        logger.info("Copied %s stop_times batches...", batch_num)

            # Read all batches first (memory efficient, as we get lazy iterators)
            reader = self._read_csv_batched(tmp_path, batch_size=batch_size)

            # Collect batches and process them in parallel
            # Using a queue approach to avoid loading all batches into memory at once
            batch_tasks: set[asyncio.Task[None]] = set()
            batch_count = 0
            while True:
                batches = reader.next_batches(1)
                if not batches:
                    break
                batch_count += 1
                batch_tasks.add(
                    asyncio.create_task(process_batch(batches[0], batch_count))
                )

                # Wait for some tasks to complete if we have many pending
                # This prevents memory buildup while maintaining parallelism
                if len(batch_tasks) >= 6:  # 2x the semaphore size
                    # Wait for at least half to complete before adding more
                    batch_tasks = await self._wait_for_stop_times_batch_tasks(
                        batch_tasks, return_when=asyncio.FIRST_COMPLETED
                    )

            # Wait for remaining tasks
            if batch_tasks:
                await self._wait_for_stop_times_batch_tasks(
                    batch_tasks, return_when=asyncio.ALL_COMPLETED
                )

        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except Exception:
                    logger.warning("Failed to delete temp file: %s", tmp_path)

        await self.progress_tracker.update(
            phase="rebuild_indexes",
            message="Rebuilding stop_times indexes",
            percent=88,
        )
        await self._recreate_stop_times_indexes_and_fks()

    async def _copy_stop_times_from_path(
        self, feed_path: Path, *, batch_size: int = 500_000
    ):
        stop_times_path = feed_path / "stop_times.txt"
        if not stop_times_path.exists():
            logger.info("No stop_times.txt found at %s", stop_times_path)
            await self.progress_tracker.update(
                phase="rebuild_indexes",
                message="Rebuilding stop_times indexes",
                percent=88,
                rows_processed=0,
                rows_total=0,
            )
            await self._recreate_stop_times_indexes_and_fks()
            return

        rows_total = self._count_csv_data_rows(stop_times_path)
        await self.progress_tracker.update(
            phase="copy_stop_times",
            message="Copying stop_times.txt",
            percent=self._stop_times_percent(0, rows_total),
            rows_processed=0,
            rows_total=rows_total,
        )

        # Process batches in parallel with a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent COPY operations
        rows_copied = 0
        rows_lock = asyncio.Lock()

        async def process_batch(batch_df: pl.DataFrame, batch_num: int) -> None:
            nonlocal rows_copied
            async with semaphore:
                await self._copy_stop_times_batch(batch_df)
                async with rows_lock:
                    rows_copied += batch_df.height
                    await self.progress_tracker.update(
                        phase="copy_stop_times",
                        message="Copying stop_times.txt",
                        percent=self._stop_times_percent(rows_copied, rows_total),
                        rows_processed=rows_copied,
                        rows_total=rows_total,
                    )
                if batch_num % 10 == 0:
                    logger.info("Copied %s stop_times batches...", batch_num)

        reader = self._read_csv_batched(str(stop_times_path), batch_size=batch_size)

        # Collect batches and process them in parallel
        batch_tasks: set[asyncio.Task[None]] = set()
        batch_count = 0
        while True:
            batches = reader.next_batches(1)
            if not batches:
                break
            batch_count += 1
            batch_tasks.add(asyncio.create_task(process_batch(batches[0], batch_count)))

            # Wait for some tasks to complete if we have many pending
            if len(batch_tasks) >= 6:  # 2x the semaphore size
                batch_tasks = await self._wait_for_stop_times_batch_tasks(
                    batch_tasks, return_when=asyncio.FIRST_COMPLETED
                )

        # Wait for remaining tasks
        if batch_tasks:
            await self._wait_for_stop_times_batch_tasks(
                batch_tasks, return_when=asyncio.ALL_COMPLETED
            )

        await self.progress_tracker.update(
            phase="rebuild_indexes",
            message="Rebuilding stop_times indexes",
            percent=88,
        )
        await self._recreate_stop_times_indexes_and_fks()

    async def _recreate_stop_times_indexes_and_fks(self) -> None:
        logger.info("Recreating indexes and foreign keys on stop_times...")

        # Primary key covers trip lookups; redundant trip index is not recreated
        await self.session.execute(
            text(
                """
                DO $$
                BEGIN
                    ALTER TABLE gtfs_stop_times ADD CONSTRAINT gtfs_stop_times_pkey
                        PRIMARY KEY (trip_id, stop_sequence);
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END $$;
                """
            )
        )

        await self.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_stop ON gtfs_stop_times(stop_id)"
            )
        )
        # Note: idx_gtfs_stop_times_trip is intentionally NOT recreated because
        # the (trip_id, stop_sequence) primary key already covers trip_id lookups.
        await self.session.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_departure_lookup ON gtfs_stop_times(stop_id, departure_seconds)"
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
            ).select(["service_id", "date", "exception_type"])

            await self._copy_polars_df(
                export_df,
                "gtfs_calendar_dates",
                columns=["service_id", "date", "exception_type"],
            )

            logger.info(f"Copied {calendar_dates_df.height} calendar date records")

    async def _download_feed(self, feed_url: str) -> Path:
        """Download GTFS feed ZIP file."""
        filename = f"gtfs_feed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        feed_path = self.storage_path / filename
        tmp_path = feed_path.with_suffix(f"{feed_path.suffix}.part")

        logger.info(f"Downloading GTFS feed from {feed_url}")

        bytes_downloaded = 0
        async with httpx.AsyncClient(
            timeout=self.settings.gtfs_download_timeout_seconds
        ) as client:
            try:
                async with client.stream("GET", feed_url) as response:
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length:
                        logger.info(
                            "GTFS feed response size: %.1f MB",
                            int(content_length) / 1024 / 1024,
                        )

                    with open(tmp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
            except httpx.TimeoutException:
                logger.exception(
                    "Timed out downloading GTFS feed from %s after %.1f MB",
                    feed_url,
                    bytes_downloaded / 1024 / 1024,
                )
                tmp_path.unlink(missing_ok=True)
                raise
            except Exception:
                logger.exception(
                    "Failed downloading GTFS feed from %s after %.1f MB",
                    feed_url,
                    bytes_downloaded / 1024 / 1024,
                )
                tmp_path.unlink(missing_ok=True)
                raise

        tmp_path.replace(feed_path)

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
            "downloaded_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "feed_start_date": feed_start_date,
            "feed_end_date": feed_end_date,
            "stop_count": stop_count,
            "route_count": route_count,
            "trip_count": trip_count,
        }

        await self.session.execute(insert(GTFSFeedInfo).values(feed_info))
        await self.session.commit()
        logger.info(f"Recorded feed info for {feed_id}")

    def _parse_gtfs_time_to_seconds(self, time_str: Optional[str]) -> Optional[int]:
        """Convert a GTFS time string (HH:MM:SS) to seconds since service midnight."""
        return _parse_gtfs_time_to_seconds(time_str)
