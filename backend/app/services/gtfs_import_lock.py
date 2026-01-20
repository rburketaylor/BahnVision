"""
GTFS Import Lock Service.

Provides coordination between the GTFS feed importer and the GTFS-RT harvester
to prevent the harvester from running during feed imports (which would cause
database deadlocks).

Uses Valkey/Redis as a distributed lock to ensure coordination works across
multiple workers if needed.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.cache import CacheService

logger = logging.getLogger(__name__)

# Cache key for the import lock
_GTFS_IMPORT_LOCK_KEY = "gtfs:import:in_progress"
# Maximum time the import lock can be held (safety timeout)
_GTFS_IMPORT_LOCK_MAX_TTL_SECONDS = 1800  # 30 minutes


class GTFSImportLock:
    """
    Manages a distributed lock to coordinate GTFS feed imports.

    The harvester should check `is_import_in_progress()` before each cycle
    and skip if an import is running. The feed importer uses the context
    manager `import_session()` to automatically acquire/release the lock.
    """

    def __init__(self, cache_service: CacheService | None = None) -> None:
        """
        Initialize the import lock.

        Args:
            cache_service: Optional cache service for distributed locking.
                          Falls back to in-memory flag if not provided.
        """
        self._cache = cache_service
        # Fallback in-memory flag for when cache is unavailable
        self._in_memory_flag = False
        self._import_started_at: datetime | None = None

    async def is_import_in_progress(self) -> bool:
        """
        Check if a GTFS feed import is currently in progress.

        Returns:
            True if an import is running, False otherwise.
        """
        # First check the distributed lock if available
        if self._cache is not None:
            try:
                value = await self._cache.get(_GTFS_IMPORT_LOCK_KEY)
                if value is not None:
                    logger.debug("GTFS import lock found in cache: %s", value)
                    return True
            except Exception as e:
                logger.warning("Failed to check import lock in cache: %s", e)

        # Fall back to in-memory flag
        return self._in_memory_flag

    async def _acquire_lock(self) -> None:
        """Acquire the import lock."""
        self._in_memory_flag = True
        self._import_started_at = datetime.now(timezone.utc)

        if self._cache is not None:
            try:
                await self._cache.set(
                    _GTFS_IMPORT_LOCK_KEY,
                    self._import_started_at.isoformat(),
                    ttl_seconds=_GTFS_IMPORT_LOCK_MAX_TTL_SECONDS,
                )
                logger.info("Acquired GTFS import lock (distributed)")
            except Exception as e:
                logger.warning("Failed to set import lock in cache: %s", e)
        else:
            logger.info("Acquired GTFS import lock (in-memory only)")

    async def _release_lock(self) -> None:
        """Release the import lock."""
        self._in_memory_flag = False
        duration = None
        if self._import_started_at:
            duration = datetime.now(timezone.utc) - self._import_started_at
        self._import_started_at = None

        if self._cache is not None:
            try:
                await self._cache.delete(_GTFS_IMPORT_LOCK_KEY)
                logger.info(
                    "Released GTFS import lock (distributed, duration: %s)",
                    duration,
                )
            except Exception as e:
                logger.warning("Failed to delete import lock from cache: %s", e)
        else:
            logger.info("Released GTFS import lock (in-memory, duration: %s)", duration)

    @asynccontextmanager
    async def import_session(self):
        """
        Context manager for GTFS feed import.

        Acquires the lock on entry and releases it on exit (even if an error occurs).

        Usage:
            async with import_lock.import_session():
                await do_import()
        """
        await self._acquire_lock()
        try:
            yield
        finally:
            await self._release_lock()


# Global singleton instance - initialized in main.py lifespan
_global_import_lock: GTFSImportLock | None = None


def get_import_lock() -> GTFSImportLock:
    """
    Get the global import lock instance.

    Returns:
        The global GTFSImportLock instance.

    Raises:
        RuntimeError: If the import lock hasn't been initialized yet.
    """
    global _global_import_lock
    if _global_import_lock is None:
        # Create a default instance without cache for backwards compatibility
        _global_import_lock = GTFSImportLock(cache_service=None)
    return _global_import_lock


def init_import_lock(cache_service: CacheService | None = None) -> GTFSImportLock:
    """
    Initialize the global import lock with the given cache service.

    Should be called once during application startup.

    Args:
        cache_service: Cache service for distributed locking.

    Returns:
        The initialized GTFSImportLock instance.
    """
    global _global_import_lock
    _global_import_lock = GTFSImportLock(cache_service=cache_service)
    logger.info("Initialized GTFS import lock")
    return _global_import_lock
