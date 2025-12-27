"""
Tests for the HeatmapCacheWarmer job.

Tests the heatmap cache warmup functionality including target building,
trigger behavior, and warmup execution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.heatmap_cache_warmup import HeatmapCacheWarmer, HeatmapWarmupTarget


class TestHeatmapWarmupTarget:
    """Tests for HeatmapWarmupTarget dataclass."""

    def test_cache_key_property(self):
        """Test cache_key property returns correct key format."""
        target = HeatmapWarmupTarget(
            time_range="24h",
            transport_modes=None,
            bucket_width_minutes=60,
            max_points=1000,
        )

        key = target.cache_key

        assert key is not None
        assert "24h" in key
        assert "60" in key
        assert "1000" in key

    def test_cache_key_with_transport_modes(self):
        """Test cache_key includes transport modes when set."""
        target = HeatmapWarmupTarget(
            time_range="1h",
            transport_modes="UBAHN,SBAHN",
            bucket_width_minutes=30,
            max_points=100,
        )

        key = target.cache_key

        assert "1h" in key
        assert "SBAHN" in key
        assert "UBAHN" in key

    def test_cache_key_default_values(self):
        """Test cache_key with default transport_modes and max_points."""
        target = HeatmapWarmupTarget(
            time_range="7d",
            transport_modes=None,
            bucket_width_minutes=60,
            max_points=500,
        )

        key = target.cache_key

        assert "7d" in key
        # Should contain "all" or similar for default modes
        assert key is not None


class TestHeatmapCacheWarmer:
    """Tests for HeatmapCacheWarmer class."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache service."""
        cache = AsyncMock()
        cache.set_json = AsyncMock()
        return cache

    @pytest.fixture
    def mock_settings_enabled(self):
        """Create mock settings with warmup enabled."""
        settings = MagicMock()
        settings.heatmap_cache_warmup_enabled = True
        settings.heatmap_cache_warmup_time_ranges = ["1h", "24h"]
        settings.heatmap_cache_warmup_zoom_levels = [8, 10]
        settings.heatmap_cache_warmup_bucket_width_minutes = 60
        settings.heatmap_cache_ttl_seconds = 300
        return settings

    @pytest.fixture
    def mock_settings_disabled(self):
        """Create mock settings with warmup disabled."""
        settings = MagicMock()
        settings.heatmap_cache_warmup_enabled = False
        return settings

    def test_build_targets_creates_correct_combinations(
        self, mock_cache, mock_settings_enabled
    ):
        """Test _build_targets creates targets for all time/density combinations."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            warmer = HeatmapCacheWarmer(mock_cache)
            targets = warmer._build_targets()

        # 2 time ranges * 2 max_points densities = 4 targets
        assert len(targets) == 4

        # Verify all combinations exist
        time_ranges = {t.time_range for t in targets}
        max_points = {t.max_points for t in targets}

        assert time_ranges == {"1h", "24h"}
        assert max_points == {500, 1000}

    def test_build_targets_uses_settings_bucket_width(
        self, mock_cache, mock_settings_enabled
    ):
        """Test _build_targets uses bucket width from settings."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            warmer = HeatmapCacheWarmer(mock_cache)
            targets = warmer._build_targets()

        for target in targets:
            assert target.bucket_width_minutes == 60

    def test_trigger_skips_when_disabled(self, mock_cache, mock_settings_disabled):
        """Test trigger does nothing when warmup is disabled."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_disabled,
        ):
            warmer = HeatmapCacheWarmer(mock_cache)
            warmer.trigger(reason="test")

        assert warmer._task is None

    def test_trigger_skips_when_task_already_running(
        self, mock_cache, mock_settings_enabled
    ):
        """Test trigger skips when a warmup task is already in progress."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            warmer = HeatmapCacheWarmer(mock_cache)

            # Simulate a running task
            running_task = MagicMock()
            running_task.done.return_value = False
            warmer._task = running_task

            warmer.trigger(reason="second trigger")

            # Task should not be replaced
            assert warmer._task is running_task

    @pytest.mark.asyncio
    async def test_trigger_creates_task_when_enabled(
        self, mock_cache, mock_settings_enabled
    ):
        """Test trigger creates a task when warmup is enabled and no task running."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            with patch.object(HeatmapCacheWarmer, "_warmup", new_callable=AsyncMock):
                warmer = HeatmapCacheWarmer(mock_cache)
                warmer.trigger(reason="test")

                assert warmer._task is not None

    @pytest.mark.asyncio
    async def test_warmup_skips_when_disabled(self, mock_cache, mock_settings_disabled):
        """Test _warmup does nothing when warmup is disabled."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_disabled,
        ):
            warmer = HeatmapCacheWarmer(mock_cache)
            await warmer._warmup(reason="test")

        mock_cache.set_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_warmup_handles_service_exception(
        self, mock_cache, mock_settings_enabled
    ):
        """Test _warmup handles exceptions gracefully without crashing."""
        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            with patch(
                "app.jobs.heatmap_cache_warmup.AsyncSessionFactory"
            ) as mock_session_factory:
                # Make session factory raise an exception
                mock_session_factory.side_effect = RuntimeError("DB unavailable")

                warmer = HeatmapCacheWarmer(mock_cache)

                # Should not raise, just log the error - if this completes, the test passes
                await warmer._warmup(reason="test")

        # Verify no cache writes occurred due to the early failure
        mock_cache.set_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_warmup_caches_results(self, mock_cache, mock_settings_enabled):
        """Test _warmup caches results from heatmap service."""
        mock_heatmap_response = MagicMock()
        mock_heatmap_response.model_dump.return_value = {"data": "test"}

        mock_heatmap_service = MagicMock()
        mock_heatmap_service.get_cancellation_heatmap = AsyncMock(
            return_value=mock_heatmap_response
        )

        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            with patch(
                "app.jobs.heatmap_cache_warmup.AsyncSessionFactory"
            ) as mock_session_factory:
                mock_session = MagicMock()
                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)
                mock_session_factory.return_value = mock_session_cm

                with patch("app.services.gtfs_schedule.GTFSScheduleService"):
                    with patch(
                        "app.jobs.heatmap_cache_warmup.HeatmapService",
                        return_value=mock_heatmap_service,
                    ):
                        warmer = HeatmapCacheWarmer(mock_cache)
                        await warmer._warmup(reason="test")

        # Should have called set_json for each target
        assert mock_cache.set_json.call_count == 4  # 2 time ranges * 2 densities

    @pytest.mark.asyncio
    async def test_warmup_continues_on_individual_target_failure(
        self, mock_cache, mock_settings_enabled
    ):
        """Test _warmup continues processing when individual targets fail."""
        call_count = 0

        async def failing_on_first(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("First target failed")
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {"data": "test"}
            return mock_response

        mock_heatmap_service = MagicMock()
        mock_heatmap_service.get_cancellation_heatmap = failing_on_first

        with patch(
            "app.jobs.heatmap_cache_warmup.get_settings",
            return_value=mock_settings_enabled,
        ):
            with patch(
                "app.jobs.heatmap_cache_warmup.AsyncSessionFactory"
            ) as mock_session_factory:
                mock_session = MagicMock()
                mock_session_cm = MagicMock()
                mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session_cm.__aexit__ = AsyncMock(return_value=None)
                mock_session_factory.return_value = mock_session_cm

                with patch("app.services.gtfs_schedule.GTFSScheduleService"):
                    with patch(
                        "app.jobs.heatmap_cache_warmup.HeatmapService",
                        return_value=mock_heatmap_service,
                    ):
                        warmer = HeatmapCacheWarmer(mock_cache)
                        await warmer._warmup(reason="test")

        # Should have called set_json for 3 of 4 targets (first one failed)
        assert mock_cache.set_json.call_count == 3
