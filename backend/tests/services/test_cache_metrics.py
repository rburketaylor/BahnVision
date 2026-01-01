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


@pytest.mark.asyncio
async def test_mget_json_valkey_hit_counts_as_hit(cache_service, monkeypatch):
    """Test that mget_json records hit events for found keys."""
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key1 = "metrics_mget_json_hit1"
    key2 = "metrics_mget_json_hit2"
    value1 = {"key": "value1"}
    value2 = {"key": "value2"}

    await cache_service.set_json(key1, value1, ttl_seconds=60)
    await cache_service.set_json(key2, value2, ttl_seconds=60)

    result = await cache_service.mget_json([key1, key2])

    assert result[key1] == value1
    assert result[key2] == value2
    # Should have 2 hits for the mget_json call
    hit_events = [e for e in events if e == ("json", "hit")]
    assert len(hit_events) >= 2


@pytest.mark.asyncio
async def test_mget_json_valkey_miss_counts_as_miss(cache_service, monkeypatch):
    """Test that mget_json records miss events for not found keys."""
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    result = await cache_service.mget_json(["nonexistent_key1", "nonexistent_key2"])

    assert result["nonexistent_key1"] is None
    assert result["nonexistent_key2"] is None
    # Should have 2 misses
    miss_events = [e for e in events if e == ("json", "miss")]
    assert len(miss_events) == 2


@pytest.mark.asyncio
async def test_mget_json_mixed_hits_and_misses(cache_service, monkeypatch):
    """Test that mget_json correctly handles mixed hits and misses."""
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    key_exists = "metrics_mget_json_exists"
    key_missing = "metrics_mget_json_missing"
    value = {"exists": True}

    await cache_service.set_json(key_exists, value, ttl_seconds=60)

    events.clear()  # Clear events from set_json

    result = await cache_service.mget_json([key_exists, key_missing])

    assert result[key_exists] == value
    assert result[key_missing] is None
    # Should have 1 hit and 1 miss
    assert ("json", "hit") in events
    assert ("json", "miss") in events


@pytest.mark.asyncio
async def test_mget_json_empty_keys_returns_empty_dict(cache_service, monkeypatch):
    """Test that mget_json returns empty dict for empty keys list."""
    events: list[tuple[str, str]] = []

    def record(cache: str, event: str) -> None:
        events.append((cache, event))

    monkeypatch.setattr(cache_module, "record_cache_event", record)

    result = await cache_service.mget_json([])

    assert result == {}
    # Should have no events
    assert len(events) == 0
