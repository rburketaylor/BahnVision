"""Tests for Settings validation and parsing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_parsing_accepts_comma_separated():
    settings = Settings(
        CORS_ALLOW_ORIGINS="https://app.example.com, http://localhost:9000"
    )

    assert settings.cors_allow_origins == [
        "https://app.example.com",
        "http://localhost:9000",
    ]


def test_cors_parsing_accepts_json_array():
    settings = Settings(
        CORS_ALLOW_ORIGINS='["https://app.example.com", "http://localhost:9000"]'
    )

    assert settings.cors_allow_origins == [
        "https://app.example.com",
        "http://localhost:9000",
    ]


def test_cors_parsing_rejects_wildcard():
    with pytest.raises(ValidationError):
        Settings(CORS_ALLOW_ORIGINS="http://localhost:3000, *")


def test_cors_parsing_accepts_comma_separated_env_var(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS", "https://app.example.com, http://localhost:9000"
    )

    settings = Settings()

    assert settings.cors_allow_origins == [
        "https://app.example.com",
        "http://localhost:9000",
    ]


def test_valkey_fields_accept_redis_aliases(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/1")
    monkeypatch.setenv("REDIS_CACHE_TTL_SECONDS", "45")
    monkeypatch.setenv("REDIS_CACHE_TTL_NOT_FOUND_SECONDS", "10")

    settings = Settings()

    assert settings.valkey_url == "redis://example:6379/1"
    assert settings.valkey_cache_ttl_seconds == 45
    assert settings.valkey_cache_ttl_not_found_seconds == 10


def test_cache_bounds_enforced():
    with pytest.raises(ValidationError):
        Settings(CACHE_CIRCUIT_BREAKER_TIMEOUT_SECONDS=-0.1)


def test_fallback_cache_max_entries_defaults():
    settings = Settings()

    assert settings.fallback_cache_max_entries == 1024


def test_fallback_cache_max_entries_from_env():
    settings = Settings(FALLBACK_CACHE_MAX_ENTRIES="2048")

    assert settings.fallback_cache_max_entries == 2048


def test_fallback_cache_max_entries_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(FALLBACK_CACHE_MAX_ENTRIES=0)


def test_database_pool_settings_defaults():
    settings = Settings()

    assert settings.database_pool_timeout_seconds == 30.0
    assert settings.database_pool_recycle_seconds == 1800
    assert settings.database_pool_pre_ping is True


def test_database_pool_settings_from_env():
    settings = Settings(
        DATABASE_POOL_TIMEOUT_SECONDS="12.5",
        DATABASE_POOL_RECYCLE_SECONDS="600",
        DATABASE_POOL_PRE_PING="false",
    )

    assert settings.database_pool_timeout_seconds == 12.5
    assert settings.database_pool_recycle_seconds == 600
    assert settings.database_pool_pre_ping is False


def test_database_pool_timeout_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(DATABASE_POOL_TIMEOUT_SECONDS=0)


def test_gtfs_stop_times_batch_size_defaults():
    settings = Settings()

    assert settings.gtfs_stop_times_batch_size == 500_000


def test_gtfs_stop_times_batch_size_must_be_positive():
    with pytest.raises(ValidationError):
        Settings(GTFS_STOP_TIMES_BATCH_SIZE=0)


def test_gtfs_feed_archive_retention_count_defaults():
    settings = Settings()

    assert settings.gtfs_feed_archive_retention_count == 2


def test_gtfs_feed_archive_retention_count_rejects_negative_values():
    with pytest.raises(ValidationError):
        Settings(GTFS_FEED_ARCHIVE_RETENTION_COUNT=-1)


def test_gtfs_rt_retention_enabled_defaults_disabled():
    settings = Settings()

    assert settings.gtfs_rt_retention_enabled is False


def test_gtfs_rt_retention_enabled_from_env():
    settings = Settings(GTFS_RT_RETENTION_ENABLED="true")

    assert settings.gtfs_rt_retention_enabled is True
