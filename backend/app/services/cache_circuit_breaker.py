"""Circuit breaker helper for cache operations."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from app.services.cache_ttl_config import TTLConfig

logger = logging.getLogger(__name__)
T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker decorator pattern."""

    def __init__(self, config: TTLConfig) -> None:
        self._config = config
        self._open_until = 0.0

    def is_open(self) -> bool:
        """Check if the circuit breaker is currently open."""
        return time.monotonic() < self._open_until

    def open(self) -> None:
        """Open the circuit breaker for the configured timeout."""
        self._open_until = time.monotonic() + self._config.circuit_breaker_timeout

    def close(self) -> None:
        """Close the circuit breaker immediately."""
        self._open_until = 0.0

    def protect(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to protect a function from circuit breaker failures."""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open():
                return None
            try:
                result = await func(*args, **kwargs)
                self.close()
                return result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Cache circuit breaker opened for %s", func.__name__, exc_info=exc
                )
                self.open()
                return None

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open():
                return None
            try:
                result = func(*args, **kwargs)
                self.close()
                return result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Cache circuit breaker opened for %s", func.__name__, exc_info=exc
                )
                self.open()
                return None

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


__all__ = ["CircuitBreaker"]
