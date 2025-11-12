"""Unit tests for shared caching utilities."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from pydantic import BaseModel

import app.api.v1.shared.caching as caching
from app.api.v1.shared.caching import (
    CacheManager,
    CacheRefreshProtocol,
    execute_cache_refresh,
    handle_cache_errors,
    handle_cache_lookup,
)
from app.services.mvg_client import MVGServiceError, StationNotFoundError


class SampleModel(BaseModel):
    value: int


class FakeCache:
    """Simple in-memory cache double."""

    def __init__(self) -> None:
        self.values: dict[str, dict[str, Any]] = {}
        self.stale_values: dict[str, dict[str, Any]] = {}
        self.set_calls: list[dict[str, Any]] = []
        self.single_flight_calls: list[tuple[str, float, float, float]] = []
        self.stale_read_results: list[dict[str, Any] | None] = []

    async def get_json(self, key: str) -> dict[str, Any] | None:
        return self.values.get(key)

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl_seconds: float | None = None,
        stale_ttl_seconds: float | None = None,
    ) -> None:
        self.values[key] = value
        self.set_calls.append(
            {
                "key": key,
                "value": value,
                "ttl_seconds": ttl_seconds,
                "stale_ttl_seconds": stale_ttl_seconds,
            }
        )

    async def get_stale_json(self, key: str) -> dict[str, Any] | None:
        if self.stale_read_results:
            return self.stale_read_results.pop(0)
        return self.stale_values.get(key)

    def single_flight(
        self,
        key: str,
        ttl_seconds: float,
        wait_timeout: float,
        retry_delay: float,
    ):
        self.single_flight_calls.append((key, ttl_seconds, wait_timeout, retry_delay))

        class _SingleFlight:
            async def __aenter__(self):
                return None

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        return _SingleFlight()


class DummyProtocol(CacheRefreshProtocol[SampleModel]):
    """Cache protocol stub with configurable fetch/store behavior."""

    def __init__(self, cache_name: str = "mvg_departures") -> None:
        self._cache_name = cache_name
        self.fetch_exception: Exception | None = None
        self.fetch_result: SampleModel = SampleModel(value=1)
        self.store_calls: list[tuple[str, SampleModel]] = []

    async def fetch_data(self, **kwargs: Any) -> SampleModel:
        if self.fetch_exception:
            raise self.fetch_exception
        return self.fetch_result

    async def store_data(
        self,
        cache: FakeCache,
        cache_key: str,
        data: SampleModel,
        settings: Any,
    ) -> None:
        self.store_calls.append((cache_key, data))
        await cache.set_json(
            cache_key,
            data.model_dump(),
            ttl_seconds=getattr(settings, f"{self.cache_name()}_cache_ttl_seconds", 60),
            stale_ttl_seconds=getattr(settings, f"{self.cache_name()}_cache_stale_ttl_seconds", 120),
        )

    def cache_name(self) -> str:
        return self._cache_name

    def get_model_class(self) -> type[SampleModel]:
        return SampleModel


@pytest.fixture
def fake_cache() -> FakeCache:
    return FakeCache()


@pytest.fixture
def dummy_settings():
    class DummySettings:
        cache_singleflight_lock_ttl_seconds = 1.0
        cache_singleflight_lock_wait_seconds = 0.1
        cache_singleflight_retry_delay_seconds = 0.01
        valkey_cache_ttl_not_found_seconds = 60
        mvg_departures_cache_ttl_seconds = 45
        mvg_departures_cache_stale_ttl_seconds = 120
        mvg_route_cache_stale_ttl_seconds = 180

    return DummySettings()


@pytest.fixture
def cache_events(monkeypatch):
    events: list[tuple[str, str]] = []

    def fake_record(cache_name: str, event: str) -> None:
        events.append((cache_name, event))

    monkeypatch.setattr(caching, "record_cache_event", fake_record)
    return events


@pytest.fixture
def refresh_observations(monkeypatch):
    calls: list[tuple[str, float]] = []

    def fake_observe(cache_name: str, duration: float) -> None:
        calls.append((cache_name, duration))

    monkeypatch.setattr(caching, "observe_cache_refresh", fake_observe)
    return calls


@pytest.mark.asyncio
async def test_handle_cache_lookup_hit_sets_headers(fake_cache, cache_events):
    fake_cache.values["cache-key"] = {"value": 7}
    response = Response()
    background = BackgroundTasks()

    result = await handle_cache_lookup(
        cache=fake_cache,
        cache_key="cache-key",
        cache_name="mvg_departures",
        response=response,
        background_tasks=background,
        refresh_func=lambda **_: None,
        refresh_kwargs={},
        model_class=SampleModel,
    )

    assert result.status == "hit"
    assert result.data == SampleModel(value=7)
    assert response.headers["X-Cache-Status"] == "hit"
    assert cache_events == [("mvg_departures", "hit")]


@pytest.mark.asyncio
async def test_handle_cache_lookup_not_found_marker_raises(fake_cache, cache_events):
    fake_cache.values["cache-key"] = {"__status": "not_found", "detail": "gone"}
    response = Response()
    background = BackgroundTasks()

    with pytest.raises(HTTPException) as exc_info:
        await handle_cache_lookup(
            cache=fake_cache,
            cache_key="cache-key",
            cache_name="mvg_departures",
            response=response,
            background_tasks=background,
            refresh_func=lambda **_: None,
            refresh_kwargs={},
            model_class=SampleModel,
        )

    assert exc_info.value.status_code == 404
    assert response.headers["X-Cache-Status"] == "hit"
    assert cache_events == [("mvg_departures", "hit")]


@pytest.mark.asyncio
async def test_handle_cache_lookup_returns_stale_and_schedules_refresh(fake_cache, cache_events):
    fake_cache.stale_values["cache-key"] = {"value": 3}
    response = Response()
    background = BackgroundTasks()
    refresh_calls: list[dict[str, Any]] = []

    def refresh_func(**kwargs: Any) -> None:
        refresh_calls.append(kwargs)

    result = await handle_cache_lookup(
        cache=fake_cache,
        cache_key="cache-key",
        cache_name="mvg_departures",
        response=response,
        background_tasks=background,
        refresh_func=refresh_func,
        refresh_kwargs={"arg": "value"},
        model_class=SampleModel,
    )

    assert result.status == "stale-refresh"
    assert result.data == SampleModel(value=3)
    assert response.headers["X-Cache-Status"] == "stale-refresh"
    assert len(background.tasks) == 1
    assert refresh_calls == []
    assert cache_events == [("mvg_departures", "stale_return")]


@pytest.mark.asyncio
async def test_handle_cache_errors_timeout_returns_stale(fake_cache, cache_events):
    fake_cache.stale_values["cache-key"] = {"value": 5}

    result = await handle_cache_errors(
        cache=fake_cache,
        cache_key="cache-key",
        cache_name="mvg_departures",
        exc=TimeoutError("lock"),
        model_class=SampleModel,
    )

    assert result is not None
    assert result.status == "stale"
    assert result.data == SampleModel(value=5)
    assert cache_events == [
        ("mvg_departures", "lock_timeout"),
        ("mvg_departures", "stale_return"),
    ]


@pytest.mark.asyncio
async def test_handle_cache_errors_timeout_without_stale_raises(fake_cache, cache_events):
    with pytest.raises(HTTPException) as exc_info:
        await handle_cache_errors(
            cache=fake_cache,
            cache_key="cache-key",
            cache_name="mvg_departures",
            exc=TimeoutError("lock"),
            model_class=SampleModel,
            allow_stale_fallback=False,
        )

    assert exc_info.value.status_code == 503
    assert cache_events == [("mvg_departures", "lock_timeout")]


@pytest.mark.asyncio
async def test_handle_cache_errors_mvg_error_with_stale(fake_cache, cache_events):
    fake_cache.stale_values["cache-key"] = {"value": 2}

    result = await handle_cache_errors(
        cache=fake_cache,
        cache_key="cache-key",
        cache_name="mvg_departures",
        exc=MVGServiceError("upstream error"),
        model_class=SampleModel,
    )

    assert result is not None
    assert result.data == SampleModel(value=2)
    assert cache_events == [
        ("mvg_departures", "stale_return"),
    ]


@pytest.mark.asyncio
async def test_handle_cache_errors_not_found_raises(fake_cache, cache_events):
    with pytest.raises(HTTPException) as exc_info:
        await handle_cache_errors(
            cache=fake_cache,
            cache_key="cache-key",
            cache_name="mvg_departures",
            exc=StationNotFoundError("missing"),
            model_class=SampleModel,
        )

    assert exc_info.value.status_code == 404
    assert cache_events == [("mvg_departures", "not_found")]


@pytest.mark.asyncio
async def test_execute_cache_refresh_uses_cached_payload(fake_cache, dummy_settings, cache_events):
    fake_cache.values["cache-key"] = {"value": 11}
    protocol = DummyProtocol()

    result = await execute_cache_refresh(
        protocol=protocol,
        cache=fake_cache,
        cache_key="cache-key",
        settings=dummy_settings,
    )

    assert result == SampleModel(value=11)
    assert protocol.store_calls == []
    assert cache_events == [("mvg_departures", "refresh_skip_hit")]


@pytest.mark.asyncio
async def test_execute_cache_refresh_records_not_found_marker(fake_cache, dummy_settings, cache_events):
    protocol = DummyProtocol()
    protocol.fetch_exception = StationNotFoundError("no station")

    with pytest.raises(StationNotFoundError):
        await execute_cache_refresh(
            protocol=protocol,
            cache=fake_cache,
            cache_key="cache-key",
            settings=dummy_settings,
        )

    assert fake_cache.set_calls[-1]["value"] == {"__status": "not_found", "detail": "no station"}
    assert fake_cache.set_calls[-1]["ttl_seconds"] == dummy_settings.valkey_cache_ttl_not_found_seconds
    assert cache_events[-1] == ("mvg_departures", "refresh_not_found")


@pytest.mark.asyncio
async def test_execute_cache_refresh_stores_data_and_records_metrics(
    fake_cache,
    dummy_settings,
    cache_events,
    refresh_observations,
):
    protocol = DummyProtocol()
    protocol.fetch_result = SampleModel(value=42)

    result = await execute_cache_refresh(
        protocol=protocol,
        cache=fake_cache,
        cache_key="cache-key",
        settings=dummy_settings,
    )

    assert result == SampleModel(value=42)
    assert fake_cache.values["cache-key"] == {"value": 42}
    assert protocol.store_calls
    assert cache_events[-1] == ("mvg_departures", "refresh_success")
    assert refresh_observations
    assert fake_cache.single_flight_calls


@pytest.mark.asyncio
async def test_execute_cache_refresh_propagates_mvg_errors(fake_cache, dummy_settings, cache_events):
    protocol = DummyProtocol()
    protocol.fetch_exception = MVGServiceError("boom")

    with pytest.raises(MVGServiceError):
        await execute_cache_refresh(
            protocol=protocol,
            cache=fake_cache,
            cache_key="cache-key",
            settings=dummy_settings,
        )

    assert cache_events[-1] == ("mvg_departures", "refresh_error")


@pytest.mark.asyncio
async def test_cache_manager_refresh_then_hit(
    fake_cache,
    dummy_settings,
    cache_events,
    refresh_observations,
):
    protocol = DummyProtocol()
    protocol.fetch_result = SampleModel(value=9)
    manager = CacheManager(protocol=protocol, cache=fake_cache, cache_name="mvg_departures")

    response = Response()
    background = BackgroundTasks()
    result = await manager.get_cached_data(
        cache_key="cache-key",
        response=response,
        background_tasks=background,
        settings=dummy_settings,
    )

    assert result == SampleModel(value=9)
    assert response.headers["X-Cache-Status"] == "miss"
    assert fake_cache.values["cache-key"] == {"value": 9}

    response_hit = Response()
    background_hit = BackgroundTasks()
    hit_result = await manager.get_cached_data(
        cache_key="cache-key",
        response=response_hit,
        background_tasks=background_hit,
        settings=dummy_settings,
    )

    assert hit_result == SampleModel(value=9)
    assert response_hit.headers["X-Cache-Status"] == "hit"
    assert ("mvg_departures", "hit") in cache_events


@pytest.mark.asyncio
async def test_cache_manager_returns_stale_when_refresh_fails(
    fake_cache,
    dummy_settings,
    cache_events,
    monkeypatch,
):
    protocol = DummyProtocol()
    manager = CacheManager(protocol=protocol, cache=fake_cache, cache_name="mvg_departures")
    fake_cache.stale_values["cache-key"] = {"value": 4}
    fake_cache.stale_read_results = [None]

    async def failing_refresh(**kwargs: Any):
        raise MVGServiceError("unavailable")

    monkeypatch.setattr(caching, "execute_cache_refresh", failing_refresh)

    response = Response()
    background = BackgroundTasks()
    result = await manager.get_cached_data(
        cache_key="cache-key",
        response=response,
        background_tasks=background,
        settings=dummy_settings,
    )

    assert result == SampleModel(value=4)
    assert response.headers["X-Cache-Status"] == "stale"
    assert ("mvg_departures", "stale_return") in cache_events
