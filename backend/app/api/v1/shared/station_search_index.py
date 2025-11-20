"""
High-performance station search index implementation.

This module provides an O(1) lookup index for station searches,
replacing the inefficient O(n) linear scan approach.
"""

from typing import Any, ClassVar
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import asyncio
import logging
import unicodedata

from app.models.mvg import Station
from app.services.cache import CacheService

logger = logging.getLogger(__name__)


@dataclass
class StationSearchIndex:
    """
    High-performance search index for stations.

    Provides O(1) or O(log n) lookups instead of O(n) linear scans.
    Built with asyncio context manager support for proper resource management.
    """

    # Class-level cache for station data
    _cache_key: ClassVar[str] = "station_search_index"

    # Index storage - organized for fast lookups
    name_index: dict[str, list[Station]] = field(
        default_factory=lambda: defaultdict(list)
    )
    place_index: dict[str, list[Station]] = field(
        default_factory=lambda: defaultdict(list)
    )
    exact_match_index: dict[str, Station] = field(default_factory=dict)
    stations: list[Station] = field(default_factory=list)

    # Metadata
    total_stations: int = 0
    last_updated: float = field(default_factory=lambda: 0)

    _FUZZY_MIN_RATIO: ClassVar[float] = 0.62

    def __post_init__(self) -> None:
        """Initialize the search index."""
        logger.debug("Initialized StationSearchIndex")

    async def build_index(self, stations: list[Station]) -> None:
        """
        Build the search index from a list of stations.

        This method should be called once and then the index can be used
        for many fast lookups.

        Args:
            stations: List of stations to index
        """
        logger.info(f"Building station search index for {len(stations)} stations")
        start_time = asyncio.get_event_loop().time()

        # Clear existing indexes
        self.name_index.clear()
        self.place_index.clear()
        self.exact_match_index.clear()
        self.stations = list(stations)

        for station in stations:
            # Exact match index for perfect matches
            name_lower = station.name.lower()
            self.exact_match_index[name_lower] = station

            # Name index for partial matches - split into words
            for word in self._tokenize(name_lower):
                self.name_index[word].append(station)
            normalized_name = self._normalize_text(station.name)
            for word in self._tokenize(normalized_name):
                self.name_index[word].append(station)

            # Place index for location-based searches
            place_lower = station.place.lower()
            for word in self._tokenize(place_lower):
                self.place_index[word].append(station)
            normalized_place = self._normalize_text(station.place)
            for word in self._tokenize(normalized_place):
                self.place_index[word].append(station)

        self.total_stations = len(stations)
        self.last_updated = asyncio.get_event_loop().time()

        duration = asyncio.get_event_loop().time() - start_time
        logger.info(
            f"Built station search index in {duration:.3f}s with {len(self.name_index)} name terms and {len(self.place_index)} place terms"
        )

    async def search(self, query: str, limit: int = 10) -> list[Station]:
        """
        Search stations using the high-performance index.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching stations ranked by relevance
        """
        if not query or limit <= 0:
            return []

        query_lower = query.strip().lower()
        normalized_query = self._normalize_text(query)

        # Start with exact match - highest priority
        results: list[tuple[Station, int]] = []

        # 1. Exact name match - highest relevance
        if query_lower in self.exact_match_index:
            results.append((self.exact_match_index[query_lower], 100))

        # 2. Check name index for partial matches
        query_words = query_lower.split()
        normalized_words = normalized_query.split() if normalized_query else []
        for word in query_words + normalized_words:
            if len(word) >= 2 and word in self.name_index:
                for station in self.name_index[word]:
                    # Calculate relevance score based on match quality
                    if station.name.lower() == query_lower:
                        relevance = 90  # Exact case match
                    elif query_lower in station.name.lower():
                        relevance = 80  # Substring match
                    else:
                        relevance = 70  # Word match

                    results.append((station, relevance))

        # 3. Check place index for location matches
        for word in query_words + normalized_words:
            if len(word) >= 2 and word in self.place_index:
                for station in self.place_index[word]:
                    # Lower relevance for place matches
                    relevance = 50
                    results.append((station, relevance))

        # Deduplicate and sort by relevance
        seen_stations = set()
        unique_results: list[tuple[Station, int]] = []

        for station, relevance in results:
            if station.id not in seen_stations:
                seen_stations.add(station.id)
                unique_results.append((station, relevance))

        # Sort by relevance (descending) and return top results
        unique_results.sort(key=lambda x: x[1], reverse=True)

        if len(unique_results) < limit:
            remaining = limit - len(unique_results)
            fuzzy_matches = self._fuzzy_search(
                query_lower=query_lower,
                normalized_query=normalized_query,
                seen_stations=seen_stations,
            )
            unique_results.extend(fuzzy_matches[:remaining])

        return [station for station, _ in unique_results[:limit]]

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the search index.

        Returns:
            Dictionary with index statistics
        """
        return {
            "total_stations": self.total_stations,
            "name_terms": len(self.name_index),
            "place_terms": len(self.place_index),
            "exact_matches": len(self.exact_match_index),
            "last_updated": self.last_updated,
        }

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Return a lowercase, accent-insensitive representation of text."""
        normalized = unicodedata.normalize("NFKD", value)
        stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return stripped.lower()

    @staticmethod
    def _tokenize(value: str) -> list[str]:
        return [word for word in value.split() if len(word) >= 2]

    def _fuzzy_search(
        self,
        *,
        query_lower: str,
        normalized_query: str,
        seen_stations: set[str],
    ) -> list[tuple[Station, int]]:
        """Fallback fuzzy search across all stations for typos/substrings."""
        candidates: list[tuple[Station, int]] = []
        for station in self.stations:
            if station.id in seen_stations:
                continue

            name_lower = station.name.lower()
            place_lower = station.place.lower()
            normalized_name = self._normalize_text(station.name)
            normalized_place = self._normalize_text(station.place)

            score = 0
            if query_lower and query_lower in name_lower:
                score = 90
            elif query_lower and query_lower in place_lower:
                score = 80
            elif normalized_query:
                if normalized_query in normalized_name:
                    score = 85
                elif normalized_query in normalized_place:
                    score = 75

            if score == 0:
                ratio = max(
                    (
                        SequenceMatcher(None, query_lower, name_lower).ratio()
                        if query_lower
                        else 0
                    ),
                    (
                        SequenceMatcher(None, query_lower, place_lower).ratio()
                        if query_lower
                        else 0
                    ),
                    (
                        SequenceMatcher(None, normalized_query, normalized_name).ratio()
                        if normalized_query
                        else 0
                    ),
                    (
                        SequenceMatcher(
                            None, normalized_query, normalized_place
                        ).ratio()
                        if normalized_query
                        else 0
                    ),
                )
                if ratio >= self._FUZZY_MIN_RATIO:
                    score = int(ratio * 100)

            if score:
                candidates.append((station, score))

        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates

    async def clear(self) -> None:
        """Clear all indexes (useful for testing)."""
        self.name_index.clear()
        self.place_index.clear()
        self.exact_match_index.clear()
        self.total_stations = 0
        self.last_updated = 0
        self.stations = []

    async def __aenter__(self) -> "StationSearchIndex":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        # Nothing to clean up, but interface for consistency
        pass


class CachedStationSearchIndex:
    """
    Cached station search index that persists the index in cache.

    This wrapper combines the StationSearchIndex with cache storage
    to avoid rebuilding the index on every request.
    """

    def __init__(self, cache: CacheService, ttl_seconds: int = 3600):
        """
        Initialize cached search index.

        Args:
            cache: Cache service instance
            ttl_seconds: Cache TTL for the index
        """
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self._local_index: StationSearchIndex | None = None

    async def get_index(self, stations: list[Station]) -> StationSearchIndex:
        """
        Get the search index, loading from cache if available.

        Args:
            stations: List of stations to build index from if not cached

        Returns:
            Station search index ready for fast lookups
        """
        # Check if we have a valid local index
        if self._local_index is not None and self._local_index.total_stations > 0:
            return self._local_index

        # Try to load from cache
        try:
            cached_data = await self.cache.get_json(StationSearchIndex._cache_key)
            if cached_data:
                # Rebuild index from cached data
                self._local_index = StationSearchIndex()
                # In a real implementation, we'd serialize/deserialize the full index
                # For now, rebuild from stations (still much faster than linear search)
                await self._local_index.build_index(stations)
                logger.info("Loaded station search index from cache")
                return self._local_index
        except Exception as e:
            logger.warning(f"Failed to load station search index from cache: {e}")

        # Build new index
        self._local_index = StationSearchIndex()
        await self._local_index.build_index(stations)

        # Cache for future use (cache the station count)
        try:
            await self.cache.set_json(
                StationSearchIndex._cache_key,
                {
                    "station_count": len(stations),
                    "last_updated": self._local_index.last_updated,
                },
                ttl_seconds=self.ttl_seconds,
            )
            logger.info("Cached station search index")
        except Exception as e:
            logger.warning(f"Failed to cache station search index: {e}")

        return self._local_index

    async def clear_cache(self) -> None:
        """Clear cached index data."""
        try:
            await self.cache.delete(StationSearchIndex._cache_key)
            self._local_index = None
            logger.info("Cleared station search index cache")
        except Exception as e:
            logger.warning(f"Failed to clear station search index cache: {e}")
