from __future__ import annotations

from functools import lru_cache
from typing import Any, ClassVar, Iterable

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheTTLConfig:
    """Configuration group for cache TTL settings."""

    # Default values organized by service type
    DEFAULT_VALUES: ClassVar[dict[str, dict[str, int]]] = {
        "mvg_departures": {"ttl": 30, "stale_ttl": 300},
        "mvg_station_search": {"ttl": 60, "stale_ttl": 600},
        "mvg_station_list": {"ttl": 86400, "stale_ttl": 172800},
        "mvg_route": {"ttl": 120, "stale_ttl": 900},
    }

    # Default global cache settings
    GLOBAL_DEFAULTS: ClassVar[dict[str, Any]] = {
        "valkey_cache_ttl_seconds": 30,
        "valkey_cache_ttl_not_found_seconds": 15,
        "cache_singleflight_lock_ttl_seconds": 5,
        "cache_singleflight_lock_wait_seconds": 5.0,
        "cache_singleflight_retry_delay_seconds": 0.05,
        "cache_circuit_breaker_timeout_seconds": 2.0,
    }


class DatabaseConfig:
    """Configuration group for database settings."""

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "database_url": "postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision",
        "database_pool_size": 5,
        "database_max_overflow": 5,
        "database_echo": False,
    }


class CORSConfig:
    """Configuration group for CORS settings."""

    DEFAULT_ORIGINS: ClassVar[list[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]


class OpenTelemetryConfig:
    """Configuration group for OpenTelemetry settings."""

    DEFAULTS: ClassVar[dict[str, Any]] = {
        "otel_enabled": False,
        "otel_service_name": "bahnvision-backend",
        "otel_service_version": "0.1.0",
        "otel_exporter_otlp_endpoint": "http://jaeger:4317",
        "otel_propagators": "tracecontext,baggage,b3",
    }


def _create_redis_alias(field_name: str) -> AliasChoices:
    """Create AliasChoices for Valkey/Redis compatibility."""
    valkey_name = field_name.replace("redis_", "valkey_")
    return AliasChoices(valkey_name, field_name)


def _create_field_with_default(
    field_name: str,
    default_value: Any,
    alias_pattern: str | None = None,
    validation_constraints: dict[str, Any] | None = None,
    is_redis_alias: bool = False,
) -> Field:
    """Helper to create fields with consistent alias patterns."""

    field_kwargs = {"default": default_value}

    if alias_pattern:
        field_kwargs["alias"] = alias_pattern
        if is_redis_alias:
            field_kwargs["validation_alias"] = _create_redis_alias(alias_pattern)
        else:
            field_kwargs["validation_alias"] = AliasChoices(alias_pattern)

    if validation_constraints:
        field_kwargs.update(validation_constraints)

    return Field(**field_kwargs)


class Settings(BaseSettings):
    """Application configuration sourced from environment variables."""

    # === Valkey/Cache Configuration ===
    valkey_url: str = _create_field_with_default(
        "valkey_url",
        "valkey://localhost:6379/0",
        "VALKEY_URL",
        is_redis_alias=True,
    )

    # Global cache TTL settings
    valkey_cache_ttl_seconds: int = _create_field_with_default(
        "valkey_cache_ttl_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["valkey_cache_ttl_seconds"],
        "VALKEY_CACHE_TTL_SECONDS",
        is_redis_alias=True,
    )

    valkey_cache_ttl_not_found_seconds: int = _create_field_with_default(
        "valkey_cache_ttl_not_found_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["valkey_cache_ttl_not_found_seconds"],
        "VALKEY_CACHE_TTL_NOT_FOUND_SECONDS",
        is_redis_alias=True,
    )

    # MVG service TTL settings - generated programmatically
    mvg_departures_cache_ttl_seconds: int = _create_field_with_default(
        "mvg_departures_cache_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_departures"]["ttl"],
        "MVG_DEPARTURES_CACHE_TTL_SECONDS",
    )

    mvg_departures_cache_stale_ttl_seconds: int = _create_field_with_default(
        "mvg_departures_cache_stale_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_departures"]["stale_ttl"],
        "MVG_DEPARTURES_CACHE_STALE_TTL_SECONDS",
    )

    mvg_station_search_cache_ttl_seconds: int = _create_field_with_default(
        "mvg_station_search_cache_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_station_search"]["ttl"],
        "MVG_STATION_SEARCH_CACHE_TTL_SECONDS",
    )

    mvg_station_search_cache_stale_ttl_seconds: int = _create_field_with_default(
        "mvg_station_search_cache_stale_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_station_search"]["stale_ttl"],
        "MVG_STATION_SEARCH_CACHE_STALE_TTL_SECONDS",
    )

    mvg_station_list_cache_ttl_seconds: int = _create_field_with_default(
        "mvg_station_list_cache_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_station_list"]["ttl"],
        "MVG_STATION_LIST_CACHE_TTL_SECONDS",
    )

    mvg_station_list_cache_stale_ttl_seconds: int = _create_field_with_default(
        "mvg_station_list_cache_stale_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_station_list"]["stale_ttl"],
        "MVG_STATION_LIST_CACHE_STALE_TTL_SECONDS",
    )

    mvg_route_cache_ttl_seconds: int = _create_field_with_default(
        "mvg_route_cache_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_route"]["ttl"],
        "MVG_ROUTE_CACHE_TTL_SECONDS",
    )

    mvg_route_cache_stale_ttl_seconds: int = _create_field_with_default(
        "mvg_route_cache_stale_ttl_seconds",
        CacheTTLConfig.DEFAULT_VALUES["mvg_route"]["stale_ttl"],
        "MVG_ROUTE_CACHE_STALE_TTL_SECONDS",
    )

    # Advanced cache behavior settings
    cache_singleflight_lock_ttl_seconds: int = _create_field_with_default(
        "cache_singleflight_lock_ttl_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["cache_singleflight_lock_ttl_seconds"],
        "CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS",
    )

    cache_singleflight_lock_wait_seconds: float = _create_field_with_default(
        "cache_singleflight_lock_wait_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["cache_singleflight_lock_wait_seconds"],
        "CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS",
    )

    cache_singleflight_retry_delay_seconds: float = _create_field_with_default(
        "cache_singleflight_retry_delay_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["cache_singleflight_retry_delay_seconds"],
        "CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS",
    )

    cache_circuit_breaker_timeout_seconds: float = _create_field_with_default(
        "cache_circuit_breaker_timeout_seconds",
        CacheTTLConfig.GLOBAL_DEFAULTS["cache_circuit_breaker_timeout_seconds"],
        "CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS",
        {"ge": 0.0},
    )

    # === CORS Configuration ===
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: CORSConfig.DEFAULT_ORIGINS.copy(),
        alias="CORS_ALLOW_ORIGINS",
    )

    cors_allow_origin_regex: str | None = Field(
        default=None,
        alias="CORS_ALLOW_ORIGIN_REGEX",
    )

    # === Database Configuration ===
    database_url: str = _create_field_with_default(
        "database_url",
        DatabaseConfig.DEFAULTS["database_url"],
        "DATABASE_URL",
    )

    database_pool_size: int = _create_field_with_default(
        "database_pool_size",
        DatabaseConfig.DEFAULTS["database_pool_size"],
        "DATABASE_POOL_SIZE",
        {"ge": 1},
    )

    database_max_overflow: int = _create_field_with_default(
        "database_max_overflow",
        DatabaseConfig.DEFAULTS["database_max_overflow"],
        "DATABASE_MAX_OVERFLOW",
        {"ge": 0},
    )

    database_echo: bool = _create_field_with_default(
        "database_echo",
        DatabaseConfig.DEFAULTS["database_echo"],
        "DATABASE_ECHO",
    )

    # === OpenTelemetry Configuration ===
    otel_enabled: bool = _create_field_with_default(
        "otel_enabled",
        OpenTelemetryConfig.DEFAULTS["otel_enabled"],
        "OTEL_ENABLED",
    )

    otel_service_name: str = _create_field_with_default(
        "otel_service_name",
        OpenTelemetryConfig.DEFAULTS["otel_service_name"],
        "OTEL_SERVICE_NAME",
    )

    otel_service_version: str = _create_field_with_default(
        "otel_service_version",
        OpenTelemetryConfig.DEFAULTS["otel_service_version"],
        "OTEL_SERVICE_VERSION",
    )

    otel_exporter_otlp_endpoint: str = _create_field_with_default(
        "otel_exporter_otlp_endpoint",
        OpenTelemetryConfig.DEFAULTS["otel_exporter_otlp_endpoint"],
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    )

    otel_exporter_otlp_headers: str | None = Field(
        default=None,
        alias="OTEL_EXPORTER_OTLP_HEADERS",
    )

    otel_propagators: str = _create_field_with_default(
        "otel_propagators",
        OpenTelemetryConfig.DEFAULTS["otel_propagators"],
        "OTEL_PROPAGATORS",
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