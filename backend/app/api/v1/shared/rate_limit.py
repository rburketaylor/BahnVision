"""Shared rate limiter for API endpoints.

This module provides a centralized rate limiter that can be imported by
endpoint routers to apply consistent rate limiting across the API.
"""

from typing import Callable, cast
from urllib.parse import urlparse

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# Type alias for default limits - slowapi expects list[str | Callable[..., str]]
LimitsType = list[str | Callable[..., str]]

# Create a module-level limiter instance that will be initialized on first import.
# The limiter uses the client's IP address as the rate limit key.
# Storage URI is configured from settings when the app starts.
_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    """Get or create the shared rate limiter instance.

    Returns a Limiter configured with the application's rate limit settings.
    Uses in-memory storage by default, but will use Valkey if configured.
    """
    global _limiter
    if _limiter is None:
        settings = get_settings()

        # Build default limits from settings
        # Cast to Any to satisfy mypy - slowapi expects list[str | Callable] but we only use strings
        default_limits: LimitsType = [
            f"{settings.rate_limit_requests_per_minute}/minute",
            f"{settings.rate_limit_requests_per_hour}/hour",
            f"{settings.rate_limit_requests_per_day}/day",
        ]

        if settings.rate_limit_enabled:
            try:
                # Only pass redis/valkey-specific connection options to redis backends.
                parsed = urlparse(settings.valkey_url)
                storage_options: dict[str, str] | None = None
                if parsed.scheme in {"valkey", "redis", "rediss"}:
                    storage_options = cast(
                        dict[str, str],
                        {
                            "socket_connect_timeout": settings.valkey_socket_connect_timeout_seconds,
                            "socket_timeout": settings.valkey_socket_timeout_seconds,
                        },
                    )

                if storage_options is None:
                    _limiter = Limiter(
                        key_func=get_remote_address,
                        storage_uri=settings.valkey_url,
                        default_limits=default_limits,
                    )
                else:
                    _limiter = Limiter(
                        key_func=get_remote_address,
                        storage_uri=settings.valkey_url,
                        default_limits=default_limits,
                        storage_options=storage_options,
                    )
            except Exception:
                # Fallback to in-memory if Valkey connection fails
                _limiter = Limiter(
                    key_func=get_remote_address,
                    default_limits=default_limits,
                )
        else:
            # Create a disabled limiter (no-op)
            _limiter = Limiter(
                key_func=get_remote_address,
                default_limits=default_limits,
                enabled=False,
            )

    return _limiter


# Export the limiter for use in endpoint decorators
limiter = get_limiter()
