"""
GTFS Real-Time Background Processor

Handles continuous background processing of GTFS-RT data streams.
Runs within the FastAPI application lifespan to fetch and process
real-time transit data at regular intervals.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from app.core.config import get_settings
from app.services.cache import CacheService
from app.services.gtfs_realtime import GtfsRealtimeService

logger = logging.getLogger(__name__)


class GtfsRealtimeProcessor:
    """Background processor for GTFS-RT data streams"""

    def __init__(self, cache_service: CacheService):
        self.settings = get_settings()
        self.cache_service = cache_service
        self.gtfs_service: Optional[GtfsRealtimeService] = None
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the background processing loop"""
        if not self.settings.gtfs_rt_enabled:
            logger.info("GTFS-RT processing disabled by configuration")
            return

        logger.info("Starting GTFS-RT background processor")
        self.gtfs_service = GtfsRealtimeService(self.cache_service)
        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._processing_loop())

    async def stop(self):
        """Stop the background processing loop"""
        if self._task:
            logger.info("Stopping GTFS-RT background processor")
            self._shutdown_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _processing_loop(self):
        """Main processing loop that fetches GTFS-RT data"""
        while not self._shutdown_event.is_set():
            try:
                if not self.gtfs_service:
                    logger.warning("GTFS-RT service not initialized")
                    break

                # Fetch all types of RT data
                trip_updates_task = self.gtfs_service.fetch_trip_updates()
                vehicle_positions_task = self.gtfs_service.fetch_vehicle_positions()
                alerts_task = self.gtfs_service.fetch_alerts()

                # Run all fetches concurrently
                results = await asyncio.gather(
                    trip_updates_task,
                    vehicle_positions_task,
                    alerts_task,
                    return_exceptions=True,
                )

                # Log results and handle exceptions
                trip_updates_count = 0
                vehicle_positions_count = 0
                alerts_count = 0

                # Log individual failures and count successes
                trip_updates_result = results[0]
                vehicle_positions_result = results[1]
                alerts_result = results[2]

                if isinstance(trip_updates_result, Exception):
                    logger.error(f"Trip updates fetch failed: {trip_updates_result}")
                else:
                    trip_updates_count = len(trip_updates_result)  # type: ignore

                if isinstance(vehicle_positions_result, Exception):
                    logger.error(
                        f"Vehicle positions fetch failed: {vehicle_positions_result}"
                    )
                else:
                    vehicle_positions_count = len(vehicle_positions_result)  # type: ignore

                if isinstance(alerts_result, Exception):
                    logger.error(f"Alerts fetch failed: {alerts_result}")
                else:
                    alerts_count = len(alerts_result)  # type: ignore

                logger.debug(
                    f"GTFS-RT cycle completed: "
                    f"{trip_updates_count} trip updates, "
                    f"{vehicle_positions_count} vehicle positions, "
                    f"{alerts_count} alerts"
                )

            except asyncio.CancelledError:
                logger.info("GTFS-RT processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in GTFS-RT processing loop: {e}")

            # Wait for the next cycle or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.settings.gtfs_rt_timeout_seconds,
                )
                break  # Shutdown event was set
            except asyncio.TimeoutError:
                # Continue to next iteration
                continue


@asynccontextmanager
async def gtfs_rt_lifespan_manager(cache_service: CacheService):
    """Context manager for GTFS-RT processor lifecycle"""
    processor = GtfsRealtimeProcessor(cache_service)
    try:
        await processor.start()
        yield processor
    finally:
        await processor.stop()
