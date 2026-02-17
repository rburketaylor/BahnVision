"""
Test cache service functionality including circuit breaker, single-flight locks, and TTL behavior.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.cache import CacheService


class TestCacheService:
    """Test the cache service implementation."""

    @pytest.fixture
    def cache_service(self, fake_valkey):
        """Create cache service instance for testing."""
        return CacheService(fake_valkey)

    @pytest.mark.asyncio
    async def test_basic_json_operations(self, cache_service):
        """Test basic JSON set/get operations."""
        test_key = "test_key"
        test_value = {"test": "data", "number": 42}

        # Test set and get
        await cache_service.set_json(test_key, test_value, ttl_seconds=60)
        result = await cache_service.get_json(test_key)

        assert result == test_value, f"Expected {test_value}, got {result}"

    @pytest.mark.asyncio
    async def test_stale_cache_operations(self, cache_service):
        """Test stale cache functionality."""
        test_key = "stale_test"
        test_value = {"stale": "data"}

        # Set with stale TTL
        await cache_service.set_json(
            test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300
        )

        # Verify fresh data
        fresh_result = await cache_service.get_json(test_key)
        assert fresh_result == test_value

        # Verify stale data
        stale_result = await cache_service.get_stale_json(test_key)
        assert stale_result == test_value

    @pytest.mark.asyncio
    async def test_ttl_configuration(self, cache_service):
        """Test various TTL configurations."""
        test_key = "ttl_test"
        test_value = {"ttl": "test"}

        # Test TTL=0 (should be treated as None)
        await cache_service.set_json(test_key, test_value, ttl_seconds=0)
        result = await cache_service.get_json(test_key)
        assert result == test_value

        # Test TTL=-1 (should be treated as None)
        await cache_service.set_json(f"{test_key}_1", test_value, ttl_seconds=-1)
        result = await cache_service.get_json(f"{test_key}_1")
        assert result == test_value

        # Test valid TTL
        await cache_service.set_json(f"{test_key}_2", test_value, ttl_seconds=60)
        result = await cache_service.get_json(f"{test_key}_2")
        assert result == test_value

        # Test no TTL
        await cache_service.set_json(f"{test_key}_3", test_value)
        result = await cache_service.get_json(f"{test_key}_3")
        assert result == test_value

    @pytest.mark.asyncio
    async def test_circuit_breaker_behavior(self, cache_service, fake_valkey):
        """Test circuit breaker fallback behavior."""
        test_key = "circuit_test"
        test_value = {"circuit": "test"}

        # Set up data while Valkey is working
        await cache_service.set_json(test_key, test_value, ttl_seconds=60)
        result = await cache_service.get_json(test_key)
        assert result == test_value, "Normal operation failed"

        # Simulate Valkey failure
        fake_valkey.should_fail = True

        # Should fallback to in-memory store
        fallback_key = f"{test_key}_fallback"
        await cache_service.set_json(fallback_key, test_value, ttl_seconds=60)
        result = await cache_service.get_json(fallback_key)
        assert result == test_value, "Fallback operation failed"

        # Restore normal operation
        fake_valkey.should_fail = False

    @pytest.mark.asyncio
    async def test_single_flight_behavior(self, cache_service):
        """Test single-flight lock functionality."""
        test_key = "single_flight_test"

        # Test single-flight context manager
        try:
            async with cache_service.single_flight(
                test_key, ttl_seconds=5, wait_timeout=1.0, retry_delay=0.1
            ):
                # Simulate some work
                await asyncio.sleep(0.01)
                # This should not raise an exception
                pass
        except TimeoutError:
            pytest.fail("Single-flight lock should not timeout in this test")

    @pytest.mark.asyncio
    async def test_single_flight_timeout_does_not_release_existing_lock(
        self, cache_service, fake_valkey
    ):
        """A worker that never acquired the lock must not release it."""
        test_key = "single_flight_timeout"
        await fake_valkey.set(f"{test_key}:lock", "1", ex=30, nx=True)

        with pytest.raises(TimeoutError):
            async with cache_service.single_flight(
                test_key, ttl_seconds=5, wait_timeout=0.02, retry_delay=0.01
            ):
                pass

        assert await fake_valkey.get(f"{test_key}:lock") == "1"

    @pytest.mark.asyncio
    async def test_single_flight_valkey_failure_does_not_attempt_release(self):
        """Valkey acquisition failures should bypass locking without delete calls."""

        class FailingLockClient:
            def __init__(self) -> None:
                self.delete_calls = 0

            async def set(self, *args, **kwargs):
                raise RuntimeError("valkey unavailable")

            async def delete(self, *args):
                self.delete_calls += 1

            async def get(self, key: str):
                return None

        client = FailingLockClient()
        cache_service = CacheService(client)  # type: ignore[arg-type]

        entered = False
        async with cache_service.single_flight(
            "single_flight_valkey_error",
            ttl_seconds=5,
            wait_timeout=0.02,
            retry_delay=0.01,
        ):
            entered = True

        assert entered
        assert client.delete_calls == 0

    @pytest.mark.asyncio
    async def test_set_json_throttles_fallback_cleanup(
        self, cache_service, monkeypatch
    ):
        """Fallback cleanup should be periodic, not on every write."""
        now = 1000.0
        monkeypatch.setattr("app.services.cache.time.monotonic", lambda: now)
        cleanup_mock = AsyncMock()
        cache_service._fallback.cleanup_expired = cleanup_mock  # type: ignore[method-assign]

        await cache_service.set_json("cleanup-1", {"value": 1}, ttl_seconds=30)
        await cache_service.set_json("cleanup-2", {"value": 2}, ttl_seconds=30)
        assert cleanup_mock.await_count == 1

        now += cache_service._FALLBACK_CLEANUP_INTERVAL_SECONDS + 0.1
        await cache_service.set_json("cleanup-3", {"value": 3}, ttl_seconds=30)
        assert cleanup_mock.await_count == 2

    @pytest.mark.asyncio
    async def test_deletion_behavior(self, cache_service):
        """Test cache deletion with and without stale removal."""
        test_key = "delete_test"
        test_value = {"delete": "test"}

        # Set up test data
        await cache_service.set_json(
            test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300
        )

        # Verify it exists
        result = await cache_service.get_json(test_key)
        assert result == test_value, "Setup failed"

        # Test deletion without stale removal
        await cache_service.delete(test_key, remove_stale=False)
        result = await cache_service.get_json(test_key)
        assert result is None, "Deletion without stale removal failed"

        # Set up again
        await cache_service.set_json(
            test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300
        )

        # Test deletion with stale removal
        await cache_service.delete(test_key, remove_stale=True)
        result = await cache_service.get_json(test_key)
        stale_result = await cache_service.get_stale_json(test_key)
        assert result is None, "Deletion with stale removal failed"
        assert stale_result is None, "Stale deletion failed"

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, cache_service):
        """Test that cache misses return None."""
        result = await cache_service.get_json("nonexistent_key")
        assert result is None

        stale_result = await cache_service.get_stale_json("nonexistent_key")
        assert stale_result is None

    @pytest.mark.asyncio
    async def test_json_serialization_edge_cases(self, cache_service):
        """Test JSON serialization with edge cases."""
        test_key = "json_edge_test"

        # Test with complex nested structure
        complex_value = {
            "nested": {"deeply": {"nested": {"value": "complex"}}},
            "array": [1, 2, 3, {"nested": "array"}],
            "null_value": None,
            "boolean": True,
            "number": 42.5,
        }

        await cache_service.set_json(test_key, complex_value)
        result = await cache_service.get_json(test_key)
        assert result == complex_value

    @pytest.mark.asyncio
    async def test_json_serialization_datetime_values(self, cache_service):
        """Cache JSON helpers should handle datetime values without raising."""
        test_key = "json_datetime_test"
        dt = datetime(2026, 1, 27, 12, 34, 56, tzinfo=timezone.utc)

        await cache_service.set_json(test_key, {"at": dt})
        result = await cache_service.get_json(test_key)

        assert result == {"at": dt.isoformat()}

        await cache_service.mset_json({"json_datetime_test_2": {"at": dt}})
        result2 = await cache_service.get_json("json_datetime_test_2")
        assert result2 == {"at": dt.isoformat()}

    @pytest.mark.asyncio
    async def test_fallback_store_ttl_expiration(
        self, cache_service, fake_valkey, monkeypatch
    ):
        """Test that fallback store properly handles TTL expiration."""
        test_key = "ttl_expire_test"
        test_value = {"expire": "test"}

        now = 1000.0
        monkeypatch.setattr("app.services.cache.time.monotonic", lambda: now)

        # Simulate Valkey failure to force fallback usage
        fake_valkey.should_fail = True

        # Set with very short TTL
        await cache_service.set_json(test_key, test_value, ttl_seconds=1)

        # Should be available immediately
        result = await cache_service.get_json(test_key)
        assert result == test_value

        # Advance monotonic clock beyond TTL expiration.
        now += 1.1

        # Should be expired now (note: fallback store cleanup happens on access)
        result = await cache_service.get_json(test_key)
        assert result is None, "Fallback store should have expired the entry"

        # Restore Valkey
        fake_valkey.should_fail = False
