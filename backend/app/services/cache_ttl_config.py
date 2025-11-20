"""TTL configuration wrapper for cache components."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class TTLConfig:
    """Centralized TTL configuration with validation."""

    def __init__(self) -> None:
        settings = get_settings()

        self.valkey_cache_ttl = settings.valkey_cache_ttl_seconds
        self.valkey_cache_ttl_not_found = settings.valkey_cache_ttl_not_found_seconds
        self.mvg_departures_cache_ttl = settings.mvg_departures_cache_ttl_seconds
        self.mvg_departures_cache_stale_ttl = settings.mvg_departures_cache_stale_ttl_seconds
        self.mvg_station_search_cache_ttl = settings.mvg_station_search_cache_ttl_seconds
        self.mvg_station_search_cache_stale_ttl = settings.mvg_station_search_cache_stale_ttl_seconds
        self.mvg_station_list_cache_ttl = settings.mvg_station_list_cache_ttl_seconds
        self.mvg_station_list_cache_stale_ttl = settings.mvg_station_list_cache_stale_ttl_seconds
        self.mvg_route_cache_ttl = settings.mvg_route_cache_ttl_seconds
        self.mvg_route_cache_stale_ttl = settings.mvg_route_cache_stale_ttl_seconds

        self.singleflight_lock_ttl = settings.cache_singleflight_lock_ttl_seconds
        self.singleflight_lock_wait = settings.cache_singleflight_lock_wait_seconds
        self.singleflight_retry_delay = settings.cache_singleflight_retry_delay_seconds

        self.circuit_breaker_timeout = settings.cache_circuit_breaker_timeout_seconds

        self._validate_ttls()

    def _validate_ttls(self) -> None:
        """Validate that all TTL values are non-negative."""
        for attr_name, value in self.__dict__.items():
            if "ttl" in attr_name and isinstance(value, (int, float)) and value < 0:
                raise ValueError(f"TTL value for {attr_name} cannot be negative: {value}")

    def get_effective_ttl(self, ttl_seconds: int | None) -> int | None:
        """Get the effective TTL, using default if none provided."""
        if ttl_seconds is not None:
            return ttl_seconds if ttl_seconds > 0 else None
        return self.valkey_cache_ttl if self.valkey_cache_ttl > 0 else None

    def get_effective_stale_ttl(self, stale_ttl_seconds: int | None) -> int | None:
        """Get the effective stale TTL, using default if none provided."""
        if stale_ttl_seconds is not None:
            return stale_ttl_seconds if stale_ttl_seconds > 0 else None
        return None


__all__ = ["TTLConfig"]
