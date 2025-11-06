from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from pydantic import AliasChoices, Field, field_validator
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
    mvg_station_list_cache_ttl_seconds: int = Field(
        86400,
        alias="MVG_STATION_LIST_CACHE_TTL_SECONDS",
    )
    mvg_station_list_cache_stale_ttl_seconds: int = Field(
        172800,
        alias="MVG_STATION_LIST_CACHE_STALE_TTL_SECONDS",
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
    cache_circuit_breaker_timeout_seconds: float = Field(
        2.0,
        alias="CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS",
        ge=0.0,
    )
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        alias="CORS_ALLOW_ORIGINS",
    )
    cors_allow_origin_regex: str | None = Field(
        default=None,
        alias="CORS_ALLOW_ORIGIN_REGEX",
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
    # OpenTelemetry configuration
    otel_enabled: bool = Field(
        False,
        alias="OTEL_ENABLED",
    )
    otel_service_name: str = Field(
        "bahnvision-backend",
        alias="OTEL_SERVICE_NAME",
    )
    otel_service_version: str = Field(
        "0.1.0",
        alias="OTEL_SERVICE_VERSION",
    )
    otel_exporter_otlp_endpoint: str = Field(
        "http://jaeger:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    otel_exporter_otlp_headers: str | None = Field(
        None,
        alias="OTEL_EXPORTER_OTLP_HEADERS",
    )
    otel_propagators: str = Field(
        "tracecontext,baggage,b3",
        alias="OTEL_PROPAGATORS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(
        cls, value: Any
    ) -> Iterable[str]:
        """Allow comma-separated strings for CORS origins."""
        if isinstance(value, str):
            if not value:
                return []
            parsed = [item.strip() for item in value.split(",") if item.strip()]
        else:
            parsed = list(value) if value is not None else []

        if any(origin == "*" for origin in parsed):
            msg = (
                "Unsafe CORS origin '*' detected. Specify explicit origins (e.g. "
                "http://localhost:3000) or leave empty to disable CORS."
            )
            raise ValueError(msg)

        return parsed


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
