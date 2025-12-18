"""
Tests for the GTFS-RT data harvester service (streaming aggregation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.persistence.models import ScheduleRelationship
from app.services.gtfs_realtime_harvester import (
    DELAY_THRESHOLD_SECONDS,
    GTFSRTDataHarvester,
    ON_TIME_THRESHOLD_SECONDS,
)


class FakeCache:
    """Fake cache for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None):
        self._store[key] = value

    async def mget(self, keys: list[str]) -> dict[str, str | None]:
        """Batch get multiple keys."""
        return {key: self._store.get(key) for key in keys}

    async def mset(self, items: dict[str, str], ttl_seconds: int | None = None):
        """Batch set multiple key-value pairs."""
        self._store.update(items)


class TestGTFSRTDataHarvester:
    """Tests for GTFSRTDataHarvester."""

    def test_init(self):
        """Test harvester initialization."""
        harvester = GTFSRTDataHarvester(cache_service=None)
        assert harvester._running is False
        assert harvester._task is None

    def test_init_with_custom_interval(self):
        """Test harvester initialization with custom interval."""
        harvester = GTFSRTDataHarvester(
            cache_service=None, harvest_interval_seconds=120
        )
        assert harvester._harvest_interval == 120

    def test_init_default_interval(self):
        """Test that default interval is 300 seconds (5 minutes)."""
        harvester = GTFSRTDataHarvester(cache_service=None)
        assert harvester._harvest_interval == 300

    def test_map_schedule_relationship(self):
        """Test schedule relationship mapping."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        assert harvester._map_schedule_relationship(0) == ScheduleRelationship.SCHEDULED
        assert harvester._map_schedule_relationship(1) == ScheduleRelationship.SKIPPED
        assert harvester._map_schedule_relationship(2) == ScheduleRelationship.NO_DATA
        assert (
            harvester._map_schedule_relationship(3) == ScheduleRelationship.UNSCHEDULED
        )
        # Unknown value should default to SCHEDULED
        assert (
            harvester._map_schedule_relationship(99) == ScheduleRelationship.SCHEDULED
        )

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test harvester start and stop."""
        harvester = GTFSRTDataHarvester(cache_service=None, harvest_interval_seconds=1)

        # Mock the harvest_once to avoid actual network calls
        harvester.harvest_once = AsyncMock(return_value=0)

        await harvester.start()
        assert harvester._running is True
        assert harvester._task is not None

        await harvester.stop()
        assert harvester._running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test that starting twice warns and returns early."""
        harvester = GTFSRTDataHarvester(cache_service=None, harvest_interval_seconds=1)
        harvester.harvest_once = AsyncMock(return_value=0)

        await harvester.start()
        original_task = harvester._task

        # Second start should warn and return early
        await harvester.start()

        # Verify the original task is still the same (no new task created)
        assert harvester._task is original_task, (
            "Starting twice should not create a new task"
        )
        assert harvester._running is True, "Harvester should still be running"

        await harvester.stop()

    @pytest.mark.asyncio
    async def test_harvest_once_no_gtfs_rt(self):
        """Test harvest when GTFS-RT bindings not available."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        # Patch GTFS_RT_AVAILABLE to False
        with patch("app.services.gtfs_realtime_harvester.GTFS_RT_AVAILABLE", False):
            count = await harvester.harvest_once()
            assert count == 0

    @pytest.mark.asyncio
    async def test_aggregate_by_stop(self):
        """Test aggregation of trip updates by stop."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        trip_updates = [
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "departure_delay_seconds": 30,  # On time
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
            {
                "trip_id": "trip_2",
                "stop_id": "stop_A",
                "departure_delay_seconds": 400,  # Delayed
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
            {
                "trip_id": "trip_3",
                "stop_id": "stop_B",
                "departure_delay_seconds": None,  # Cancelled
                "schedule_relationship": ScheduleRelationship.CANCELED,
            },
        ]

        result = await harvester._aggregate_by_stop(trip_updates, bucket_start)

        assert "stop_A" in result
        assert "stop_B" in result

        # Check stop_A aggregation
        stop_a = result["stop_A"]
        assert len(stop_a["trips"]) == 2
        assert stop_a["on_time"] == 1
        assert stop_a["delayed"] == 1
        assert stop_a["cancelled"] == 0

        # Check stop_B aggregation
        stop_b = result["stop_B"]
        assert len(stop_b["trips"]) == 1
        assert stop_b["cancelled"] == 1

    @pytest.mark.asyncio
    async def test_count_new_trips_without_cache(self):
        """Test trip counting without cache - all trips counted as new."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc)
        trip_ids = {"trip_1", "trip_2", "trip_3"}

        count = await harvester._count_new_trips(bucket_start, "stop_A", trip_ids)
        assert count == 3  # All trips counted as new without cache

    @pytest.mark.asyncio
    async def test_count_new_trips_with_cache(self):
        """Test trip counting with cache - deduplication works."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc)
        trip_ids = {"trip_1", "trip_2"}

        # First call - all trips are new
        count1 = await harvester._count_new_trips(bucket_start, "stop_A", trip_ids)
        assert count1 == 2

        # Second call with same trips - all should be seen
        count2 = await harvester._count_new_trips(bucket_start, "stop_A", trip_ids)
        assert count2 == 0

        # Third call with one new trip
        count3 = await harvester._count_new_trips(
            bucket_start, "stop_A", {"trip_1", "trip_3"}
        )
        assert count3 == 1  # Only trip_3 is new

    def test_hash_trip_id(self):
        """Test trip ID hashing produces consistent 12-char result."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        hash1 = harvester._hash_trip_id("test_trip_123")
        hash2 = harvester._hash_trip_id("test_trip_123")
        hash3 = harvester._hash_trip_id("different_trip")

        assert hash1 == hash2  # Consistent
        assert len(hash1) == 12  # 12 chars
        assert hash1 != hash3  # Different trips have different hashes


class TestScheduleRelationshipMapping:
    """Test schedule relationship enum values."""

    def test_enum_values(self):
        """Test that ScheduleRelationship enum has expected values."""
        assert ScheduleRelationship.SCHEDULED.value == "SCHEDULED"
        assert ScheduleRelationship.SKIPPED.value == "SKIPPED"
        assert ScheduleRelationship.NO_DATA.value == "NO_DATA"
        assert ScheduleRelationship.UNSCHEDULED.value == "UNSCHEDULED"
        assert ScheduleRelationship.CANCELED.value == "CANCELED"


class TestDelayThresholds:
    """Test delay threshold constants."""

    def test_delay_thresholds(self):
        """Test that delay thresholds match expected values."""
        assert DELAY_THRESHOLD_SECONDS == 300  # 5 minutes
        assert ON_TIME_THRESHOLD_SECONDS == 60  # 1 minute
