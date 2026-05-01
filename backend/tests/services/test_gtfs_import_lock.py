"""Unit tests for GTFS import lock fallbacks."""

from __future__ import annotations

import builtins

import pytest

from app.services.gtfs_import_lock import (
    GTFSImportLock,
    _GTFS_IMPORT_LOCK_KEY,
)


class _AtomicLockClient:
    def __init__(self, store: dict[str, str]) -> None:
        self._store = store

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool:
        del ex
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True


class _FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._client = _AtomicLockClient(self._store)

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        del ttl_seconds
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture(autouse=True)
def isolate_lock_file(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(
        "app.services.gtfs_import_lock._GTFS_IMPORT_LOCK_FILE",
        str(tmp_path / "bahnvision_gtfs_import.lock"),
    )


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


@pytest.mark.asyncio
async def test_distributed_lock_acquire_is_atomic_across_instances():
    cache = _FakeCache()
    lock_a = GTFSImportLock(cache_service=cache)
    lock_b = GTFSImportLock(cache_service=cache)

    await lock_a._acquire_lock()
    try:
        with pytest.raises(RuntimeError, match="already held"):
            await lock_b._acquire_lock()
        assert lock_b._in_memory_flag is False
        assert await lock_b.is_import_in_progress() is True
    finally:
        await lock_a._release_lock()

    assert await lock_b.is_import_in_progress() is False


@pytest.mark.asyncio
async def test_distributed_release_skips_delete_if_lock_value_changed():
    cache = _FakeCache()
    lock = GTFSImportLock(cache_service=cache)

    await lock._acquire_lock()
    cache._store[_GTFS_IMPORT_LOCK_KEY] = "different-owner"
    await lock._release_lock()

    assert cache._store[_GTFS_IMPORT_LOCK_KEY] == "different-owner"


@pytest.mark.asyncio
async def test_file_lock_status_probe_reused_across_checks(monkeypatch):
    lock = GTFSImportLock(cache_service=None)
    open_count = 0
    real_open = builtins.open

    def counting_open(*args, **kwargs):
        nonlocal open_count
        open_count += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.gtfs_import_lock.open",
        counting_open,
        raising=False,
    )

    assert await lock.is_import_in_progress() is False
    assert await lock.is_import_in_progress() is False
    assert await lock.is_import_in_progress() is False
    assert open_count == 1
