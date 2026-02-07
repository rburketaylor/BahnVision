"""Unit tests for GTFS import lock fallbacks."""

from __future__ import annotations

import pytest

from app.services.gtfs_import_lock import GTFSImportLock


@pytest.mark.asyncio
async def test_file_lock_fallback_reports_not_in_progress_when_free():
    lock = GTFSImportLock(cache_service=None)
    assert await lock.is_import_in_progress() is False


@pytest.mark.asyncio
async def test_file_lock_fallback_tracks_local_import_session():
    lock = GTFSImportLock(cache_service=None)
    await lock._acquire_lock()
    try:
        assert await lock.is_import_in_progress() is True
    finally:
        await lock._release_lock()

    assert await lock.is_import_in_progress() is False


@pytest.mark.asyncio
async def test_file_lock_fallback_coordinates_across_instances():
    lock_a = GTFSImportLock(cache_service=None)
    lock_b = GTFSImportLock(cache_service=None)

    await lock_a._acquire_lock()
    try:
        assert await lock_b.is_import_in_progress() is True
    finally:
        await lock_a._release_lock()
