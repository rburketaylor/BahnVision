"""
GTFS-RT Data Harvester Service

Background service for collecting and persisting GTFS-RT trip updates
for historical analysis and heatmap aggregation.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.persistence.models import (
    ScheduleRelationship,
    StationAggregation,
    TripUpdateObservation,
)

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

# Delay threshold for counting a departure as "delayed" (in seconds)
DELAY_THRESHOLD_SECONDS = 300  # 5 minutes


class GTFSRTDataHarvester:
    """Background service for collecting and persisting GTFS-RT data.

    Periodically fetches trip updates from the GTFS-RT feed and stores them
    in the database for historical analysis. Also maintains pre-computed
    hourly aggregations for efficient heatmap queries.
    """

    def __init__(
        self,
        cache_service: CacheService | None = None,
        harvest_interval_seconds: int | None = None,
    ) -> None:
        """Initialize the harvester.

        Args:
            cache_service: Optional cache service for coordination
            harvest_interval_seconds: Override default harvest interval
        """
        self.settings = get_settings()
        self._cache = cache_service
        self._harvest_interval = harvest_interval_seconds or getattr(
            self.settings, "gtfs_rt_harvest_interval_seconds", 60
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

            await asyncio.sleep(self._harvest_interval)

    async def harvest_once(self) -> int:
        """Perform a single harvest iteration.

        Returns:
            Number of new observations recorded.
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

            # Store in database
            async with AsyncSessionFactory() as session:
                count = await self._store_observations(session, trip_updates)
                await session.commit()

            logger.info("Harvested %d trip update observations", count)

            # Trigger aggregation update (can run async)
            asyncio.create_task(self._update_aggregations())

            return count

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
                            "arrival_delay_seconds": (
                                stop_time_update.arrival.delay
                                if stop_time_update.HasField("arrival")
                                else None
                            ),
                            "departure_delay_seconds": (
                                stop_time_update.departure.delay
                                if stop_time_update.HasField("departure")
                                else None
                            ),
                            "schedule_relationship": schedule_rel,
                            "feed_timestamp": feed_timestamp,
                            "route_type": None,  # Could be enriched from GTFS static
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

    async def _store_observations(
        self,
        session: AsyncSession,
        trip_updates: list[dict],
    ) -> int:
        """Store trip update observations in the database.

        Uses INSERT ... ON CONFLICT DO NOTHING for deduplication.
        Batches inserts to avoid exceeding PostgreSQL's 32767 parameter limit.

        Returns:
            Number of rows inserted.
        """
        if not trip_updates:
            return 0

        # Each record has ~9 parameters, so batch size of 3000 is safe
        # (3000 * 9 = 27000 < 32767)
        BATCH_SIZE = 3000
        total_inserted = 0

        for i in range(0, len(trip_updates), BATCH_SIZE):
            batch = trip_updates[i : i + BATCH_SIZE]

            # Use PostgreSQL upsert with ON CONFLICT DO NOTHING
            stmt = insert(TripUpdateObservation).values(batch)
            stmt = stmt.on_conflict_do_nothing(
                constraint="uq_trip_update_unique",
            )

            result = await session.execute(stmt)
            total_inserted += result.rowcount or 0

        return total_inserted

    async def _update_aggregations(self, hours_back: int = 2) -> int:
        """Update pre-computed station aggregations.

        Recalculates aggregations for recent time buckets.

        Args:
            hours_back: Number of hours to recalculate

        Returns:
            Number of aggregation rows upserted.
        """
        async with AsyncSessionFactory() as session:
            now = datetime.now(timezone.utc)
            start_time = now - timedelta(hours=hours_back)

            # Calculate hourly buckets
            count = 0
            current_bucket = start_time.replace(minute=0, second=0, microsecond=0)

            while current_bucket < now:
                bucket_end = current_bucket + timedelta(hours=1)

                # Query aggregated stats for this bucket
                stmt = (
                    select(
                        TripUpdateObservation.stop_id,
                        func.count().label("total_departures"),
                        func.sum(
                            case(
                                (
                                    TripUpdateObservation.schedule_relationship
                                    == ScheduleRelationship.CANCELED,
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("cancelled_count"),
                        func.sum(
                            case(
                                (
                                    func.coalesce(
                                        TripUpdateObservation.departure_delay_seconds, 0
                                    )
                                    > DELAY_THRESHOLD_SECONDS,
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("delayed_count"),
                        func.avg(
                            func.coalesce(
                                TripUpdateObservation.departure_delay_seconds, 0
                            )
                        ).label("avg_delay_seconds"),
                        TripUpdateObservation.route_type,
                    )
                    .where(TripUpdateObservation.feed_timestamp >= current_bucket)
                    .where(TripUpdateObservation.feed_timestamp < bucket_end)
                    .group_by(
                        TripUpdateObservation.stop_id, TripUpdateObservation.route_type
                    )
                )

                result = await session.execute(stmt)
                rows = result.all()

                # Upsert aggregation rows
                for row in rows:
                    agg_stmt = insert(StationAggregation).values(
                        stop_id=row.stop_id,
                        bucket_start=current_bucket,
                        bucket_width_minutes=60,
                        total_departures=row.total_departures or 0,
                        cancelled_count=row.cancelled_count or 0,
                        delayed_count=row.delayed_count or 0,
                        avg_delay_seconds=float(row.avg_delay_seconds or 0),
                        route_type=row.route_type,
                    )
                    agg_stmt = agg_stmt.on_conflict_do_update(
                        constraint="uq_station_agg_unique",
                        set_={
                            "total_departures": agg_stmt.excluded.total_departures,
                            "cancelled_count": agg_stmt.excluded.cancelled_count,
                            "delayed_count": agg_stmt.excluded.delayed_count,
                            "avg_delay_seconds": agg_stmt.excluded.avg_delay_seconds,
                            "updated_at": func.now(),
                        },
                    )
                    await session.execute(agg_stmt)
                    count += 1

                current_bucket = bucket_end

            await session.commit()
            logger.debug("Updated %d aggregation rows", count)
            return count

    async def cleanup_old_observations(
        self,
        retention_days: int | None = None,
    ) -> int:
        """Remove observations older than retention period.

        Args:
            retention_days: Days to retain (defaults to config setting)

        Returns:
            Number of rows deleted.
        """
        days = retention_days or getattr(
            self.settings, "gtfs_rt_observation_retention_days", 30
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with AsyncSessionFactory() as session:
            stmt = delete(TripUpdateObservation).where(
                TripUpdateObservation.feed_timestamp < cutoff
            )
            result = await session.execute(stmt)
            await session.commit()

            count = result.rowcount or 0
            if count > 0:
                logger.info(
                    "Cleaned up %d observations older than %d days", count, days
                )
            return count


def get_gtfs_rt_harvester(
    cache_service: CacheService | None = None,
) -> GTFSRTDataHarvester:
    """Factory function for GTFSRTDataHarvester.

    Args:
        cache_service: Optional cache service

    Returns:
        Configured harvester instance
    """
    return GTFSRTDataHarvester(cache_service=cache_service)
