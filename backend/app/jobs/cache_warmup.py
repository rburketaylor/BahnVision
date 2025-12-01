"""
Cache warmup job for priming MVG-backed data stores.

Fetches the station catalog during startup so the first user
doesn't wait for the initial MVG sync.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.api.v1.endpoints.mvg.shared.cache_keys import departures_cache_key
from app.api.v1.shared.cache_flow import execute_cache_refresh
from app.api.v1.shared.mvg_protocols import (
    DeparturesRefreshProtocol,
    StationListRefreshProtocol,
)
from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionFactory
from app.persistence.repositories import StationRepository
from app.services.cache import CacheService, get_cache_service
from app.services.mvg_client import MVGClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WarmupSummary:
    """Aggregate cache warmup statistics."""

    stations_cached: int = 0
    departures_warmed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stations_cached": self.stations_cached,
            "departures_warmed": self.departures_warmed,
            "errors": self.errors,
        }


class CacheWarmupJob:
    """Hydrate cache layers so the first user avoids MVG cold-start latency."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cache: CacheService = get_cache_service()
        self.client = MVGClient(cache_service=self.cache)

    async def run(self) -> WarmupSummary:
        summary = WarmupSummary()

        try:
            summary.stations_cached = await self._warm_station_catalog()
            logger.info("Warmup cached %s stations", summary.stations_cached)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Station catalog warmup failed: %s", exc)
            summary.errors.append("station_catalog")

        if self.settings.cache_warmup_departure_stations:
            try:
                summary.departures_warmed = await self._warm_departure_caches()
                logger.info(
                    "Warmup hydrated %s departure cache keys",
                    summary.departures_warmed,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Departure warmup failed: %s", exc)
                summary.errors.append("departures")

        return summary

    async def _warm_station_catalog(self) -> int:
        """Fetch the full station catalog once to populate cache and persistence."""
        async with AsyncSessionFactory() as session:
            repository = StationRepository(session)
            protocol = StationListRefreshProtocol(
                client=self.client,
                cache=self.cache,
                station_repository=repository,
            )
            response = await execute_cache_refresh(
                protocol=protocol,
                cache=self.cache,
                cache_key="mvg:stations:all",
                settings=self.settings,
            )
            # Build the search index once so future requests reuse cached data
            # (the in-memory index will still be rebuilt inside the API process,
            # but this ensures MVG data is already stored in Valkey + Postgres).
            try:
                from app.api.v1.shared.station_search_index import (
                    CachedStationSearchIndex,
                )

                index = CachedStationSearchIndex(self.cache)
                await index.get_index(response.stations)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Search index warmup skipped: %s", exc)
            return len(response.stations)

    async def _warm_departure_caches(self) -> int:
        """Warm departure cache keys for frequently requested stations."""
        if not self.settings.cache_warmup_departure_stations:
            return 0

        warmed = 0
        protocol = DeparturesRefreshProtocol(
            client=self.client, filter_transport_types=None
        )
        for station in self.settings.cache_warmup_departure_stations:
            cache_key = departures_cache_key(
                station=station,
                limit=self.settings.cache_warmup_departure_limit,
                offset=self.settings.cache_warmup_departure_offset_minutes,
                transport_types=[],
            )
            try:
                await execute_cache_refresh(
                    protocol=protocol,
                    cache=self.cache,
                    cache_key=cache_key,
                    settings=self.settings,
                    station=station,
                    limit=self.settings.cache_warmup_departure_limit,
                    offset=self.settings.cache_warmup_departure_offset_minutes,
                )
                warmed += 1
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Failed to warm departures for %s: %s", station, exc)

        return warmed


async def run_cache_warmup() -> WarmupSummary:
    """Convenience helper for scripts/tests."""
    job = CacheWarmupJob()
    return await job.run()


def _configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _main() -> None:
    _configure_logging()
    summary = asyncio.run(run_cache_warmup())
    logger.info("Cache warmup completed: %s", json.dumps(summary.to_dict()))


if __name__ == "__main__":
    _main()
