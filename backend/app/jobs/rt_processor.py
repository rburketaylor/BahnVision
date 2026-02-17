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

_MIN_LOOP_WAIT_SECONDS = 0.1
_MAX_ERROR_BACKOFF_SECONDS = 30.0


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
        base_wait_seconds = self._resolve_base_wait_seconds()
        consecutive_errors = 0

        while not self._shutdown_event.is_set():
            wait_seconds = base_wait_seconds
            try:
                if not self.gtfs_service:
                    logger.warning("GTFS-RT service not initialized")
                    break

                # Fetch and process all RT data in a single request
                # This is more efficient than fetching each type separately
                # as most GTFS-RT feeds combine all entities in one file
                result = await self.gtfs_service.fetch_and_process_feed()

                logger.debug(
                    f"GTFS-RT cycle completed: "
                    f"{result.get('trip_updates', 0)} trip updates, "
                    f"{result.get('vehicle_positions', 0)} vehicle positions, "
                    f"{result.get('alerts', 0)} alerts"
                )
                consecutive_errors = 0

            except asyncio.CancelledError:
                logger.info("GTFS-RT processing loop cancelled")
                break
            except Exception as e:
                consecutive_errors += 1
                wait_seconds = min(
                    base_wait_seconds * (2 ** min(consecutive_errors - 1, 8)),
                    _MAX_ERROR_BACKOFF_SECONDS,
                )
                logger.error(f"Unexpected error in GTFS-RT processing loop: {e}")

            # Wait for the next cycle or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=wait_seconds,
                )
                break  # Shutdown event was set
            except asyncio.TimeoutError:
                # Continue to next iteration
                continue

    def _resolve_base_wait_seconds(self) -> float:
        """Return a safe positive loop wait duration."""
        configured_timeout = float(self.settings.gtfs_rt_timeout_seconds)
        if configured_timeout > 0:
            return configured_timeout

        logger.warning(
            "GTFS-RT timeout %.3fs is non-positive; using %.1fs safety wait to avoid tight-loop spinning",
            configured_timeout,
            _MIN_LOOP_WAIT_SECONDS,
        )
        return _MIN_LOOP_WAIT_SECONDS


@asynccontextmanager
async def gtfs_rt_lifespan_manager(cache_service: CacheService):
    """Context manager for GTFS-RT processor lifecycle"""
    processor = GtfsRealtimeProcessor(cache_service)
    try:
        await processor.start()
        yield processor
    finally:
        await processor.stop()
