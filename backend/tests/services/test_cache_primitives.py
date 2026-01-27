"""Unit tests for cache primitives."""

import time
from unittest.mock import Mock

from unittest.mock import patch
import pytest

from app.services.cache import CircuitBreaker, TTLConfig
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

    def test_recovery_timeout(self, breaker):
        breaker.open()
        assert breaker.is_open()
        time.sleep(0.15)
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
