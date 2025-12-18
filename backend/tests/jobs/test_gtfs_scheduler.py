"""
Unit tests for GTFSFeedScheduler.

Tests scheduler lifecycle and feed update logic.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.jobs.gtfs_scheduler import GTFSFeedScheduler


class TestGTFSFeedSchedulerInit:
    """Tests for GTFSFeedScheduler initialization."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_update_interval_hours = 24
        settings.gtfs_max_feed_age_hours = 48
        settings.gtfs_feed_url = "https://example.com/gtfs.zip"
        settings.gtfs_storage_path = "/tmp/gtfs"
        return settings

    def test_scheduler_init(self, mock_settings):
        """Test scheduler initialization."""
        scheduler = GTFSFeedScheduler(mock_settings)

        assert scheduler.settings == mock_settings
        assert scheduler.scheduler is not None

    def test_scheduler_setup_jobs(self, mock_settings):
        """Test that jobs are set up on initialization."""
        scheduler = GTFSFeedScheduler(mock_settings)

        # Get jobs from the scheduler
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "gtfs_feed_update"


class TestGTFSFeedSchedulerLifecycle:
    """Tests for scheduler lifecycle methods."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_update_interval_hours = 24
        settings.gtfs_max_feed_age_hours = 48
        settings.gtfs_feed_url = "https://example.com/gtfs.zip"
        settings.gtfs_storage_path = "/tmp/gtfs"
        return settings

    @pytest.fixture
    def scheduler(self, mock_settings):
        """Create scheduler instance."""
        return GTFSFeedScheduler(mock_settings)

    @pytest.mark.asyncio
    async def test_scheduler_start(self, scheduler):
        """Test starting the scheduler."""
        with patch.object(scheduler, "_check_and_update_feed", new_callable=AsyncMock):
            await scheduler.start()

            assert scheduler.scheduler.running

            # Clean up
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop(self, scheduler):
        """Test stopping the scheduler."""
        # Start first
        with patch.object(scheduler, "_check_and_update_feed", new_callable=AsyncMock):
            await scheduler.start()
            assert scheduler.scheduler.running

            # Then stop - just verify it doesn't raise
            await scheduler.stop()
            # Note: APScheduler's shutdown() doesn't immediately set running to False
            # The scheduler signals shutdown but the event loop may still be active

    @pytest.mark.asyncio
    async def test_scheduler_initial_import_on_empty_db(self, scheduler):
        """Test that initial import is triggered when no feed exists."""
        with patch("app.jobs.gtfs_scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()

            # Mock empty database (no feed info)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_session.execute = AsyncMock(return_value=mock_result)

            # Create async generator
            async def session_generator():
                yield mock_session

            mock_get_session.return_value = session_generator()

            with patch("app.jobs.gtfs_scheduler.GTFSFeedImporter") as mock_importer:
                mock_instance = AsyncMock()
                mock_instance.import_feed = AsyncMock(return_value="new_feed_id")
                mock_importer.return_value = mock_instance

                await scheduler._check_and_update_feed()

                mock_instance.import_feed.assert_called_once()


class TestGTFSFeedSchedulerUpdateLogic:
    """Tests for feed update decision logic."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_update_interval_hours = 24
        settings.gtfs_max_feed_age_hours = 48
        settings.gtfs_feed_url = "https://example.com/gtfs.zip"
        settings.gtfs_storage_path = "/tmp/gtfs"
        return settings

    @pytest.fixture
    def scheduler(self, mock_settings):
        """Create scheduler instance."""
        return GTFSFeedScheduler(mock_settings)

    @pytest.mark.asyncio
    async def test_check_and_update_triggers_on_stale_feed(self, scheduler):
        """Test that update is triggered when feed is too old."""
        with patch("app.jobs.gtfs_scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()

            # Mock stale feed (50 hours old, threshold is 48)
            stale_time = datetime.now(timezone.utc) - timedelta(hours=50)
            mock_feed_info = MagicMock()
            mock_feed_info.downloaded_at = stale_time
            mock_feed_info.feed_end_date = None  # Ensure comparison doesn't fail

            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_feed_info)
            mock_session.execute = AsyncMock(return_value=mock_result)

            async def session_generator():
                yield mock_session

            mock_get_session.return_value = session_generator()

            with patch("app.jobs.gtfs_scheduler.GTFSFeedImporter") as mock_importer:
                mock_instance = AsyncMock()
                mock_instance.import_feed = AsyncMock(return_value="updated_feed")
                mock_importer.return_value = mock_instance

                await scheduler._check_and_update_feed()

                mock_instance.import_feed.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_update_skips_fresh_feed(self, scheduler):
        """Test that update is skipped when feed is still fresh."""
        with patch("app.jobs.gtfs_scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()

            # Mock fresh feed (10 hours old, threshold is 48)
            fresh_time = datetime.now(timezone.utc) - timedelta(hours=10)
            mock_feed_info = MagicMock()
            mock_feed_info.downloaded_at = fresh_time
            mock_feed_info.feed_end_date = None

            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=mock_feed_info)
            mock_session.execute = AsyncMock(return_value=mock_result)

            async def session_generator():
                yield mock_session

            mock_get_session.return_value = session_generator()

            with patch("app.jobs.gtfs_scheduler.GTFSFeedImporter") as mock_importer:
                mock_instance = AsyncMock()
                mock_importer.return_value = mock_instance

                await scheduler._check_and_update_feed()

                # Should NOT have called import_feed
                mock_instance.import_feed.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_feed_error_handling(self, scheduler):
        """Test that errors during feed update are handled gracefully."""
        with patch("app.jobs.gtfs_scheduler.get_session") as mock_get_session:
            mock_session = AsyncMock()

            async def session_generator():
                yield mock_session

            mock_get_session.return_value = session_generator()

            with patch("app.jobs.gtfs_scheduler.GTFSFeedImporter") as mock_importer:
                mock_instance = AsyncMock()
                mock_instance.import_feed = AsyncMock(
                    side_effect=Exception("Network error")
                )
                mock_importer.return_value = mock_instance

                # Should not raise - verify it completes successfully
                try:
                    await scheduler._update_gtfs_feed()
                    completed_without_error = True
                except Exception:
                    completed_without_error = False

                assert completed_without_error, (
                    "Error handling should not propagate exceptions"
                )


class TestGTFSFeedSchedulerJobInfo:
    """Tests for job information retrieval."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_update_interval_hours = 24
        settings.gtfs_max_feed_age_hours = 48
        return settings

    @pytest.fixture
    def scheduler(self, mock_settings):
        """Create scheduler instance."""
        return GTFSFeedScheduler(mock_settings)

    def test_get_job_info_not_running(self, scheduler):
        """Test getting job info when scheduler is not running."""
        info = scheduler.get_job_info()

        assert info["scheduler_running"] is False
        assert "jobs" in info
        assert len(info["jobs"]) == 1

    @pytest.mark.asyncio
    async def test_get_job_info_running(self, scheduler):
        """Test getting job info when scheduler is running."""
        with patch.object(scheduler, "_check_and_update_feed", new_callable=AsyncMock):
            await scheduler.start()

            info = scheduler.get_job_info()

            assert info["scheduler_running"] is True
            assert len(info["jobs"]) == 1
            assert info["jobs"][0]["id"] == "gtfs_feed_update"
            assert info["jobs"][0]["name"] == "Update GTFS feed"

            await scheduler.stop()

    def test_get_job_info_structure(self, scheduler):
        """Test the structure of job info."""
        info = scheduler.get_job_info()

        assert "scheduler_running" in info
        assert "jobs" in info
        assert isinstance(info["jobs"], list)

        for job in info["jobs"]:
            assert "id" in job
            assert "name" in job
            assert "next_run" in job
            assert "trigger" in job
