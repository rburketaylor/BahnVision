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
from app.services.heatmap_cache import heatmap_live_snapshot_cache_key


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

    async def set_json(
        self,
        key: str,
        value,
        ttl_seconds: int | None = None,
        stale_ttl_seconds: int | None = None,
    ):
        self._store[key] = value


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeRow:
    def __init__(self, stop_id, stop_name, stop_lat, stop_lon):
        self.stop_id = stop_id
        self.stop_name = stop_name
        self.stop_lat = stop_lat
        self.stop_lon = stop_lon


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
        assert stop_a["trip_count"] == 2
        assert stop_a["on_time"] == 1
        assert stop_a["delayed"] == 1
        assert stop_a["cancelled"] == 0

        # Check stop_B aggregation
        stop_b = result["stop_B"]
        assert stop_b["trip_count"] == 1
        assert stop_b["cancelled"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_by_stop_deduplicates_per_trip(self):
        """Test that a single trip with multiple stop_time_updates is counted once.

        This was a critical bug where delayed_count was massively inflated because
        each stop a trip visited was being counted separately.
        """
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        # Simulate trip_1 visiting stop_A with multiple updates (different delays)
        # This could happen if the feed is polled multiple times or the trip
        # reports delays at different stops along its route
        trip_updates = [
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "departure_delay_seconds": 100,  # Minor delay
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "departure_delay_seconds": 400,  # Later update shows more delay
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "departure_delay_seconds": 500,  # Even more delay
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
        ]

        result = await harvester._aggregate_by_stop(trip_updates, bucket_start)

        stop_a = result["stop_A"]
        # Only 1 unique trip
        assert stop_a["trip_count"] == 1
        # The trip should be counted ONCE as delayed (not 3 times!)
        assert stop_a["delayed"] == 1
        assert stop_a["on_time"] == 0
        assert stop_a["cancelled"] == 0

    def test_hash_trip_id(self):
        """Test trip ID hashing produces consistent 12-char result."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        hash1 = harvester._hash_trip_id("test_trip_123")
        hash2 = harvester._hash_trip_id("test_trip_123")
        hash3 = harvester._hash_trip_id("different_trip")

        assert hash1 == hash2  # Consistent
        assert len(hash1) == 12  # 12 chars
        assert hash1 != hash3  # Different trips have different hashes

    @pytest.mark.asyncio
    async def test_cache_live_snapshot_writes_impacted_only(self):
        """Test that live snapshot caches impacted stations only."""
        cache = AsyncMock()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        trip_updates = [
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "route_id": "route_1",
                "departure_delay_seconds": 400,
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
            {
                "trip_id": "trip_2",
                "stop_id": "stop_B",
                "route_id": "route_1",
                "departure_delay_seconds": 0,
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
        ]
        route_type_map = {"route_1": 1}
        snapshot_stats = harvester._aggregate_snapshot_by_stop_and_route(
            trip_updates, route_type_map
        )
        snapshot_timestamp = datetime.now(timezone.utc)

        session = AsyncMock()
        session.execute.return_value = FakeResult(
            [
                FakeRow("stop_A", "Stop A", 48.1, 11.5),
                FakeRow("stop_B", "Stop B", 48.2, 11.6),
            ]
        )

        await harvester._cache_live_snapshot(
            session, snapshot_stats, snapshot_timestamp
        )

        cache.set_json.assert_called_once()
        called_key = cache.set_json.call_args[0][0]
        called_payload = cache.set_json.call_args[0][1]
        assert called_key == heatmap_live_snapshot_cache_key()
        assert len(called_payload["data_points"]) == 1


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
