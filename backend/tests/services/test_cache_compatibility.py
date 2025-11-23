"""
Test cache service functionality including circuit breaker, single-flight locks, and TTL behavior.
"""

import asyncio

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
    async def test_fallback_store_ttl_expiration(self, cache_service, fake_valkey):
        """Test that fallback store properly handles TTL expiration."""
        test_key = "ttl_expire_test"
        test_value = {"expire": "test"}

        # Simulate Valkey failure to force fallback usage
        fake_valkey.should_fail = True

        # Set with very short TTL
        await cache_service.set_json(test_key, test_value, ttl_seconds=1)

        # Should be available immediately
        result = await cache_service.get_json(test_key)
        assert result == test_value

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired now (note: fallback store cleanup happens on access)
        result = await cache_service.get_json(test_key)
        assert result is None, "Fallback store should have expired the entry"

        # Restore Valkey
        fake_valkey.should_fail = False
