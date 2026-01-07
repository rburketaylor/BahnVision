"""Application configuration.

Environment variables are loaded from .env file and can be overridden.
All settings have sensible defaults for local development.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _valkey_alias(env_name: str) -> AliasChoices:
    """Support both VALKEY_* and REDIS_* env var names for compatibility."""
    redis_name = env_name.replace("VALKEY_", "REDIS_")
    return AliasChoices(redis_name, env_name)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ==========================================================================
    # Infrastructure
    # ==========================================================================

    # Environment mode - set to 'production' in production deployments
    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
        description="Deployment environment: 'development', 'staging', or 'production'.",
    )

    valkey_url: str = Field(
        default="valkey://localhost:6379/0",
        validation_alias=_valkey_alias("VALKEY_URL"),
    )

    database_url: str = Field(
        default="postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision",
        alias="DATABASE_URL",
        description="Database connection URL. Use environment variable in production.",
    )
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE", ge=1)
    database_max_overflow: int = Field(default=5, alias="DATABASE_MAX_OVERFLOW", ge=0)
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")

    # ==========================================================================
    # Cache TTLs (seconds)
    # ==========================================================================

    # Global defaults
    valkey_cache_ttl_seconds: int = Field(
        default=30,
        validation_alias=_valkey_alias("VALKEY_CACHE_TTL_SECONDS"),
    )
    valkey_cache_ttl_not_found_seconds: int = Field(
        default=15,
        validation_alias=_valkey_alias("VALKEY_CACHE_TTL_NOT_FOUND_SECONDS"),
    )

    # Departures: short TTL for real-time data
    transit_departures_cache_ttl_seconds: int = Field(
        default=30, alias="TRANSIT_DEPARTURES_CACHE_TTL_SECONDS"
    )
    transit_departures_cache_stale_ttl_seconds: int = Field(
        default=300, alias="TRANSIT_DEPARTURES_CACHE_STALE_TTL_SECONDS"
    )

    # Station search: medium TTL
    transit_station_search_cache_ttl_seconds: int = Field(
        default=60, alias="TRANSIT_STATION_SEARCH_CACHE_TTL_SECONDS"
    )
    transit_station_search_cache_stale_ttl_seconds: int = Field(
        default=600, alias="TRANSIT_STATION_SEARCH_CACHE_STALE_TTL_SECONDS"
    )

    # Station list: long TTL (changes rarely)
    transit_station_list_cache_ttl_seconds: int = Field(
        default=86400, alias="TRANSIT_STATION_LIST_CACHE_TTL_SECONDS"
    )
    transit_station_list_cache_stale_ttl_seconds: int = Field(
        default=172800, alias="TRANSIT_STATION_LIST_CACHE_STALE_TTL_SECONDS"
    )

    # Route planning: medium TTL
    transit_route_cache_ttl_seconds: int = Field(
        default=120, alias="TRANSIT_ROUTE_CACHE_TTL_SECONDS"
    )
    transit_route_cache_stale_ttl_seconds: int = Field(
        default=900, alias="TRANSIT_ROUTE_CACHE_STALE_TTL_SECONDS"
    )

    # Heatmap: longer TTL (expensive aggregation, refreshed in background)
    heatmap_cache_ttl_seconds: int = Field(
        default=300, alias="HEATMAP_CACHE_TTL_SECONDS", ge=0
    )
    heatmap_cache_stale_ttl_seconds: int = Field(
        default=3600,
        alias="HEATMAP_CACHE_STALE_TTL_SECONDS",
        ge=0,
        description="How long to retain a stale heatmap cache entry for fast fallbacks.",
    )
    heatmap_live_cache_ttl_seconds: int = Field(
        default=600,
        alias="HEATMAP_LIVE_CACHE_TTL_SECONDS",
        ge=0,
        description="TTL for live heatmap snapshot cache entries.",
    )
    heatmap_live_cache_stale_ttl_seconds: int = Field(
        default=1800,
        alias="HEATMAP_LIVE_CACHE_STALE_TTL_SECONDS",
        ge=0,
        description="How long to retain a stale live heatmap snapshot.",
    )

    # ==========================================================================
    # Cache Behavior
    # ==========================================================================

    cache_singleflight_lock_ttl_seconds: int = Field(
        default=5, alias="CACHE_SINGLEFLIGHT_LOCK_TTL_SECONDS"
    )
    cache_singleflight_lock_wait_seconds: float = Field(
        default=5.0, alias="CACHE_SINGLEFLIGHT_LOCK_WAIT_SECONDS"
    )
    cache_singleflight_retry_delay_seconds: float = Field(
        default=0.05, alias="CACHE_SINGLEFLIGHT_RETRY_DELAY_SECONDS"
    )
    cache_circuit_breaker_timeout_seconds: float = Field(
        default=2.0, alias="CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS", ge=0.0
    )

    # ==========================================================================
    # Cache Warmup
    # ==========================================================================

    cache_warmup_departure_stations: list[str] = Field(
        default_factory=list, alias="CACHE_WARMUP_DEPARTURE_STATIONS"
    )
    cache_warmup_departure_limit: int = Field(
        default=10, alias="CACHE_WARMUP_DEPARTURE_LIMIT", ge=1, le=40
    )
    cache_warmup_departure_offset_minutes: int = Field(
        default=0, alias="CACHE_WARMUP_DEPARTURE_OFFSET_MINUTES", ge=0, le=240
    )

    heatmap_cache_warmup_enabled: bool = Field(
        default=True,
        alias="HEATMAP_CACHE_WARMUP_ENABLED",
        description="Warm heatmap cache after each GTFS-RT harvest cycle.",
    )
    heatmap_cache_warmup_time_ranges: list[str] = Field(
        default_factory=lambda: ["24h"],
        alias="HEATMAP_CACHE_WARMUP_TIME_RANGES",
        description="Comma-separated list of heatmap time_range presets to prewarm (e.g. 1h,6h,24h).",
    )
    heatmap_cache_warmup_zoom_levels: list[int] = Field(
        default_factory=lambda: [6, 10, 12],
        alias="HEATMAP_CACHE_WARMUP_ZOOM_LEVELS",
        description="Comma-separated list of zoom levels to prewarm (e.g. 6,10,12).",
    )
    heatmap_cache_warmup_bucket_width_minutes: int = Field(
        default=60,
        alias="HEATMAP_CACHE_WARMUP_BUCKET_WIDTH_MINUTES",
        ge=15,
        le=1440,
        description="Bucket width minutes to prewarm for heatmap cache.",
    )

    # ==========================================================================
    # CORS
    # ==========================================================================

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
        default=None, alias="CORS_ALLOW_ORIGIN_REGEX"
    )
    cors_strict_mode: bool = Field(default=False, alias="CORS_STRICT_MODE")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(
        default=60, alias="RATE_LIMIT_REQUESTS_PER_MINUTE", gt=0
    )
    rate_limit_requests_per_hour: int = Field(
        default=1000, alias="RATE_LIMIT_REQUESTS_PER_HOUR", gt=0
    )
    rate_limit_requests_per_day: int = Field(
        default=10000, alias="RATE_LIMIT_REQUESTS_PER_DAY", gt=0
    )

    # ==========================================================================
    # GTFS Configuration
    # ==========================================================================

    # GTFS Static Feed Configuration
    gtfs_feed_url: str = Field(
        default="https://download.gtfs.de/germany/free/latest.zip",
        alias="GTFS_FEED_URL",
    )
    gtfs_use_unlogged_tables: bool = Field(
        default=True, alias="GTFS_USE_UNLOGGED_TABLES"
    )
    gtfs_update_interval_hours: int = Field(
        default=24, alias="GTFS_UPDATE_INTERVAL_HOURS"
    )
    gtfs_max_feed_age_hours: int = Field(
        default=48,
        alias="GTFS_MAX_FEED_AGE_HOURS",  # Force re-download if older
    )
    gtfs_download_timeout_seconds: int = Field(
        default=300,
        alias="GTFS_DOWNLOAD_TIMEOUT",  # 5 min for large feed
    )
    gtfs_storage_path: str = Field(default="/data/gtfs", alias="GTFS_STORAGE_PATH")

    # GTFS-RT Configuration
    gtfs_rt_enabled: bool = Field(default=False, alias="GTFS_RT_ENABLED")
    gtfs_rt_feed_url: str = Field(
        default="https://realtime.gtfs.de/realtime-free.pb", alias="GTFS_RT_FEED_URL"
    )
    gtfs_rt_timeout_seconds: int = Field(default=10, alias="GTFS_RT_TIMEOUT")
    gtfs_rt_circuit_breaker_threshold: int = Field(
        default=3, alias="GTFS_RT_CIRCUIT_BREAKER_THRESHOLD"
    )
    gtfs_rt_circuit_breaker_recovery_seconds: int = Field(
        default=60, alias="GTFS_RT_CIRCUIT_BREAKER_RECOVERY"
    )

    # GTFS Cache TTLs
    gtfs_schedule_cache_ttl_seconds: int = Field(
        default=43200,
        alias="GTFS_SCHEDULE_CACHE_TTL_SECONDS",  # 12 hours
    )
    gtfs_stop_cache_ttl_seconds: int = Field(
        default=86400,
        alias="GTFS_STOP_CACHE_TTL_SECONDS",  # 24 hours
    )
    gtfs_rt_cache_ttl_seconds: int = Field(
        default=30,
        alias="GTFS_RT_CACHE_TTL_SECONDS",  # 30 seconds (real-time)
    )

    # GTFS-RT Harvesting Configuration
    gtfs_rt_harvesting_enabled: bool = Field(
        default=True,
        alias="GTFS_RT_HARVESTING_ENABLED",
        description="Enable background GTFS-RT data collection for heatmap.",
    )
    gtfs_rt_harvest_interval_seconds: int = Field(
        default=300,  # 5 minutes - optimized for delay statistics, not real-time tracking
        alias="GTFS_RT_HARVEST_INTERVAL_SECONDS",
        description="Interval between GTFS-RT harvest cycles (seconds).",
    )
    gtfs_rt_stats_retention_days: int = Field(
        default=90,  # Extended retention for aggregated stats (low storage footprint)
        alias="GTFS_RT_STATS_RETENTION_DAYS",
        description="Days to retain station statistics.",
    )

    # ==========================================================================
    # OpenTelemetry (optional)
    # ==========================================================================

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(
        default="bahnvision-backend", alias="OTEL_SERVICE_NAME"
    )
    otel_service_version: str = Field(default="0.1.0", alias="OTEL_SERVICE_VERSION")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://jaeger:4317", alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_otlp_headers: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_HEADERS"
    )
    otel_propagators: str = Field(
        default="tracecontext,baggage,b3", alias="OTEL_PROPAGATORS"
    )

    # ==========================================================================
    # Pydantic Settings Config
    # ==========================================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================================================
    # Validators
    # ==========================================================================

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Parse comma-separated CORS origins, rejecting wildcard '*'."""
        if isinstance(value, str):
            if not value:
                return []
            parsed = [item.strip() for item in value.split(",") if item.strip()]
        else:
            parsed = list(value) if value is not None else []

        if "*" in parsed:
            raise ValueError(
                "Wildcard CORS origin '*' is not allowed. "
                "Specify explicit origins like 'http://localhost:3000'."
            )
        return parsed

    @field_validator("cache_warmup_departure_stations", mode="before")
    @classmethod
    def parse_warmup_stations(cls, value: Any) -> list[str]:
        """Parse comma-separated station list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value) if value else []

    @field_validator("heatmap_cache_warmup_time_ranges", mode="before")
    @classmethod
    def parse_heatmap_time_ranges(cls, value: Any) -> list[str]:
        """Parse comma-separated time range presets."""
        allowed = {"1h", "6h", "24h", "7d", "30d"}
        if isinstance(value, str):
            parsed = [item.strip() for item in value.split(",") if item.strip()]
        else:
            parsed = list(value) if value else []

        normalized: list[str] = []
        for item in parsed:
            item_str = str(item).strip()
            if not item_str:
                continue
            if item_str not in allowed:
                raise ValueError(
                    f"Invalid heatmap time range preset: {item_str}. Allowed: {sorted(allowed)}"
                )
            normalized.append(item_str)

        return normalized or ["24h"]

    @field_validator("heatmap_cache_warmup_zoom_levels", mode="before")
    @classmethod
    def parse_heatmap_zoom_levels(cls, value: Any) -> list[int]:
        """Parse comma-separated zoom level list."""
        if isinstance(value, str):
            raw_items = [item.strip() for item in value.split(",") if item.strip()]
        else:
            raw_items = list(value) if value else []

        zoom_levels: list[int] = []
        for item in raw_items:
            zoom = int(item)
            if zoom < 1 or zoom > 18:
                raise ValueError(f"Invalid heatmap zoom level: {zoom}. Allowed: 1..18")
            if zoom not in zoom_levels:
                zoom_levels.append(zoom)

        return zoom_levels or [6, 10]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Validate security-sensitive settings in production environment."""
        if self.environment.lower() == "production":
            # Check for default database credentials
            default_db_url = "postgresql+asyncpg://bahnvision:bahnvision@localhost"
            if self.database_url.startswith(default_db_url):
                raise ValueError(
                    "Default database credentials detected in production. "
                    "Set DATABASE_URL environment variable with secure credentials."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
