from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration sourced from environment variables."""

    valkey_url: str = Field(
        "valkey://localhost:6379/0",
        alias="VALKEY_URL",
        validation_alias=AliasChoices("VALKEY_URL", "REDIS_URL"),
    )
    valkey_cache_ttl_seconds: int = Field(
        30,
        alias="VALKEY_CACHE_TTL_SECONDS",
        validation_alias=AliasChoices(
            "VALKEY_CACHE_TTL_SECONDS", "REDIS_CACHE_TTL_SECONDS"
        ),
    )
    valkey_cache_ttl_not_found_seconds: int = Field(
        15,
        alias="VALKEY_CACHE_TTL_NOT_FOUND_SECONDS",
        validation_alias=AliasChoices(
            "VALKEY_CACHE_TTL_NOT_FOUND_SECONDS",
            "REDIS_CACHE_TTL_NOT_FOUND_SECONDS",
        ),
    )
    mvg_departures_cache_ttl_seconds: int = Field(
        30,
        alias="MVG_DEPARTURES_CACHE_TTL_SECONDS",
    )
    mvg_departures_cache_stale_ttl_seconds: int = Field(
        300,
        alias="MVG_DEPARTURES_CACHE_STALE_TTL_SECONDS",
    )
    mvg_station_search_cache_ttl_seconds: int = Field(
        60,
        alias="MVG_STATION_SEARCH_CACHE_TTL_SECONDS",
    )
    mvg_station_search_cache_stale_ttl_seconds: int = Field(
        600,
        alias="MVG_STATION_SEARCH_CACHE_STALE_TTL_SECONDS",
    )
    mvg_route_cache_ttl_seconds: int = Field(
        120,
        alias="MVG_ROUTE_CACHE_TTL_SECONDS",
    )
    mvg_route_cache_stale_ttl_seconds: int = Field(
        900,
        alias="MVG_ROUTE_CACHE_STALE_TTL_SECONDS",
    )
    cache_singleflight_lock_ttl_seconds: int = Field(
        5,
        alias="CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS",
    )
    cache_singleflight_lock_wait_seconds: float = Field(
        5.0,
        alias="CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS",
    )
    cache_singleflight_retry_delay_seconds: float = Field(
        0.05,
        alias="CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS",
    )
    database_url: str = Field(
        "postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(
        5,
        alias="DATABASE_POOL_SIZE",
        ge=1,
    )
    database_max_overflow: int = Field(
        5,
        alias="DATABASE_MAX_OVERFLOW",
        ge=0,
    )
    database_echo: bool = Field(
        False,
        alias="DATABASE_ECHO",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
