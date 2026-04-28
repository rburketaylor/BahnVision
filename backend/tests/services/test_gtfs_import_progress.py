from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.gtfs_import_progress import (
    GTFS_IMPORT_PROGRESS_KEY,
    GTFS_IMPORT_PROGRESS_TTL_SECONDS,
    GTFSImportProgressTracker,
)


class _FakeCache:
    def __init__(self) -> None:
        self.payload = None
        self.set_json = AsyncMock(side_effect=self._set_json)
        self.get_json = AsyncMock(side_effect=self._get_json)

    async def _set_json(self, key, value, ttl_seconds=None):
        self.payload = value

    async def _get_json(self, key):
        return self.payload


@pytest.fixture(autouse=True)
def _clear_progress_fallback():
    GTFSImportProgressTracker._fallback_progress = None
    GTFSImportProgressTracker._fallback_expires_at = None
    yield
    GTFSImportProgressTracker._fallback_progress = None
    GTFSImportProgressTracker._fallback_expires_at = None


@pytest.mark.asyncio
async def test_tracker_writes_and_reads_progress_json():
    cache = _FakeCache()
    tracker = GTFSImportProgressTracker(cache=cache)

    await tracker.start(phase="download", message="Downloading", percent=2)
    await tracker.update(
        phase="copy_stop_times",
        message="Copying stop_times.txt",
        percent=72.44,
        rows_processed=36_200_000,
        rows_total=50_000_000,
    )

    progress = await tracker.get()

    assert progress["state"] == "running"
    assert progress["phase"] == "copy_stop_times"
    assert progress["percent"] == 72.4
    assert progress["rows_processed"] == 36_200_000
    assert progress["rows_total"] == 50_000_000
    assert progress["started_at"] is not None
    assert progress["updated_at"] is not None
    cache.set_json.assert_awaited_with(
        GTFS_IMPORT_PROGRESS_KEY,
        progress,
        ttl_seconds=GTFS_IMPORT_PROGRESS_TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_tracker_records_success_and_failure_details():
    tracker = GTFSImportProgressTracker(cache=_FakeCache())

    await tracker.start(phase="read", message="Reading", percent=10)
    await tracker.succeed(message="Imported GTFS feed gtfs_1")

    success = await tracker.get()
    assert success["state"] == "succeeded"
    assert success["phase"] == "complete"
    assert success["percent"] == 100.0
    assert success["finished_at"] is not None

    await tracker.fail(ValueError("bad feed"))

    failure = await tracker.get()
    assert failure["state"] == "failed"
    assert failure["error_type"] == "ValueError"
    assert failure["error_message"] == "bad feed"


@pytest.mark.asyncio
async def test_tracker_never_raises_and_uses_process_fallback():
    cache = _FakeCache()
    cache.set_json.side_effect = RuntimeError("cache down")
    cache.get_json.side_effect = RuntimeError("cache down")
    tracker = GTFSImportProgressTracker(cache=cache)

    await tracker.start(phase="download", message="Downloading", percent=1)
    progress = await tracker.get()

    assert progress["state"] == "running"
    assert progress["phase"] == "download"
