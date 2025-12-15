"""
GTFS-RT Data Harvester Service (Streaming Aggregation)

Background service for collecting GTFS-RT trip updates and aggregating them
in place using streaming upserts for efficient storage.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
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
            # Fetch trip updates from feed
            trip_updates = await self._fetch_trip_updates()

            if not trip_updates:
                logger.debug("No trip updates received")
                return 0

            # Calculate current time bucket (hourly)
            now = datetime.now(timezone.utc)
            bucket_start = now.replace(minute=0, second=0, microsecond=0)

            # Group updates by stop_id and aggregate
            stop_stats = await self._aggregate_by_stop(trip_updates, bucket_start)

            if not stop_stats:
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
            return []

        try:
            async with httpx.AsyncClient(
                timeout=self.settings.gtfs_rt_timeout_seconds,
                headers={"User-Agent": "BahnVision-GTFS-RT-Harvester/1.0"},
            ) as client:
                response = await client.get(self.settings.gtfs_rt_feed_url)
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

        Args:
            trip_updates: List of parsed trip updates
            bucket_start: Start of the current time bucket

        Returns:
            Dict mapping stop_id -> aggregated statistics
        """
        stop_stats: dict[str, dict] = defaultdict(
            lambda: {
                "trips": set(),
                "delays": [],
                "delayed": 0,
                "on_time": 0,
                "cancelled": 0,
            }
        )

        for update in trip_updates:
            stop_id = update["stop_id"]
            trip_id = update["trip_id"]

            # Track unique trips
            stop_stats[stop_id]["trips"].add(trip_id)

            # Get delay value
            delay = update.get("departure_delay_seconds") or 0
            stop_stats[stop_id]["delays"].append(delay)

            # Classify the observation
            if update["schedule_relationship"] == ScheduleRelationship.CANCELED:
                stop_stats[stop_id]["cancelled"] += 1
            elif delay > DELAY_THRESHOLD_SECONDS:
                stop_stats[stop_id]["delayed"] += 1
            elif abs(delay) < ON_TIME_THRESHOLD_SECONDS:
                stop_stats[stop_id]["on_time"] += 1

        # Count new trips using cache deduplication
        for stop_id, stats in stop_stats.items():
            new_trip_count = await self._count_new_trips(
                bucket_start, stop_id, stats["trips"]
            )
            stats["new_trip_count"] = new_trip_count

        return dict(stop_stats)

    async def _count_new_trips(
        self,
        bucket_start: datetime,
        stop_id: str,
        trip_ids: set[str],
    ) -> int:
        """Count trips not seen in this bucket yet using Valkey cache.

        Args:
            bucket_start: Time bucket start
            stop_id: Stop ID for the bucket
            trip_ids: Set of trip IDs to check

        Returns:
            Number of new (unseen) trips
        """
        if not self._cache or not trip_ids:
            # Without cache, count all as new (less accurate but functional)
            return len(trip_ids)

        bucket_key = bucket_start.strftime("%Y%m%d%H")
        new_count = 0

        for trip_id in trip_ids:
            # Create a unique cache key for this trip in this bucket
            cache_key = (
                f"gtfs_rt_trip:{bucket_key}:{stop_id}:{self._hash_trip_id(trip_id)}"
            )

            try:
                # Check if we've seen this trip
                seen = await self._cache.get(cache_key)  # type: ignore[attr-defined]
                if not seen:
                    # Mark as seen with TTL slightly longer than bucket
                    await self._cache.set(cache_key, "1", ttl_seconds=7200)  # type: ignore[attr-defined]  # 2 hours
                    new_count += 1
            except Exception as e:
                logger.debug("Cache operation failed: %s", e)
                new_count += 1  # Assume new on cache failure

        return new_count

    def _hash_trip_id(self, trip_id: str) -> str:
        """Create a short hash of trip_id to reduce cache key size."""
        return hashlib.md5(trip_id.encode(), usedforsecurity=False).hexdigest()[:12]

    async def _upsert_stats(
        self,
        session: AsyncSession,
        bucket_start: datetime,
        stop_stats: dict[str, dict],
    ) -> None:
        """Upsert aggregated stats to database using ON CONFLICT DO UPDATE.

        Args:
            session: Database session
            bucket_start: Time bucket start
            stop_stats: Aggregated stats by stop_id
        """
        for stop_id, stats in stop_stats.items():
            total_delay = sum(stats["delays"]) if stats["delays"] else 0

            stmt = insert(RealtimeStationStats).values(
                stop_id=stop_id,
                bucket_start=bucket_start,
                bucket_width_minutes=60,
                observation_count=1,
                trip_count=stats.get("new_trip_count", len(stats["trips"])),
                total_delay_seconds=total_delay,
                delayed_count=stats["delayed"],
                on_time_count=stats["on_time"],
                cancelled_count=stats["cancelled"],
            )

            stmt = stmt.on_conflict_do_update(
                constraint="uq_realtime_stats_unique",
                set_={
                    "observation_count": RealtimeStationStats.observation_count + 1,
                    "trip_count": (
                        RealtimeStationStats.trip_count
                        + stats.get("new_trip_count", len(stats["trips"]))
                    ),
                    "total_delay_seconds": (
                        RealtimeStationStats.total_delay_seconds + total_delay
                    ),
                    "delayed_count": (
                        RealtimeStationStats.delayed_count + stats["delayed"]
                    ),
                    "on_time_count": (
                        RealtimeStationStats.on_time_count + stats["on_time"]
                    ),
                    "cancelled_count": (
                        RealtimeStationStats.cancelled_count + stats["cancelled"]
                    ),
                    "last_updated_at": func.now(),
                },
            )

            await session.execute(stmt)

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

            count = result.rowcount or 0
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
