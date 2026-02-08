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
