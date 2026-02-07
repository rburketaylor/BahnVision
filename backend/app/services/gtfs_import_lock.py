"""
GTFS Import Lock Service.

Provides coordination between the GTFS feed importer and the GTFS-RT harvester
to prevent the harvester from running during feed imports (which would cause
database deadlocks).

Uses Valkey/Redis as a distributed lock to ensure coordination works across
multiple workers if needed.
"""

from __future__ import annotations

import fcntl
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from app.services.cache import CacheService

logger = logging.getLogger(__name__)

# Cache key for the import lock
_GTFS_IMPORT_LOCK_KEY = "gtfs:import:in_progress"
# Maximum time the import lock can be held (safety timeout)
_GTFS_IMPORT_LOCK_MAX_TTL_SECONDS = 1800  # 30 minutes
# Fallback file lock path when distributed cache is unavailable.
_GTFS_IMPORT_LOCK_FILE = "/tmp/bahnvision_gtfs_import.lock"


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
        self._file_lock_handle: TextIO | None = None

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

        # Local process state check first.
        if self._in_memory_flag:
            return True

        # Cross-process fallback: check local file lock state.
        return self._is_file_lock_held()

    async def _acquire_lock(self) -> None:
        """Acquire the import lock."""
        self._in_memory_flag = True
        self._import_started_at = datetime.now(timezone.utc)

        distributed_acquired = False
        if self._cache is not None:
            try:
                await self._cache.set(
                    _GTFS_IMPORT_LOCK_KEY,
                    self._import_started_at.isoformat(),
                    ttl_seconds=_GTFS_IMPORT_LOCK_MAX_TTL_SECONDS,
                )
                logger.info("Acquired GTFS import lock (distributed)")
                distributed_acquired = True
            except Exception as e:
                logger.warning("Failed to set import lock in cache: %s", e)

        if not distributed_acquired:
            self._acquire_file_lock()
            logger.info("Acquired GTFS import lock (local file fallback)")

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

        self._release_file_lock()
        logger.info("Released GTFS import lock (duration: %s)", duration)

    def _acquire_file_lock(self) -> None:
        """Acquire a non-blocking local file lock for cross-process coordination."""
        if self._file_lock_handle is not None:
            return

        lock_dir = os.path.dirname(_GTFS_IMPORT_LOCK_FILE)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        lock_handle = open(_GTFS_IMPORT_LOCK_FILE, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_handle.close()
            raise RuntimeError(
                "Could not acquire fallback GTFS import file lock"
            ) from exc
        self._file_lock_handle = lock_handle

    def _release_file_lock(self) -> None:
        """Release the local fallback file lock if held."""
        if self._file_lock_handle is None:
            return
        try:
            fcntl.flock(self._file_lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._file_lock_handle.close()
            self._file_lock_handle = None

    def _is_file_lock_held(self) -> bool:
        """Check whether another process holds the fallback file lock."""
        if self._file_lock_handle is not None:
            return True

        lock_dir = os.path.dirname(_GTFS_IMPORT_LOCK_FILE)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)

        probe = open(_GTFS_IMPORT_LOCK_FILE, "a+", encoding="utf-8")
        try:
            try:
                fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            else:
                fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
                return False
        finally:
            probe.close()

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
