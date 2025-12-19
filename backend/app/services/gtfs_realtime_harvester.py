"""
GTFS-RT Data Harvester Service (Streaming Aggregation)

Background service for collecting GTFS-RT trip updates and aggregating them
in place using streaming upserts for efficient storage.
"""

from __future__ import annotations

import asyncio
import io
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.persistence.models import RealtimeStationStats, ScheduleRelationship

if TYPE_CHECKING:
    from app.services.cache import CacheService

# Import GTFS-RT bindings with fallback
try:
    from google.transit import gtfs_realtime_pb2

    FeedMessage = gtfs_realtime_pb2.FeedMessage
    GTFS_RT_AVAILABLE = True
except ImportError:
    try:
        import gtfs_realtime_bindings

        FeedMessage = gtfs_realtime_bindings.FeedMessage
        GTFS_RT_AVAILABLE = True
    except ImportError:
        FeedMessage = None
        GTFS_RT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Delay thresholds (in seconds)
DELAY_THRESHOLD_SECONDS = 300  # 5 minutes = delayed
ON_TIME_THRESHOLD_SECONDS = 60  # 1 minute = on time
STATUS_UNKNOWN = "unknown"
STATUS_ON_TIME = "on_time"
STATUS_DELAYED = "delayed"
STATUS_CANCELLED = "cancelled"
STATUS_RANK = {
    STATUS_UNKNOWN: 0,
    STATUS_ON_TIME: 1,
    STATUS_DELAYED: 2,
    STATUS_CANCELLED: 3,
}


def _escape_tsv(val) -> str:
    """Escape value for TSV format. Returns \\N for NULL."""
    if val is None:
        return "\\N"
    s = str(val)
    s = (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return s


class GTFSRTDataHarvester:
    """Background service for collecting and aggregating GTFS-RT data.

    Uses streaming aggregation to update statistics in place, avoiding
    the storage overhead of storing raw observations.
    """

    def __init__(
        self,
        cache_service: CacheService | None = None,
        harvest_interval_seconds: int | None = None,
    ) -> None:
        """Initialize the harvester.

        Args:
            cache_service: Cache service for trip deduplication
            harvest_interval_seconds: Override default harvest interval
        """
        self.settings = get_settings()
        self._cache = cache_service
        self._harvest_interval = harvest_interval_seconds or getattr(
            self.settings, "gtfs_rt_harvest_interval_seconds", 300
        )
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the harvesting background loop."""
        if self._running:
            logger.warning("Harvester already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_polling_loop())
        logger.info(
            "GTFS-RT harvester started with interval %ds", self._harvest_interval
        )

    async def stop(self) -> None:
        """Stop the harvesting background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("GTFS-RT harvester stopped")

    async def _run_polling_loop(self) -> None:
        """Main polling loop that runs until stopped."""
        while self._running:
            try:
                await self.harvest_once()
            except Exception as e:
                logger.error("Harvester iteration failed: %s", e)

            await asyncio.sleep(self._harvest_interval)  # type: ignore[arg-type]

    async def harvest_once(self) -> int:
        """Perform a single harvest iteration with streaming aggregation.

        Returns:
            Number of stations updated.
        """
        if not GTFS_RT_AVAILABLE:
            logger.warning("GTFS-RT bindings not available, skipping harvest")
            return 0

        try:
            logger.info("Starting GTFS-RT harvest cycle")

            # Fetch trip updates from feed
            trip_updates = await self._fetch_trip_updates()

            if not trip_updates:
                logger.debug("No trip updates received")
                return 0

            logger.info(f"Received {len(trip_updates)} trip updates from GTFS-RT feed")

            # Calculate current time bucket (hourly)
            now = datetime.now(timezone.utc)
            bucket_start = now.replace(minute=0, second=0, microsecond=0)
            logger.debug(
                f"Processing data for bucket starting at {bucket_start.isoformat()}"
            )

            # Group updates by stop_id and aggregate
            stop_stats = await self._aggregate_by_stop(trip_updates, bucket_start)

            if not stop_stats:
                logger.debug("No stop statistics generated from trip updates")
                return 0

            # Upsert aggregations to database
            async with AsyncSessionFactory() as session:
                await self._upsert_stats(session, bucket_start, stop_stats)
                await session.commit()

            logger.info(
                "Harvested and aggregated stats for %d stations", len(stop_stats)
            )
            return len(stop_stats)

        except Exception as e:
            logger.error("Failed to harvest GTFS-RT data: %s", e)
            return 0

    async def _fetch_trip_updates(self) -> list[dict]:
        """Fetch and parse trip updates from GTFS-RT feed.

        Returns:
            List of parsed trip update dictionaries.
        """
        if not FeedMessage:
            logger.warning("GTFS-RT FeedMessage not available")
            return []

        try:
            logger.debug(f"Fetching GTFS-RT data from {self.settings.gtfs_rt_feed_url}")
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={"User-Agent": "BahnVision-GTFS-RT-Harvester/1.0"},
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)

            logger.debug(f"Received response with status {response.status_code}")
            response.raise_for_status()

            feed = FeedMessage()
            feed.ParseFromString(response.content)

            # Extract feed timestamp
            feed_timestamp = datetime.fromtimestamp(feed.header.timestamp, timezone.utc)

            trip_updates = []
            for entity in feed.entity:
                if not entity.HasField("trip_update"):
                    continue

                tu = entity.trip_update
                if not tu.trip.trip_id:
                    continue

                for stop_time_update in tu.stop_time_update:
                    if not stop_time_update.stop_id:
                        continue

                    # Map schedule relationship
                    schedule_rel = self._map_schedule_relationship(
                        stop_time_update.schedule_relationship
                    )

                    trip_updates.append(
                        {
                            "trip_id": tu.trip.trip_id,
                            "route_id": tu.trip.route_id or "",
                            "stop_id": stop_time_update.stop_id,
                            "stop_sequence": stop_time_update.stop_sequence,
                            "departure_delay_seconds": (
                                stop_time_update.departure.delay
                                if stop_time_update.HasField("departure")
                                else None
                            ),
                            "schedule_relationship": schedule_rel,
                            "feed_timestamp": feed_timestamp,
                        }
                    )

            return trip_updates

        except Exception as e:
            logger.error("Failed to fetch trip updates: %s", e)
            return []

    def _map_schedule_relationship(self, relationship: int) -> ScheduleRelationship:
        """Map GTFS-RT schedule relationship code to enum."""
        mapping = {
            0: ScheduleRelationship.SCHEDULED,
            1: ScheduleRelationship.SKIPPED,
            2: ScheduleRelationship.NO_DATA,
            3: ScheduleRelationship.UNSCHEDULED,
        }
        return mapping.get(relationship, ScheduleRelationship.SCHEDULED)

    async def _aggregate_by_stop(
        self,
        trip_updates: list[dict],
        bucket_start: datetime,
    ) -> dict[str, dict]:
        """Aggregate trip updates by stop_id with deduplication.

        Counts delays/cancellations per UNIQUE TRIP, not per stop_time_update.
        Each trip is classified once per bucket, with cache-backed upgrades to
        worse statuses across harvest cycles.

        Args:
            trip_updates: List of parsed trip updates
            bucket_start: Start of the current time bucket

        Returns:
            Dict mapping stop_id -> aggregated statistics
        """
        # First pass: determine the status of each unique trip at each stop
        # Key: (stop_id, trip_id) -> {"delay": max_delay, "cancelled": bool}
        trip_status_by_stop: dict[tuple[str, str], dict] = {}

        for update in trip_updates:
            stop_id = update["stop_id"]
            trip_id = update["trip_id"]
            key = (stop_id, trip_id)

            delay = update.get("departure_delay_seconds") or 0
            is_cancelled = (
                update["schedule_relationship"] == ScheduleRelationship.CANCELED
            )

            if key not in trip_status_by_stop:
                trip_status_by_stop[key] = {
                    "delay": delay,
                    "cancelled": is_cancelled,
                }
            else:
                # Keep the worst status for this trip at this stop
                existing = trip_status_by_stop[key]
                existing["delay"] = max(existing["delay"], delay)
                existing["cancelled"] = existing["cancelled"] or is_cancelled

        # Second pass: aggregate by stop_id using per-trip status with deduplication.
        stop_stats: dict[str, dict] = defaultdict(
            lambda: {
                "trip_statuses": {},
            }
        )

        for (stop_id, trip_id), status in trip_status_by_stop.items():
            stop_stats[stop_id]["trip_statuses"][trip_id] = {
                "delay": status["delay"],
                "status": self._classify_status(status["delay"], status["cancelled"]),
            }

        for stop_id, stats in stop_stats.items():
            deltas = await self._apply_trip_statuses(
                bucket_start, stop_id, stats["trip_statuses"]
            )
            stats.update(deltas)
            stats.pop("trip_statuses", None)

        return dict(stop_stats)

    def _classify_status(self, delay: int, cancelled: bool) -> str:
        """Classify a trip status based on delay and cancellation."""
        if cancelled:
            return STATUS_CANCELLED
        if delay > DELAY_THRESHOLD_SECONDS:
            return STATUS_DELAYED
        if abs(delay) < ON_TIME_THRESHOLD_SECONDS:
            return STATUS_ON_TIME
        return STATUS_UNKNOWN

    def _normalize_cached_status(self, value: str | None) -> str | None:
        if value is None:
            return None
        if value in STATUS_RANK:
            return value
        return STATUS_UNKNOWN

    async def _apply_trip_statuses(
        self,
        bucket_start: datetime,
        stop_id: str,
        trip_statuses: dict[str, dict],
    ) -> dict[str, int]:
        """Apply per-trip status deltas with cache-backed deduplication.

        Ensures each trip contributes at most once per bucket while allowing
        upgrades to worse statuses (on_time -> delayed -> cancelled).
        """
        trip_count = 0
        total_delay_seconds = 0
        delayed = 0
        on_time = 0
        cancelled = 0

        if not trip_statuses:
            return {
                "trip_count": trip_count,
                "total_delay_seconds": total_delay_seconds,
                "delayed": delayed,
                "on_time": on_time,
                "cancelled": cancelled,
            }

        bucket_key = bucket_start.strftime("%Y%m%d%H")
        cache_keys = {
            trip_id: f"gtfs_rt_trip:{bucket_key}:{stop_id}:{self._hash_trip_id(trip_id)}"
            for trip_id in trip_statuses
        }

        if not self._cache:
            for status in trip_statuses.values():
                trip_count += 1
                total_delay_seconds += status["delay"]
                if status["status"] == STATUS_DELAYED:
                    delayed += 1
                elif status["status"] == STATUS_ON_TIME:
                    on_time += 1
                elif status["status"] == STATUS_CANCELLED:
                    cancelled += 1
            return {
                "trip_count": trip_count,
                "total_delay_seconds": total_delay_seconds,
                "delayed": delayed,
                "on_time": on_time,
                "cancelled": cancelled,
            }

        try:
            existing = await self._cache.mget(list(cache_keys.values()))
            updates: dict[str, str] = {}

            for trip_id, info in trip_statuses.items():
                cache_key = cache_keys[trip_id]
                prev_status = self._normalize_cached_status(existing.get(cache_key))
                new_status = info["status"] or STATUS_UNKNOWN

                if prev_status is None:
                    trip_count += 1
                    total_delay_seconds += info["delay"]
                    if new_status == STATUS_DELAYED:
                        delayed += 1
                    elif new_status == STATUS_ON_TIME:
                        on_time += 1
                    elif new_status == STATUS_CANCELLED:
                        cancelled += 1
                    updates[cache_key] = new_status
                    continue

                prev_rank = STATUS_RANK.get(prev_status, 0)
                new_rank = STATUS_RANK.get(new_status, 0)
                if new_rank > prev_rank:
                    if prev_status == STATUS_DELAYED:
                        delayed -= 1
                    elif prev_status == STATUS_ON_TIME:
                        on_time -= 1
                    elif prev_status == STATUS_CANCELLED:
                        cancelled -= 1

                    if new_status == STATUS_DELAYED:
                        delayed += 1
                    elif new_status == STATUS_ON_TIME:
                        on_time += 1
                    elif new_status == STATUS_CANCELLED:
                        cancelled += 1
                    updates[cache_key] = new_status

            if updates:
                await self._cache.mset(updates, ttl_seconds=7200)  # 2 hours

        except Exception as exc:
            logger.debug("Batch cache operation failed: %s", exc)
            for status in trip_statuses.values():
                trip_count += 1
                total_delay_seconds += status["delay"]
                if status["status"] == STATUS_DELAYED:
                    delayed += 1
                elif status["status"] == STATUS_ON_TIME:
                    on_time += 1
                elif status["status"] == STATUS_CANCELLED:
                    cancelled += 1

        return {
            "trip_count": trip_count,
            "total_delay_seconds": total_delay_seconds,
            "delayed": delayed,
            "on_time": on_time,
            "cancelled": cancelled,
        }

    def _hash_trip_id(self, trip_id: str) -> str:
        """Create a short hash of trip_id to reduce cache key size."""
        return hashlib.md5(trip_id.encode(), usedforsecurity=False).hexdigest()[:12]

    async def _get_asyncpg_conn(self, session: AsyncSession):
        """Get raw asyncpg connection for COPY operations."""
        raw_conn = await session.connection()
        dbapi_conn = await raw_conn.get_raw_connection()
        return dbapi_conn.driver_connection

    async def _upsert_stats(
        self,
        session: AsyncSession,
        bucket_start: datetime,
        stop_stats: dict[str, dict],
    ) -> None:
        """Upsert aggregated stats using COPY to temp table + single INSERT.

        Uses PostgreSQL COPY protocol for ~5-20x faster bulk upserts:
        1. Create temp table (unlogged, auto-dropped on commit)
        2. COPY data into temp table via binary protocol
        3. Single INSERT...ON CONFLICT from temp to main table

        Args:
            session: Database session
            bucket_start: Time bucket start
            stop_stats: Aggregated stats by stop_id
        """
        if not stop_stats:
            return

        # 1. Create temp table (ON COMMIT DROP for automatic cleanup)
        await session.execute(
            text(
                """
                CREATE TEMP TABLE IF NOT EXISTS temp_rt_stats (
                    stop_id VARCHAR(64) NOT NULL,
                    bucket_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    bucket_width_minutes INTEGER NOT NULL,
                    observation_count INTEGER NOT NULL,
                    trip_count INTEGER NOT NULL,
                    total_delay_seconds BIGINT NOT NULL,
                    delayed_count INTEGER NOT NULL,
                    on_time_count INTEGER NOT NULL,
                    cancelled_count INTEGER NOT NULL
                ) ON COMMIT DROP
                """
            )
        )

        # 2. Build TSV data for COPY
        bucket_str = bucket_start.isoformat()
        lines = []
        for stop_id, stats in stop_stats.items():
            line = "\t".join(
                [
                    _escape_tsv(stop_id),
                    _escape_tsv(bucket_str),
                    _escape_tsv(60),  # bucket_width_minutes
                    _escape_tsv(1),  # observation_count
                    _escape_tsv(stats["trip_count"]),
                    _escape_tsv(stats["total_delay_seconds"]),
                    _escape_tsv(stats["delayed"]),
                    _escape_tsv(stats["on_time"]),
                    _escape_tsv(stats["cancelled"]),
                ]
            )
            lines.append(line)

        tsv_data = "\n".join(lines)

        # 3. COPY data into temp table (binary protocol, super fast)
        asyncpg_conn = await self._get_asyncpg_conn(session)
        await asyncpg_conn.copy_to_table(
            "temp_rt_stats",
            source=io.BytesIO(tsv_data.encode("utf-8")),
            columns=[
                "stop_id",
                "bucket_start",
                "bucket_width_minutes",
                "observation_count",
                "trip_count",
                "total_delay_seconds",
                "delayed_count",
                "on_time_count",
                "cancelled_count",
            ],
            format="text",
        )

        # 4. Single INSERT...ON CONFLICT from temp to main table
        await session.execute(
            text(
                """
                INSERT INTO realtime_station_stats (
                    stop_id, bucket_start, bucket_width_minutes,
                    observation_count, trip_count, total_delay_seconds,
                    delayed_count, on_time_count, cancelled_count
                )
                SELECT
                    stop_id, bucket_start, bucket_width_minutes,
                    observation_count, trip_count, total_delay_seconds,
                    delayed_count, on_time_count, cancelled_count
                FROM temp_rt_stats
                ON CONFLICT ON CONSTRAINT uq_realtime_stats_unique
                DO UPDATE SET
                    observation_count = realtime_station_stats.observation_count + 1,
                    trip_count = realtime_station_stats.trip_count + EXCLUDED.trip_count,
                    total_delay_seconds = realtime_station_stats.total_delay_seconds + EXCLUDED.total_delay_seconds,
                    delayed_count = realtime_station_stats.delayed_count + EXCLUDED.delayed_count,
                    on_time_count = realtime_station_stats.on_time_count + EXCLUDED.on_time_count,
                    cancelled_count = realtime_station_stats.cancelled_count + EXCLUDED.cancelled_count,
                    last_updated_at = NOW()
                """
            )
        )

        logger.debug("Upserted %d station stats via COPY", len(stop_stats))

    async def cleanup_old_stats(
        self,
        retention_days: int | None = None,
    ) -> int:
        """Remove stats older than retention period.

        Args:
            retention_days: Days to retain (defaults to config setting)

        Returns:
            Number of rows deleted.
        """
        days_value = retention_days or getattr(
            self.settings, "gtfs_rt_stats_retention_days", 90
        )
        days: int = int(days_value) if days_value is not None else 90
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with AsyncSessionFactory() as session:
            stmt = delete(RealtimeStationStats).where(
                RealtimeStationStats.bucket_start < cutoff
            )
            result = await session.execute(stmt)
            await session.commit()

            count: int = getattr(result, "rowcount", 0) or 0
            if count > 0:
                logger.info("Cleaned up %d stat rows older than %d days", count, days)
            return count


def get_gtfs_rt_harvester(
    cache_service: CacheService | None = None,
) -> GTFSRTDataHarvester:
    """Factory function for GTFSRTDataHarvester.

    Args:
        cache_service: Optional cache service for trip deduplication

    Returns:
        Configured harvester instance
    """
    return GTFSRTDataHarvester(cache_service=cache_service)
