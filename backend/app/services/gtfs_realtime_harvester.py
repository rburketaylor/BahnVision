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
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionFactory
from app.jobs.heatmap_cache_warmup import HeatmapCacheWarmer
from app.models.heatmap import (
    HeatmapDataPoint,
    HeatmapResponse,
    HeatmapSummary,
    TimeRange,
    TransportStats,
)
from app.persistence.models import RealtimeStationStats, ScheduleRelationship
from app.services.heatmap_cache import heatmap_live_snapshot_cache_key
from app.services.heatmap_service import GTFS_ROUTE_TYPES, TRANSPORT_TYPE_NAMES

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
        self._heatmap_cache_warmer: HeatmapCacheWarmer | None = (
            HeatmapCacheWarmer(cache_service)
            if cache_service is not None
            and hasattr(cache_service, "get_json")
            and hasattr(cache_service, "set_json")
            else None
        )
        self._harvest_interval = harvest_interval_seconds or getattr(
            self.settings, "gtfs_rt_harvest_interval_seconds", 300
        )
        self._running = False
        self._task: asyncio.Task | None = None
        # Status tracking for monitoring
        self._last_harvest_at: datetime | None = None
        self._last_stations_updated: int = 0

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

    def get_status(self) -> dict:
        """Get current harvester status for monitoring.

        Returns:
            Dict with running status and last harvest info.
        """
        return {
            "is_running": self._running,
            "last_harvest_at": self._last_harvest_at,
            "stations_updated_last_harvest": self._last_stations_updated,
        }

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

            # 1. Fetch trip updates from feed
            trip_updates = await self._fetch_trip_updates()

            now = datetime.now(timezone.utc)

            if not trip_updates:
                # Even with no trip updates, cache an empty live snapshot so the
                # API can distinguish "harvester not running" (503) from
                # "harvester running but no impacted stations" (200 with empty list).
                logger.info("No trip updates received - caching empty live snapshot")
                async with AsyncSessionFactory() as session:
                    await self._cache_live_snapshot(session, {}, now)

                # Update status tracking to reflect successful (but empty) harvest
                self._last_harvest_at = now
                self._last_stations_updated = 0
                return 0

            logger.info(f"Received {len(trip_updates)} trip updates from GTFS-RT feed")

            updated_count = 0
            async with AsyncSessionFactory() as session:
                # 2. Fetch route_id -> route_type mapping for transport mode grouping
                route_type_map = await self._get_route_type_map(session)

                # 3. Calculate current time bucket (hourly)
                bucket_start = now.replace(minute=0, second=0, microsecond=0)
                logger.debug(
                    f"Processing data for bucket starting at {bucket_start.isoformat()}"
                )

                # 4. Group updates by stop_id and route_type and aggregate
                stop_stats = await self._aggregate_by_stop_and_route(
                    trip_updates, bucket_start, route_type_map
                )

                snapshot_stats = self._aggregate_snapshot_by_stop_and_route(
                    trip_updates, route_type_map
                )
                snapshot_timestamp = self._resolve_snapshot_timestamp(trip_updates)

                # Always cache the live snapshot, even if no stop_stats for DB upsert.
                # This ensures the API can serve a 200 response when the harvester
                # is running but there are no impacted stations.
                await self._cache_live_snapshot(
                    session, snapshot_stats, snapshot_timestamp
                )

                if not stop_stats:
                    logger.debug("No stop statistics generated from trip updates")
                    self._last_harvest_at = now
                    self._last_stations_updated = 0
                    return 0

                # 5. Upsert aggregations to database
                await self._upsert_stats(session, bucket_start, stop_stats)
                await session.commit()
                updated_count = len(stop_stats)

            # Update status tracking
            self._last_harvest_at = datetime.now(timezone.utc)
            self._last_stations_updated = updated_count

            logger.info(
                "Harvested and aggregated stats for %d station-route combinations",
                updated_count,
            )

            if updated_count > 0 and self._heatmap_cache_warmer is not None:
                self._heatmap_cache_warmer.trigger(reason="gtfs-rt harvest")

            return updated_count

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
            # Use explicit timeout for large feed download (~27MB)
            timeout = httpx.Timeout(
                connect=30.0,
                read=180.0,  # 3 minutes for large feed
                write=30.0,
                pool=30.0,
            )
            async with httpx.AsyncClient(
                timeout=timeout,
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
            logger.exception(
                "Failed to fetch trip updates: %s: %s", type(e).__name__, e
            )
            return []

    def _map_schedule_relationship(self, relationship: int) -> ScheduleRelationship:
        """Map GTFS-RT schedule relationship code to enum."""
        mapping = {
            0: ScheduleRelationship.SCHEDULED,
            1: ScheduleRelationship.SKIPPED,
            2: ScheduleRelationship.NO_DATA,
            3: ScheduleRelationship.UNSCHEDULED,
            4: ScheduleRelationship.CANCELED,
        }
        return mapping.get(relationship, ScheduleRelationship.SCHEDULED)

    async def _get_route_type_map(self, session: AsyncSession) -> dict[str, int]:
        """Fetch route_id -> route_type mapping from gtfs_routes table."""
        try:
            stmt = text("SELECT route_id, route_type FROM gtfs_routes")
            result = await session.execute(stmt)
            return {str(row[0]): int(row[1]) for row in result.all()}
        except Exception as e:
            logger.warning(f"Failed to fetch route type map: {e}")
            return {}

    async def _aggregate_by_stop(
        self,
        trip_updates: list[dict],
        bucket_start: datetime,
    ) -> dict[str, dict]:
        """Aggregate trip updates by stop_id with deduplication.

        This method exists primarily for backwards compatibility with earlier
        versions of the harvester (and for unit tests). Newer code paths use
        `_aggregate_by_stop_and_route` for per-route_type stats, but heatmap
        generation only needs stop-level totals and the DB layer can still roll
        up per-route_type rows later.

        Returns:
            Dict mapping stop_id -> aggregated deltas.
        """
        # Determine the status of each unique trip at each stop.
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
                existing = trip_status_by_stop[key]
                existing["delay"] = max(existing["delay"], delay)
                existing["cancelled"] = existing["cancelled"] or is_cancelled

        # Aggregate per stop using cache-backed deduplication logic.
        trip_statuses_per_stop: dict[str, dict[str, dict]] = defaultdict(dict)
        for (stop_id, trip_id), status in trip_status_by_stop.items():
            trip_statuses_per_stop[stop_id][trip_id] = {
                "delay": status["delay"],
                "status": self._classify_status(status["delay"], status["cancelled"]),
            }

        final_stats: dict[str, dict] = {}
        for stop_id, trip_statuses in trip_statuses_per_stop.items():
            final_stats[stop_id] = await self._apply_trip_statuses(
                bucket_start, stop_id, trip_statuses
            )

        return final_stats

    async def _aggregate_by_stop_and_route(
        self,
        trip_updates: list[dict],
        bucket_start: datetime,
        route_type_map: dict[str, int],
    ) -> dict[tuple[str, int | None], dict]:
        """Aggregate trip updates by (stop_id, route_type) with deduplication.

        Counts delays/cancellations per UNIQUE TRIP, not per stop_time_update.
        Each trip is classified once per bucket.

        Returns:
            Dict mapping (stop_id, route_type) -> aggregated statistics
        """
        # First pass: determine the status of each unique trip at each stop
        # Key: (stop_id, route_type, trip_id) -> {"delay": max_delay, "cancelled": bool}
        trip_status_by_stop: dict[tuple[str, int | None, str], dict] = {}

        for update in trip_updates:
            stop_id = update["stop_id"]
            trip_id = update["trip_id"]
            route_id = update.get("route_id")
            route_type = route_type_map.get(route_id) if route_id else None

            key = (stop_id, route_type, trip_id)

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
                existing = trip_status_by_stop[key]
                existing["delay"] = max(existing["delay"], delay)
                existing["cancelled"] = existing["cancelled"] or is_cancelled

        # Second pass: aggregate by (stop_id, route_type)
        stats_by_key: dict[tuple[str, int | None], dict] = defaultdict(
            lambda: {"trip_statuses": {}}
        )

        for trip_key, status in trip_status_by_stop.items():
            s_id, r_type, t_id = trip_key
            stats_by_key[(s_id, r_type)]["trip_statuses"][t_id] = {
                "delay": status["delay"],
                "status": self._classify_status(status["delay"], status["cancelled"]),
            }

        final_stats: dict[tuple[str, int | None], dict] = {}
        for agg_key, stats in stats_by_key.items():
            stop_id_val, route_type_val = agg_key
            deltas = await self._apply_trip_statuses(
                bucket_start, f"{stop_id_val}:{route_type_val}", stats["trip_statuses"]
            )
            final_stats[agg_key] = deltas

        return final_stats

    def _aggregate_snapshot_by_stop_and_route(
        self,
        trip_updates: list[dict],
        route_type_map: dict[str, int],
    ) -> dict[tuple[str, int | None], dict]:
        """Aggregate trip updates into a point-in-time snapshot.

        Counts delays/cancellations per unique trip in the current feed.
        """
        trip_status_by_stop: dict[tuple[str, int | None, str], dict] = {}

        for update in trip_updates:
            stop_id = update["stop_id"]
            trip_id = update["trip_id"]
            route_id = update.get("route_id")
            route_type = route_type_map.get(route_id) if route_id else None

            key = (stop_id, route_type, trip_id)

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
                existing = trip_status_by_stop[key]
                existing["delay"] = max(existing["delay"], delay)
                existing["cancelled"] = existing["cancelled"] or is_cancelled

        snapshot_stats: dict[tuple[str, int | None], dict] = defaultdict(
            lambda: {
                "trip_count": 0,
                "total_delay_seconds": 0,
                "delayed": 0,
                "on_time": 0,
                "cancelled": 0,
            }
        )

        for (stop_id, route_type, _trip_id), status in trip_status_by_stop.items():
            entry = snapshot_stats[(stop_id, route_type)]
            entry["trip_count"] += 1
            entry["total_delay_seconds"] += status["delay"]
            classified = self._classify_status(status["delay"], status["cancelled"])
            if classified == STATUS_DELAYED:
                entry["delayed"] += 1
            elif classified == STATUS_ON_TIME:
                entry["on_time"] += 1
            elif classified == STATUS_CANCELLED:
                entry["cancelled"] += 1

        return snapshot_stats

    def _resolve_snapshot_timestamp(self, trip_updates: list[dict]) -> datetime:
        """Pick the snapshot timestamp from feed metadata."""
        timestamps: list[datetime] = [
            update["feed_timestamp"]
            for update in trip_updates
            if isinstance(update.get("feed_timestamp"), datetime)
        ]
        if timestamps:
            return max(timestamps)
        return datetime.now(timezone.utc)

    async def _cache_live_snapshot(
        self,
        session: AsyncSession,
        snapshot_stats: dict[tuple[str, int | None], dict],
        snapshot_timestamp: datetime,
    ) -> None:
        """Build and cache the live heatmap snapshot."""
        if not self._cache or not hasattr(self._cache, "set_json"):
            return

        by_stop: dict[str, dict] = {}
        for (stop_id, route_type), stats in snapshot_stats.items():
            total = int(stats.get("trip_count", 0) or 0)
            if total <= 0:
                continue

            cancelled = int(stats.get("cancelled", 0) or 0)
            delayed = int(stats.get("delayed", 0) or 0)

            entry = by_stop.setdefault(
                stop_id, {"total": 0, "cancelled": 0, "delayed": 0, "by_transport": {}}
            )
            entry["total"] += total
            entry["cancelled"] += cancelled
            entry["delayed"] += delayed

            if route_type is None:
                continue
            transport_type = GTFS_ROUTE_TYPES.get(route_type, "BUS")
            transport_entry = entry["by_transport"].setdefault(
                transport_type, {"total": 0, "cancelled": 0, "delayed": 0}
            )
            transport_entry["total"] += total
            transport_entry["cancelled"] += cancelled
            transport_entry["delayed"] += delayed

        impacted_stop_ids = [
            stop_id
            for stop_id, stats in by_stop.items()
            if stats["cancelled"] > 0 or stats["delayed"] > 0
        ]

        stop_metadata: dict[str, tuple[str, float, float]] = {}
        if impacted_stop_ids:
            from app.models.gtfs import GTFSStop

            stmt = (
                select(
                    GTFSStop.stop_id,
                    GTFSStop.stop_name,
                    GTFSStop.stop_lat,
                    GTFSStop.stop_lon,
                )
                .where(GTFSStop.stop_id.in_(impacted_stop_ids))
                .where(GTFSStop.stop_lat.isnot(None))
                .where(GTFSStop.stop_lon.isnot(None))
            )
            result = await session.execute(stmt)
            for row in result.all():
                stop_metadata[row.stop_id] = (
                    row.stop_name or row.stop_id,
                    float(row.stop_lat),
                    float(row.stop_lon),
                )

        data_points: list[HeatmapDataPoint] = []
        for stop_id in impacted_stop_ids:
            info = stop_metadata.get(stop_id)
            if not info:
                continue
            station_name, lat, lon = info
            stats = by_stop[stop_id]
            total = int(stats["total"])
            cancelled = int(stats["cancelled"])
            delayed = int(stats["delayed"])
            if total <= 0:
                continue

            # Station-level rates for popup display.
            cancellation_rate = min(cancelled / total, 1.0) if total > 0 else 0.0
            delay_rate = min(delayed / total, 1.0) if total > 0 else 0.0

            by_transport = {
                key: TransportStats(
                    total=int(val["total"]),
                    cancelled=int(val["cancelled"]),
                    delayed=int(val["delayed"]),
                )
                for key, val in stats["by_transport"].items()
            }

            data_points.append(
                HeatmapDataPoint(
                    station_id=stop_id,
                    station_name=station_name,
                    latitude=lat,
                    longitude=lon,
                    total_departures=total,
                    cancelled_count=cancelled,
                    cancellation_rate=cancellation_rate,
                    delayed_count=delayed,
                    delay_rate=delay_rate,
                    by_transport=by_transport,
                )
            )

        network_total_departures = sum(
            int(stats["total"]) for stats in by_stop.values()
        )
        network_total_cancellations = sum(
            int(stats["cancelled"]) for stats in by_stop.values()
        )
        network_total_delays = sum(int(stats["delayed"]) for stats in by_stop.values())
        network_total_stations = sum(
            1 for stats in by_stop.values() if int(stats["total"]) > 0
        )

        overall_cancellation_rate = (
            min(network_total_cancellations / network_total_departures, 1.0)
            if network_total_departures > 0
            else 0.0
        )
        overall_delay_rate = (
            min(network_total_delays / network_total_departures, 1.0)
            if network_total_departures > 0
            else 0.0
        )

        most_affected_station = None
        affected_stations = [dp for dp in data_points if dp.total_departures >= 50]
        if affected_stations:
            most_affected_station = max(
                affected_stations,
                key=lambda x: x.delay_rate + x.cancellation_rate,
            ).station_name

        line_stats: dict[str, dict[str, int]] = {}
        for stats in by_stop.values():
            for transport, transport_stats in stats["by_transport"].items():
                entry = line_stats.setdefault(
                    transport, {"total": 0, "cancelled": 0, "delayed": 0}
                )
                entry["total"] += int(transport_stats["total"])
                entry["cancelled"] += int(transport_stats["cancelled"])
                entry["delayed"] += int(transport_stats["delayed"])

        most_affected_line = None
        highest_line_rate = 0.0
        for line, line_stat in line_stats.items():
            total = line_stat["total"]
            if total < 100:
                continue
            combined_rate = (line_stat["cancelled"] + line_stat["delayed"]) / total
            if combined_rate > highest_line_rate:
                highest_line_rate = combined_rate
                most_affected_line = TRANSPORT_TYPE_NAMES.get(line, line)

        summary = HeatmapSummary(
            total_stations=network_total_stations,
            total_departures=network_total_departures,
            total_cancellations=network_total_cancellations,
            overall_cancellation_rate=overall_cancellation_rate,
            total_delays=network_total_delays,
            overall_delay_rate=overall_delay_rate,
            most_affected_station=most_affected_station,
            most_affected_line=most_affected_line,
        )
        interval_seconds = self._harvest_interval or 300
        from_time = snapshot_timestamp - timedelta(seconds=interval_seconds)

        snapshot = HeatmapResponse(
            time_range=TimeRange.model_validate(
                {"from": from_time, "to": snapshot_timestamp}
            ),
            data_points=data_points,
            summary=summary,
            last_updated_at=snapshot_timestamp,
        )

        settings = get_settings()
        await self._cache.set_json(
            heatmap_live_snapshot_cache_key(),
            snapshot.model_dump(mode="json"),
            ttl_seconds=settings.heatmap_live_cache_ttl_seconds,
            stale_ttl_seconds=settings.heatmap_live_cache_stale_ttl_seconds,
        )

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
        stop_stats: dict[tuple[str, int | None], dict],
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
                    cancelled_count INTEGER NOT NULL,
                    route_type INTEGER
                ) ON COMMIT DROP
                """
            )
        )

        # 2. Build TSV data for COPY
        bucket_str = bucket_start.isoformat()
        lines = []
        for key, stats in stop_stats.items():
            stop_id, route_type = key
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
                    _escape_tsv(route_type),
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
                "route_type",
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
                    delayed_count, on_time_count, cancelled_count, route_type
                )
                SELECT
                    stop_id, bucket_start, bucket_width_minutes,
                    observation_count, trip_count, total_delay_seconds,
                    delayed_count, on_time_count, cancelled_count, route_type
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
