"""Progress tracking for GTFS static feed imports."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Protocol

from app.services.cache import get_cache_service

logger = logging.getLogger(__name__)

GTFS_IMPORT_PROGRESS_KEY = "gtfs:import:progress"
GTFS_IMPORT_PROGRESS_TTL_SECONDS = 24 * 60 * 60

GTFSImportProgressState = str
GTFSImportProgressPhase = str

_IDLE_PROGRESS: dict[str, Any] = {
    "state": "idle",
    "phase": None,
    "message": None,
    "percent": None,
    "rows_processed": None,
    "rows_total": None,
    "started_at": None,
    "updated_at": None,
    "finished_at": None,
    "error_type": None,
    "error_message": None,
}


class GTFSImportProgressTrackerProtocol(Protocol):
    async def start(
        self, *, phase: str, message: str, percent: float = 0.0
    ) -> None: ...

    async def update(
        self,
        *,
        phase: str,
        message: str,
        percent: float | None = None,
        rows_processed: int | None = None,
        rows_total: int | None = None,
    ) -> None: ...

    async def succeed(self, *, message: str = "GTFS import complete") -> None: ...

    async def fail(self, exc: Exception) -> None: ...


class NoOpGTFSImportProgressTracker:
    async def start(self, *, phase: str, message: str, percent: float = 0.0) -> None:
        return None

    async def update(
        self,
        *,
        phase: str,
        message: str,
        percent: float | None = None,
        rows_processed: int | None = None,
        rows_total: int | None = None,
    ) -> None:
        return None

    async def succeed(self, *, message: str = "GTFS import complete") -> None:
        return None

    async def fail(self, exc: Exception) -> None:
        return None


class GTFSImportProgressTracker:
    """Store GTFS import progress in Valkey with process-local fallback."""

    _fallback_progress: dict[str, Any] | None = None
    _fallback_expires_at: float | None = None

    def __init__(self, cache: Any | None = None) -> None:
        self._cache = cache

    async def start(self, *, phase: str, message: str, percent: float = 0.0) -> None:
        now = _utc_now_iso()
        await self._safe_write(
            {
                **_IDLE_PROGRESS,
                "state": "running",
                "phase": phase,
                "message": message,
                "percent": _clamp_percent(percent),
                "started_at": now,
                "updated_at": now,
            }
        )

    async def update(
        self,
        *,
        phase: str,
        message: str,
        percent: float | None = None,
        rows_processed: int | None = None,
        rows_total: int | None = None,
    ) -> None:
        current = await self.get()
        now = _utc_now_iso()
        payload = {
            **current,
            "state": "running",
            "phase": phase,
            "message": message,
            "updated_at": now,
            "error_type": None,
            "error_message": None,
        }
        if percent is not None:
            payload["percent"] = _clamp_percent(percent)
        if rows_processed is not None:
            payload["rows_processed"] = max(rows_processed, 0)
        if rows_total is not None:
            payload["rows_total"] = max(rows_total, 0)
        if payload.get("started_at") is None:
            payload["started_at"] = now
        await self._safe_write(payload)

    async def succeed(self, *, message: str = "GTFS import complete") -> None:
        current = await self.get()
        now = _utc_now_iso()
        await self._safe_write(
            {
                **current,
                "state": "succeeded",
                "phase": "complete",
                "message": message,
                "percent": 100.0,
                "updated_at": now,
                "finished_at": now,
                "error_type": None,
                "error_message": None,
            }
        )

    async def fail(self, exc: Exception) -> None:
        current = await self.get()
        now = _utc_now_iso()
        await self._safe_write(
            {
                **current,
                "state": "failed",
                "updated_at": now,
                "finished_at": now,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        )

    async def get(self) -> dict[str, Any]:
        try:
            cache = self._get_cache()
            payload = await cache.get_json(GTFS_IMPORT_PROGRESS_KEY)
            if isinstance(payload, dict):
                return _normalize_progress(payload)
        except Exception:
            logger.warning(
                "Failed to read GTFS import progress from cache", exc_info=True
            )

        if (
            self._fallback_progress is not None
            and self._fallback_expires_at is not None
            and self._fallback_expires_at > time.monotonic()
        ):
            return _normalize_progress(self._fallback_progress)
        type(self)._fallback_progress = None
        type(self)._fallback_expires_at = None
        return dict(_IDLE_PROGRESS)

    def _get_cache(self) -> Any:
        if self._cache is None:
            self._cache = get_cache_service()
        return self._cache

    async def _safe_write(self, payload: dict[str, Any]) -> None:
        normalized = _normalize_progress(payload)
        type(self)._fallback_progress = normalized
        type(self)._fallback_expires_at = (
            time.monotonic() + GTFS_IMPORT_PROGRESS_TTL_SECONDS
        )
        try:
            cache = self._get_cache()
            await cache.set_json(
                GTFS_IMPORT_PROGRESS_KEY,
                normalized,
                ttl_seconds=GTFS_IMPORT_PROGRESS_TTL_SECONDS,
            )
        except Exception:
            logger.warning(
                "Failed to write GTFS import progress to cache", exc_info=True
            )


def get_gtfs_import_progress_tracker() -> GTFSImportProgressTracker:
    return GTFSImportProgressTracker()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp_percent(percent: float) -> float:
    return round(max(0.0, min(float(percent), 100.0)), 1)


def _normalize_progress(payload: dict[str, Any]) -> dict[str, Any]:
    progress = dict(_IDLE_PROGRESS)
    progress.update(payload)
    if progress["percent"] is not None:
        progress["percent"] = _clamp_percent(float(progress["percent"]))
    for key in ("rows_processed", "rows_total"):
        if progress[key] is not None:
            progress[key] = max(int(progress[key]), 0)
    return progress
