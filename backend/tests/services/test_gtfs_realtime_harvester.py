"""
Tests for the GTFS-RT data harvester service (streaming aggregation).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.persistence.models import ScheduleRelationship
from app.services.gtfs_realtime_harvester import (
    DELAY_THRESHOLD_SECONDS,
    GTFSRTDataHarvester,
    ON_TIME_THRESHOLD_SECONDS,
    _TRIP_MARKER_TTL_SECONDS,
    _TRIP_MARKER_UPDATE_LUA,
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


class AtomicEvalClient:
    """Redis eval-compatible fake client for atomic marker updates."""

    def __init__(self, store: dict[str, str]):
        self._store = store
        self._lock = asyncio.Lock()

    async def eval(self, _script: str, numkeys: int, *keys_and_args):
        assert numkeys == 1
        key = keys_and_args[0]
        new_status = keys_and_args[1]
        new_delay = max(int(keys_and_args[2]), 0)
        _ttl = int(keys_and_args[3])
        rank = {"unknown": 0, "on_time": 1, "delayed": 2, "cancelled": 3}

        async with self._lock:
            prev_raw = self._store.get(key)
            prev_status: str | None = None
            prev_delay = 0

            if prev_raw is not None:
                if "|" in prev_raw:
                    status_raw, delay_raw = prev_raw.split("|", 1)
                    prev_status = status_raw if status_raw in rank else "unknown"
                    try:
                        prev_delay = max(int(delay_raw), 0)
                    except ValueError:
                        prev_delay = 0
                else:
                    prev_status = prev_raw if prev_raw in rank else "unknown"

            trip_delta = 0
            delay_delta = 0
            delayed_delta = 0
            on_time_delta = 0
            cancelled_delta = 0

            if prev_status is None:
                trip_delta = 1
                delay_delta = new_delay
                if new_status == "delayed":
                    delayed_delta = 1
                elif new_status == "on_time":
                    on_time_delta = 1
                elif new_status == "cancelled":
                    cancelled_delta = 1
                self._store[key] = f"{new_status}|{new_delay}"
                return [
                    trip_delta,
                    delay_delta,
                    delayed_delta,
                    on_time_delta,
                    cancelled_delta,
                ]

            prev_rank = rank.get(prev_status, 0)
            new_rank = rank.get(new_status, 0)
            is_uncancel = prev_status == "cancelled" and new_status != "cancelled"
            if new_rank > prev_rank or is_uncancel:
                if prev_status == "delayed":
                    delayed_delta -= 1
                elif prev_status == "on_time":
                    on_time_delta -= 1
                elif prev_status == "cancelled":
                    cancelled_delta -= 1

                if new_status == "delayed":
                    delayed_delta += 1
                elif new_status == "on_time":
                    on_time_delta += 1
                elif new_status == "cancelled":
                    cancelled_delta += 1

                delay_delta = max(new_delay - prev_delay, 0)
                self._store[key] = f"{new_status}|{new_delay}"
            elif prev_status != "cancelled" and new_delay > prev_delay:
                delay_delta = new_delay - prev_delay
                self._store[key] = f"{prev_status}|{new_delay}"

            return [
                trip_delta,
                delay_delta,
                delayed_delta,
                on_time_delta,
                cancelled_delta,
            ]


class AtomicCache(FakeCache):
    def __init__(self):
        super().__init__()
        self._client = AtomicEvalClient(self._store)


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
    async def test_harvest_once_checks_import_lock_once_per_cycle(self):
        """Import lock should be checked once per harvest cycle."""
        harvester = GTFSRTDataHarvester(cache_service=None)
        harvester._fetch_trip_updates = AsyncMock(return_value=[])
        harvester._check_import_lock = AsyncMock(return_value=False)
        harvester._cache_live_snapshot = AsyncMock()

        class DummySessionContext:
            async def __aenter__(self):
                return AsyncMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with (
            patch("app.services.gtfs_realtime_harvester.GTFS_RT_AVAILABLE", True),
            patch(
                "app.services.gtfs_realtime_harvester.AsyncSessionFactory",
                return_value=DummySessionContext(),
            ),
        ):
            count = await harvester.harvest_once()

        assert count == 0
        assert harvester._check_import_lock.await_count == 1

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
        """Test trip ID hashing produces consistent 24-char result."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        hash1 = harvester._hash_trip_id("test_trip_123")
        hash2 = harvester._hash_trip_id("test_trip_123")
        hash3 = harvester._hash_trip_id("different_trip")

        assert hash1 == hash2  # Consistent
        assert len(hash1) == 24  # 96-bit hex prefix
        assert hash1 != hash3  # Different trips have different hashes

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_reads_legacy_trip_marker_key(self):
        """Legacy marker keys should still prevent double-counting in-bucket."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_start.strftime("%Y%m%d%H")
        legacy_key = f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id_legacy('trip_1')}"
        cache._store[legacy_key] = "delayed|400"

        result = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )

        assert result["trip_count"] == 0
        assert result["total_delay_seconds"] == 0
        assert result["delayed"] == 0

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_writes_primary_and_legacy_marker_keys(self):
        """New writes should keep both marker-key formats in sync."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_start.strftime("%Y%m%d%H")
        primary_key = (
            f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id('trip_1')}"
        )
        legacy_key = f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id_legacy('trip_1')}"

        await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )

        assert cache._store[primary_key] == "delayed|400"
        assert cache._store[legacy_key] == "delayed|400"

    def test_lua_script_ttl_fallback_matches_python_constant(self):
        """Lua fallback TTL should stay aligned with Python source-of-truth."""
        assert f"or {_TRIP_MARKER_TTL_SECONDS}" in _TRIP_MARKER_UPDATE_LUA

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

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_tracks_delay_deltas_on_upgrade(self):
        """Delay totals should include delta when status is upgraded in-bucket."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        first = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )
        assert first["trip_count"] == 1
        assert first["total_delay_seconds"] == 400
        assert first["delayed"] == 1

        upgraded = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 700, "status": "cancelled"}},
        )
        assert upgraded["trip_count"] == 0
        assert upgraded["total_delay_seconds"] == 300
        assert upgraded["delayed"] == -1
        assert upgraded["cancelled"] == 1

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_allows_uncancel_transition(self):
        """Cancelled status should be reversible when feed indicates uncancelled."""
        cache = FakeCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        first = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 0, "status": "cancelled"}},
        )
        assert first["trip_count"] == 1
        assert first["cancelled"] == 1

        uncancelled = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )
        assert uncancelled["trip_count"] == 0
        assert uncancelled["cancelled"] == -1
        assert uncancelled["delayed"] == 1
        assert uncancelled["total_delay_seconds"] == 400

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_atomic_path_allows_uncancel_transition(self):
        """Atomic script path should match uncancel behavior of fallback path."""
        cache = AtomicCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 0, "status": "cancelled"}},
        )
        uncancelled = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )

        assert uncancelled["trip_count"] == 0
        assert uncancelled["cancelled"] == -1
        assert uncancelled["delayed"] == 1
        assert uncancelled["total_delay_seconds"] == 400

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_atomic_path_reads_legacy_trip_marker_key(self):
        """Atomic path should use legacy markers when they already exist."""
        cache = AtomicCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_start.strftime("%Y%m%d%H")
        legacy_key = f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id_legacy('trip_1')}"
        cache._store[legacy_key] = "delayed|400"

        result = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )

        assert result["trip_count"] == 0
        assert result["total_delay_seconds"] == 0
        assert result["delayed"] == 0

    @pytest.mark.asyncio
    async def test_aggregate_by_stop_allows_uncancelled_latest_status(self):
        """Latest non-cancelled update should clear prior cancelled state."""
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
                "departure_delay_seconds": 0,
                "schedule_relationship": ScheduleRelationship.CANCELED,
            },
            {
                "trip_id": "trip_1",
                "stop_id": "stop_A",
                "departure_delay_seconds": 450,
                "schedule_relationship": ScheduleRelationship.SCHEDULED,
            },
        ]

        result = await harvester._aggregate_by_stop(trip_updates, bucket_start)

        assert result["stop_A"]["cancelled"] == 0
        assert result["stop_A"]["delayed"] == 1
        assert result["stop_A"]["trip_count"] == 1

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_batch_failure_uses_single_key_fallback(self):
        """Batch cache failures should not count all trips as new."""

        class BatchFailCache(FakeCache):
            async def mget(self, keys: list[str]) -> dict[str, str | None]:
                raise RuntimeError("mget failed")

            async def mset(self, items: dict[str, str], ttl_seconds: int | None = None):
                raise RuntimeError("mset failed")

        cache = BatchFailCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_start.strftime("%Y%m%d%H")
        cache_key = (
            f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id('trip_1')}"
        )
        cache._store[cache_key] = "delayed|400"

        result = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )
        assert result["trip_count"] == 0
        assert result["delayed"] == 0
        assert result["cancelled"] == 0

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_mset_failure_does_not_double_count(self):
        """mset failure should not re-apply deltas from fallback counting."""

        class MsetFailCache(FakeCache):
            async def mset(self, items: dict[str, str], ttl_seconds: int | None = None):
                raise RuntimeError("mset failed")

        cache = MsetFailCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        bucket_key = bucket_start.strftime("%Y%m%d%H")
        cache_key = (
            f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id('trip_1')}"
        )

        result = await harvester._apply_trip_statuses(
            bucket_start=bucket_start,
            stop_id="stop_A",
            trip_statuses={"trip_1": {"delay": 400, "status": "delayed"}},
        )

        assert result["trip_count"] == 1
        assert result["total_delay_seconds"] == 400
        assert result["delayed"] == 1
        assert cache._store[cache_key] == "delayed|400"

    @pytest.mark.asyncio
    async def test_apply_trip_statuses_atomic_path_prevents_parallel_double_count(self):
        """Atomic cache updates should avoid TOCTOU double-counting."""
        cache = AtomicCache()
        harvester = GTFSRTDataHarvester(cache_service=cache)

        from datetime import datetime, timezone

        bucket_start = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        trip_statuses = {"trip_1": {"delay": 400, "status": "delayed"}}

        first, second = await asyncio.gather(
            harvester._apply_trip_statuses(bucket_start, "stop_A", trip_statuses),
            harvester._apply_trip_statuses(bucket_start, "stop_A", trip_statuses),
        )

        assert first["trip_count"] + second["trip_count"] == 1
        assert first["delayed"] + second["delayed"] == 1
        assert first["total_delay_seconds"] + second["total_delay_seconds"] == 400

        bucket_key = bucket_start.strftime("%Y%m%d%H")
        cache_key = (
            f"gtfs_rt_trip:{bucket_key}:stop_A:{harvester._hash_trip_id('trip_1')}"
        )
        assert cache._store[cache_key] == "delayed|400"


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

    def test_negative_delay_classified_as_on_time(self):
        """Early trips should be treated as on-time, not unknown."""
        harvester = GTFSRTDataHarvester(cache_service=None)
        assert harvester._classify_status(-90, cancelled=False) == "on_time"
