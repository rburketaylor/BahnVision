"""
Unit tests for GTFS Real-Time background processor.
"""

import pytest
from unittest.mock import AsyncMock, patch
import asyncio

from app.services.cache import CacheService
from app.jobs.rt_processor import GtfsRealtimeProcessor, gtfs_rt_lifespan_manager


@pytest.fixture
def mock_cache_service():
    """Create a mock cache service."""
    cache_service = AsyncMock(spec=CacheService)
    return cache_service


@pytest.fixture
def rt_processor(mock_cache_service):
    """Create RT processor with mocked dependencies."""
    with patch("app.jobs.rt_processor.get_settings") as mock_settings:
        mock_settings.return_value.gtfs_rt_enabled = True
        mock_settings.return_value.gtfs_rt_timeout_seconds = 10

        processor = GtfsRealtimeProcessor(mock_cache_service)
        return processor


class TestGtfsRealtimeProcessor:
    """Test GTFS-RT processor functionality."""

    @pytest.mark.asyncio
    async def test_start_when_enabled(self, rt_processor):
        """Test that processor starts when GTFS-RT is enabled."""
        await rt_processor.start()

        assert rt_processor._task is not None
        assert not rt_processor._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_start_when_disabled(self, mock_cache_service):
        """Test that processor doesn't start when GTFS-RT is disabled."""
        with patch("app.jobs.rt_processor.get_settings") as mock_settings:
            mock_settings.return_value.gtfs_rt_enabled = False

            processor = GtfsRealtimeProcessor(mock_cache_service)
            await processor.start()

            assert processor._task is None

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, rt_processor):
        """Test that stop cancels the background task."""
        await rt_processor.start()
        task = rt_processor._task

        await rt_processor.stop()

        assert rt_processor._task is None
        assert rt_processor._shutdown_event.is_set()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_processing_loop_success(self, rt_processor):
        """Test successful processing loop iteration."""
        # Mock GTFS service
        mock_gtfs_service = AsyncMock()
        mock_gtfs_service.fetch_and_process_feed.return_value = {
            "trip_updates": 1,
            "vehicle_positions": 1,
            "alerts": 1,
        }

        rt_processor.gtfs_service = mock_gtfs_service

        # Start loop
        loop_task = asyncio.create_task(rt_processor._processing_loop())

        # Give loop time to execute once, then stop it
        await asyncio.sleep(0.001)
        rt_processor._shutdown_event.set()

        # Wait for loop to finish
        await asyncio.wait_for(loop_task, timeout=0.1)

        # Verify fetch method was called
        mock_gtfs_service.fetch_and_process_feed.assert_called()

    @pytest.mark.asyncio
    async def test_processing_loop_handles_exceptions(self, rt_processor):
        """Test that processing loop handles exceptions gracefully."""
        # Mock GTFS service with failing method
        mock_gtfs_service = AsyncMock()
        mock_gtfs_service.fetch_and_process_feed.side_effect = Exception(
            "Network error"
        )

        rt_processor.gtfs_service = mock_gtfs_service

        # Start loop
        loop_task = asyncio.create_task(rt_processor._processing_loop())

        # Give loop time to execute once, then stop it
        await asyncio.sleep(0.001)
        rt_processor._shutdown_event.set()

        # Wait for loop to finish
        await asyncio.wait_for(loop_task, timeout=0.1)

        # Verify fetch method was still called despite exception
        mock_gtfs_service.fetch_and_process_feed.assert_called()

    @pytest.mark.asyncio
    async def test_processing_loop_handles_cancelled_error(self, rt_processor):
        """Test that processing loop handles CancelledError gracefully."""
        # Mock GTFS service
        mock_gtfs_service = AsyncMock()
        started = asyncio.Event()
        fetch_cancelled = asyncio.Event()

        async def _blocking_fetch():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                fetch_cancelled.set()
                raise

        mock_gtfs_service.fetch_and_process_feed.side_effect = _blocking_fetch

        rt_processor.gtfs_service = mock_gtfs_service

        # Start the loop and immediately cancel it
        loop_task = asyncio.create_task(rt_processor._processing_loop())

        # Ensure the loop actually entered fetch_and_process_feed.
        await asyncio.wait_for(started.wait(), timeout=0.1)
        loop_task.cancel()

        # _processing_loop should handle CancelledError internally and exit cleanly.
        await asyncio.wait_for(loop_task, timeout=0.1)

        assert fetch_cancelled.is_set()
        assert loop_task.done()
        assert not loop_task.cancelled()
        assert loop_task.exception() is None
        mock_gtfs_service.fetch_and_process_feed.assert_awaited_once()


class TestGtfsRtLifespanManager:
    """Test GTFS-RT lifespan manager."""

    @pytest.mark.asyncio
    async def test_lifespan_manager_context(self, mock_cache_service):
        """Test that lifespan manager properly starts and stops processor."""
        with patch("app.jobs.rt_processor.get_settings") as mock_settings:
            mock_settings.return_value.gtfs_rt_enabled = True
            mock_settings.return_value.gtfs_rt_timeout_seconds = 10

            async with gtfs_rt_lifespan_manager(mock_cache_service) as processor:
                assert processor is not None
                assert isinstance(processor, GtfsRealtimeProcessor)
                assert processor._task is not None

            # After context exit, task should be cleaned up
            # Note: In real scenario, the task would be cancelled and cleaned up

    @pytest.mark.asyncio
    async def test_lifespan_manager_when_disabled(self, mock_cache_service):
        """Test lifespan manager when GTFS-RT is disabled."""
        with patch("app.jobs.rt_processor.get_settings") as mock_settings:
            mock_settings.return_value.gtfs_rt_enabled = False

            async with gtfs_rt_lifespan_manager(mock_cache_service) as processor:
                assert processor is not None
                assert isinstance(processor, GtfsRealtimeProcessor)
                assert processor._task is None  # No task when disabled
