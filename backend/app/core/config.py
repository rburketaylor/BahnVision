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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
