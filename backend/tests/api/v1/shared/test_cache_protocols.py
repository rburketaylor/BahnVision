"""Tests for API cache protocols and cache manager."""

from __future__ import annotations

import pytest

from app.api.v1.shared.cache_protocols import CacheResult, CacheRefreshProtocol


class TestCacheResult:
    """Tests for CacheResult container class."""

    def test_cache_result_default_values(self):
        """Test CacheResult with default values."""
        result = CacheResult()

        assert result.data is None
        assert result.status == "miss"
        assert result.headers == {}

    def test_cache_result_with_data(self):
        """Test CacheResult with data."""
        data = {"key": "value"}
        result = CacheResult(data=data, status="hit")

        assert result.data == data
        assert result.status == "hit"

    def test_cache_result_with_headers(self):
        """Test CacheResult with custom headers."""
        headers = {"X-Cache-Status": "hit", "X-Cache-Age": "100"}
        result = CacheResult(data=None, status="stale", headers=headers)

        assert result.headers["X-Cache-Status"] == "hit"
        assert result.headers["X-Cache-Age"] == "100"
        assert result.status == "stale"

    def test_cache_result_headers_defaults_to_empty_dict(self):
        """Test that headers defaults to empty dict, not None."""
        result = CacheResult(data="test", status="hit")

        assert isinstance(result.headers, dict)
        assert len(result.headers) == 0


class TestCacheRefreshProtocol:
    """Tests for CacheRefreshProtocol abstract base class."""

    def test_protocol_is_abstract(self):
        """Test that CacheRefreshProtocol cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CacheRefreshProtocol()

    def test_protocol_requires_fetch_data(self):
        """Test that subclass must implement fetch_data."""

        class IncompleteProtocol(CacheRefreshProtocol):
            async def store_data(self, cache, cache_key, data, settings):
                pass

            def cache_name(self):
                return "test"

            def get_model_class(self):
                return dict

        with pytest.raises(TypeError):
            IncompleteProtocol()

    def test_protocol_requires_cache_name(self):
        """Test that subclass must implement cache_name."""

        class IncompleteProtocol(CacheRefreshProtocol):
            async def fetch_data(self, **kwargs):
                return {}

            async def store_data(self, cache, cache_key, data, settings):
                pass

            def get_model_class(self):
                return dict

        with pytest.raises(TypeError):
            IncompleteProtocol()
