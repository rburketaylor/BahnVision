import pytest

import app.services.cache as cache_module


@pytest.mark.asyncio
async def test_get_json_valkey_hit_counts_as_hit(cache_service, monkeypatch):
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key = "metrics_json_hit"
    value = {"hello": "world"}

    await cache_service.set_json(key, value, ttl_seconds=60)
    assert await cache_service.get_json(key) == value

    assert events == [("json", "hit")]


@pytest.mark.asyncio
async def test_get_json_fallback_counts_as_miss(
    cache_service, fake_valkey, monkeypatch
):
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key = "metrics_json_fallback"
    value = {"fallback": True}

    await cache_service.set_json(key, value, ttl_seconds=60)
    await fake_valkey.delete(key)

    assert await cache_service.get_json(key) == value
    assert ("json", "miss") in events
    assert ("json", "hit") not in events


@pytest.mark.asyncio
async def test_get_stale_json_fallback_counts_as_miss(
    cache_service, fake_valkey, monkeypatch
):
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key = "metrics_stale_fallback"
    value = {"stale": True}
    stale_key = f"{key}{cache_module.CacheService._STALE_SUFFIX}"

    await cache_service.set_json(key, value, ttl_seconds=60, stale_ttl_seconds=300)
    await fake_valkey.delete(stale_key)

    assert await cache_service.get_stale_json(key) == value
    assert ("stale", "miss") in events
    assert ("stale", "hit") not in events


@pytest.mark.asyncio
async def test_get_raw_fallback_counts_as_miss(cache_service, fake_valkey, monkeypatch):
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key = "metrics_raw_fallback"
    value = "ok"

    await cache_service.set(key, value, ttl_seconds=60)
    await fake_valkey.delete(key)

    assert await cache_service.get(key) == value
    assert ("raw", "miss") in events
    assert ("raw", "hit") not in events
