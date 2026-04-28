"""Unit tests for cache primitives."""

from unittest.mock import Mock
from unittest.mock import patch
import pytest

from app.services.cache import CircuitBreaker, FallbackCache, TTLConfig
from app.core.config import Settings


class TestTTLConfig:
    """Tests for TTLConfig."""

    @pytest.fixture
    def mock_settings(self):
        with patch("app.services.cache.get_settings") as mock:
            settings = Mock(spec=Settings)
            settings.valkey_cache_ttl_seconds = 300
            settings.valkey_cache_ttl_not_found_seconds = 60
            settings.cache_circuit_breaker_timeout_seconds = 30
            settings.cache_mset_batch_size = 10000
            settings.fallback_cache_max_entries = 1024
            mock.return_value = settings
            yield settings

    def test_init_reads_settings(self, mock_settings):
        config = TTLConfig()
        assert config.valkey_cache_ttl == 300

    def test_get_effective_ttl_returns_default(self, mock_settings):
        config = TTLConfig()
        assert config.get_effective_ttl(None) == 300

    def test_get_effective_ttl_returns_override(self, mock_settings):
        config = TTLConfig()
        assert config.get_effective_ttl(10) == 10

    def test_get_effective_stale_ttl(self, mock_settings):
        config = TTLConfig()
        assert config.get_effective_stale_ttl(None) is None
        assert config.get_effective_stale_ttl(50) == 50

    def test_reads_fallback_cache_max_entries(self, mock_settings):
        config = TTLConfig()
        assert config.fallback_cache_max_entries == 1024


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def config(self):
        c = Mock(spec=TTLConfig)
        c.circuit_breaker_timeout = 0.1
        return c

    @pytest.fixture
    def breaker(self, config):
        return CircuitBreaker(config)

    def test_initial_state_closed(self, breaker):
        assert not breaker.is_open()

    def test_open_circuit(self, breaker):
        breaker.open()
        assert breaker.is_open()

    def test_close_circuit(self, breaker):
        breaker.open()
        breaker.close()
        assert not breaker.is_open()

    def test_recovery_timeout(self, breaker, monkeypatch):
        now = 1000.0
        monkeypatch.setattr("app.services.cache.time.monotonic", lambda: now)
        breaker.open()
        assert breaker.is_open()
        now += 0.15
        assert not breaker.is_open()

    def test_protect_returns_none_when_open(self, breaker):
        breaker.open()
        result = breaker.protect(lambda: "success")()
        assert result is None

    def test_protect_returns_result_when_closed(self, breaker):
        result = breaker.protect(lambda: "success")()
        assert result == "success"

    def test_protect_opens_on_exception(self, breaker):
        def failing():
            raise ValueError("fail")

        result = breaker.protect(failing)()
        assert result is None
        assert breaker.is_open()


class TestFallbackCache:
    @pytest.fixture
    def clock(self, monkeypatch):
        now = {"value": 1000.0}
        monkeypatch.setattr("app.services.cache.time.monotonic", lambda: now["value"])
        return now

    @pytest.fixture
    def cache(self):
        return FallbackCache(max_entries=3)

    @pytest.mark.asyncio
    async def test_set_evicts_oldest_entry_when_over_capacity(self, cache, clock):
        await cache.set("k1", "v1", ttl_seconds=60)
        await cache.set("k2", "v2", ttl_seconds=60)
        await cache.set("k3", "v3", ttl_seconds=60)
        await cache.set("k4", "v4", ttl_seconds=60)

        assert await cache.get("k1") is None
        assert await cache.get("k2") == "v2"
        assert await cache.get("k3") == "v3"
        assert await cache.get("k4") == "v4"

    @pytest.mark.asyncio
    async def test_set_clears_expired_entries_before_size_eviction(self, clock):
        short_lived = FallbackCache(max_entries=2)

        await short_lived.set("k1", "v1", ttl_seconds=1)
        await short_lived.set("k2", "v2", ttl_seconds=60)

        clock["value"] += 2.0
        await short_lived.set("k3", "v3", ttl_seconds=60)

        assert await short_lived.get("k1") is None
        assert await short_lived.get("k2") == "v2"
        assert await short_lived.get("k3") == "v3"

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_expired_entries(self, cache, clock):
        await cache.set("k1", "v1", ttl_seconds=1)
        await cache.set("k2", "v2", ttl_seconds=60)

        clock["value"] += 2.0
        await cache.cleanup_expired()

        assert await cache.get("k1") is None
        assert await cache.get("k2") == "v2"
