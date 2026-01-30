"""
Heatmap cache warmup job.

The heatmap aggregation query can be expensive on cold caches. This job prewarms
the most common heatmap variants (by time range + density) after each GTFS-RT
harvest cycle so first user refreshes are fast.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import cast

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionFactory
from app.models.heatmap import TimeRangePreset
from app.services.heatmap_cache import heatmap_cancellations_cache_key
from app.services.heatmap_service import (
    HeatmapOverviewMetric,
    HeatmapService,
    resolve_max_points,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HeatmapWarmupTarget:
    time_range: TimeRangePreset
    transport_modes: str | None
    bucket_width_minutes: int
    max_points: int
    is_overview: bool = False
    metrics: HeatmapOverviewMetric = "both"

    @property
    def cache_key(self) -> str:
        if self.is_overview:
            return (
                f"heatmap:overview:{self.time_range or 'default'}:"
                f"{self.transport_modes or 'all'}:{self.bucket_width_minutes}:{self.metrics}"
            )
        return heatmap_cancellations_cache_key(
            time_range=self.time_range,
            transport_modes=self.transport_modes,
            bucket_width_minutes=self.bucket_width_minutes,
            max_points=self.max_points,
        )


class HeatmapCacheWarmer:
    """Background warmup runner for heatmap cache keys."""

    def __init__(self, cache_service) -> None:
        self._settings: Settings = get_settings()
        self._cache = cache_service
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    def trigger(self, *, reason: str) -> None:
        """Schedule a warmup run if one isn't already running."""
        if not self._settings.heatmap_cache_warmup_enabled:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._warmup(reason=reason))

    async def shutdown(self) -> None:
        """Cancel any in-flight warmup task and wait for it to finish."""
        task = self._task
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            if self._task is task:
                self._task = None

    def _build_targets(self) -> list[HeatmapWarmupTarget]:
        targets: list[HeatmapWarmupTarget] = []

        # Original targets (existing logic)
        for time_range in self._settings.heatmap_cache_warmup_time_ranges:
            max_points_variants = {
                resolve_max_points(zoom, None)
                for zoom in self._settings.heatmap_cache_warmup_zoom_levels
            }
            for max_points in sorted(max_points_variants):
                targets.append(
                    HeatmapWarmupTarget(
                        time_range=cast(TimeRangePreset, time_range),
                        transport_modes=None,
                        bucket_width_minutes=self._settings.heatmap_cache_warmup_bucket_width_minutes,
                        max_points=max_points,
                    )
                )

        # NEW: Add overview targets
        for time_range in self._settings.heatmap_cache_warmup_time_ranges:
            targets.append(
                HeatmapWarmupTarget(
                    time_range=cast(TimeRangePreset, time_range),
                    transport_modes=None,
                    bucket_width_minutes=self._settings.heatmap_cache_warmup_bucket_width_minutes,
                    max_points=0,  # 0 = overview mode
                    is_overview=True,  # New flag
                    metrics="both",
                )
            )

        return targets

    async def _warmup(self, *, reason: str) -> None:
        async with self._lock:
            if not self._settings.heatmap_cache_warmup_enabled:
                return

            targets = self._build_targets()
            ttl_seconds = self._settings.heatmap_cache_ttl_seconds
            stale_ttl_seconds = self._settings.heatmap_cache_stale_ttl_seconds

            started_at = time.monotonic()
            logger.info(
                "Heatmap cache warmup started (%s): %d variants",
                reason,
                len(targets),
            )

            try:
                async with AsyncSessionFactory() as session:
                    from app.services.gtfs_schedule import GTFSScheduleService

                    gtfs_schedule = GTFSScheduleService(session)
                    service = HeatmapService(
                        gtfs_schedule, self._cache, session=session
                    )

                    warmed = 0
                    for target in targets:
                        try:
                            if target.is_overview:
                                # Use overview method for overview targets
                                overview_result = await service.get_heatmap_overview(
                                    time_range=target.time_range,
                                    transport_modes=target.transport_modes,
                                    bucket_width_minutes=target.bucket_width_minutes,
                                    metrics=target.metrics,
                                )
                                await self._cache.set_json(
                                    target.cache_key,
                                    overview_result.model_dump(mode="json"),
                                    ttl_seconds=ttl_seconds,
                                    stale_ttl_seconds=stale_ttl_seconds,
                                )
                            else:
                                # Use regular method for regular targets
                                heatmap_result = await service.get_cancellation_heatmap(
                                    time_range=target.time_range,
                                    transport_modes=target.transport_modes,
                                    bucket_width_minutes=target.bucket_width_minutes,
                                    max_points=target.max_points,
                                )
                                await self._cache.set_json(
                                    target.cache_key,
                                    heatmap_result.model_dump(mode="json"),
                                    ttl_seconds=ttl_seconds,
                                    stale_ttl_seconds=stale_ttl_seconds,
                                )
                            warmed += 1
                        except Exception:
                            logger.exception(
                                "Heatmap cache warmup failed for key '%s'",
                                target.cache_key,
                            )

                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                logger.info(
                    "Heatmap cache warmup finished (%s): %d/%d variants in %dms",
                    reason,
                    warmed,
                    len(targets),
                    elapsed_ms,
                )
            except Exception:
                logger.exception("Heatmap cache warmup failed (%s)", reason)
