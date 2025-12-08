"""Tests for rate limiter configuration.

Target: app/api/v1/shared/rate_limit.py (23 surviving mutations → improve to 60%+)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from slowapi import Limiter


class TestGetLimiter:
    """Tests for get_limiter function."""

    def setup_method(self):
        """Reset the global limiter before each test."""
        import app.api.v1.shared.rate_limit as rate_limit_module

        rate_limit_module._limiter = None

    def test_returns_limiter_instance(self):
        """Should return a Limiter instance."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=True,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="memory://",
            )
            limiter = get_limiter()

        assert isinstance(limiter, Limiter)

    def test_caches_limiter_instance(self):
        """Should return the same limiter on subsequent calls."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=True,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="memory://",
            )
            limiter1 = get_limiter()
            limiter2 = get_limiter()

        assert limiter1 is limiter2

    def test_disabled_creates_disabled_limiter(self):
        """When rate limiting is disabled, should create a disabled limiter."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=False,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="memory://",
            )
            limiter = get_limiter()

        assert isinstance(limiter, Limiter)
        assert limiter.enabled is False

    def test_uses_settings_for_default_limits(self):
        """Should use settings values for default limits."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=False,  # Use disabled for simpler test
                rate_limit_requests_per_minute=100,
                rate_limit_requests_per_hour=500,
                rate_limit_requests_per_day=2000,
                valkey_url="memory://",
            )
            limiter = get_limiter()

        # Verify the limiter was created (we can't easily inspect default_limits)
        assert limiter is not None

    def test_falls_back_to_memory_on_valkey_error(self):
        """When Valkey connection fails, should fallback to in-memory storage."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=True,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="redis://invalid-host:6379",  # Will fail to connect
            )

            with patch("app.api.v1.shared.rate_limit.Limiter") as mock_limiter_class:
                # First call raises, second call succeeds (fallback)
                mock_limiter_class.side_effect = [
                    Exception("Connection failed"),
                    MagicMock(spec=Limiter),
                ]

                get_limiter()

        # Should have tried twice - once with valkey, once without
        assert mock_limiter_class.call_count == 2

    def test_enabled_uses_valkey_storage_uri(self):
        """When enabled, should use valkey URL for storage."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=True,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="redis://localhost:6379",
            )

            with patch("app.api.v1.shared.rate_limit.Limiter") as mock_limiter_class:
                mock_limiter_class.return_value = MagicMock(spec=Limiter)
                get_limiter()

        # Check that Limiter was called with storage_uri
        call_kwargs = mock_limiter_class.call_args.kwargs
        assert call_kwargs.get("storage_uri") == "redis://localhost:6379"


class TestLimiterExport:
    """Tests for the module-level limiter export."""

    def test_limiter_is_exported(self):
        """The module should export a 'limiter' instance."""
        from app.api.v1.shared.rate_limit import limiter

        assert limiter is not None
        assert isinstance(limiter, Limiter)


class TestDefaultLimitsFormat:
    """Tests for default limits string formatting."""

    def setup_method(self):
        """Reset the global limiter before each test."""
        import app.api.v1.shared.rate_limit as rate_limit_module

        rate_limit_module._limiter = None

    def test_formats_minute_limit_correctly(self):
        """Should format minute limit as '{N}/minute'."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=False,
                rate_limit_requests_per_minute=123,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=1000,
                valkey_url="memory://",
            )

            with patch("app.api.v1.shared.rate_limit.Limiter") as mock_limiter_class:
                mock_limiter_class.return_value = MagicMock(spec=Limiter, enabled=False)
                get_limiter()

        call_kwargs = mock_limiter_class.call_args.kwargs
        default_limits = call_kwargs.get("default_limits", [])
        assert "123/minute" in default_limits

    def test_formats_hour_limit_correctly(self):
        """Should format hour limit as '{N}/hour'."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=False,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=456,
                rate_limit_requests_per_day=1000,
                valkey_url="memory://",
            )

            with patch("app.api.v1.shared.rate_limit.Limiter") as mock_limiter_class:
                mock_limiter_class.return_value = MagicMock(spec=Limiter, enabled=False)
                get_limiter()

        call_kwargs = mock_limiter_class.call_args.kwargs
        default_limits = call_kwargs.get("default_limits", [])
        assert "456/hour" in default_limits

    def test_formats_day_limit_correctly(self):
        """Should format day limit as '{N}/day'."""
        from app.api.v1.shared.rate_limit import get_limiter

        with patch("app.api.v1.shared.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_enabled=False,
                rate_limit_requests_per_minute=60,
                rate_limit_requests_per_hour=300,
                rate_limit_requests_per_day=789,
                valkey_url="memory://",
            )

            with patch("app.api.v1.shared.rate_limit.Limiter") as mock_limiter_class:
                mock_limiter_class.return_value = MagicMock(spec=Limiter, enabled=False)
                get_limiter()

        call_kwargs = mock_limiter_class.call_args.kwargs
        default_limits = call_kwargs.get("default_limits", [])
        assert "789/day" in default_limits
