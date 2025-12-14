"""
Tests for the GTFS-RT data harvester service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.persistence.models import ScheduleRelationship
from app.services.gtfs_realtime_harvester import GTFSRTDataHarvester


class FakeCache:
    """Fake cache for testing."""

    async def get(self, key: str):
        return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None):
        pass


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
    async def test_harvest_once_no_gtfs_rt(self):
        """Test harvest when GTFS-RT bindings not available."""
        harvester = GTFSRTDataHarvester(cache_service=None)

        # Patch GTFS_RT_AVAILABLE to False
        with patch("app.services.gtfs_realtime_harvester.GTFS_RT_AVAILABLE", False):
            count = await harvester.harvest_once()
            assert count == 0


class TestScheduleRelationshipMapping:
    """Test schedule relationship enum values."""

    def test_enum_values(self):
        """Test that ScheduleRelationship enum has expected values."""
        assert ScheduleRelationship.SCHEDULED.value == "SCHEDULED"
        assert ScheduleRelationship.SKIPPED.value == "SKIPPED"
        assert ScheduleRelationship.NO_DATA.value == "NO_DATA"
        assert ScheduleRelationship.UNSCHEDULED.value == "UNSCHEDULED"
        assert ScheduleRelationship.CANCELED.value == "CANCELED"
