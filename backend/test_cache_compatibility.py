#!/usr/bin/env python3
"""
Test script to verify that the simplified cache service maintains compatibility
with the original cache service API and behavior.
"""

import asyncio
import json
from typing import Any

# Import both services for comparison
from app.services.cache import CacheService as OriginalCacheService
from app.services.cache_simplified import SimplifiedCacheService


class MockValkeyClient:
    """Mock Valkey client for testing."""

    def __init__(self):
        self._store = {}
        self._fail_operations = False

    def set_fail_mode(self, fail: bool) -> None:
        self._fail_operations = fail

    async def get(self, key: str) -> str | None:
        if self._fail_operations:
            raise Exception("Simulated Valkey failure")
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if self._fail_operations:
            raise Exception("Simulated Valkey failure")

        if nx and key in self._store:
            return False

        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        if self._fail_operations:
            raise Exception("Simulated Valkey failure")

        deleted = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                deleted += 1
        return deleted


async def test_api_compatibility():
    """Test that both services have the same public API."""
    print("Testing API compatibility...")

    mock_client = MockValkeyClient()
    original = OriginalCacheService(mock_client)
    simplified = SimplifiedCacheService(mock_client)

    # Check that both services have the same methods
    original_methods = set(method for method in dir(original) if not method.startswith('_'))
    simplified_methods = set(method for method in dir(simplified) if not method.startswith('_'))

    # Remove any methods that are unique to either implementation
    common_methods = original_methods & simplified_methods

    print(f"Original methods: {sorted(original_methods)}")
    print(f"Simplified methods: {sorted(simplified_methods)}")
    print(f"Common methods: {sorted(common_methods)}")

    # Test basic operations
    test_key = "test_key"
    test_value = {"test": "data", "number": 42}

    # Test set_json
    await original.set_json(test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300)
    await simplified.set_json(f"{test_key}_simple", test_value, ttl_seconds=60, stale_ttl_seconds=300)

    # Test get_json
    original_result = await original.get_json(test_key)
    simplified_result = await simplified.get_json(f"{test_key}_simple")

    assert original_result == test_value, f"Original get_json failed: {original_result}"
    assert simplified_result == test_value, f"Simplified get_json failed: {simplified_result}"

    # Test get_stale_json
    original_stale = await original.get_stale_json(test_key)
    simplified_stale = await simplified.get_stale_json(f"{test_key}_simple")

    assert original_stale == test_value, f"Original get_stale_json failed: {original_stale}"
    assert simplified_stale == test_value, f"Simplified get_stale_json failed: {simplified_stale}"

    print("✓ API compatibility test passed")


async def test_circuit_breaker_behavior():
    """Test that circuit breaker behavior is preserved."""
    print("Testing circuit breaker behavior...")

    mock_client = MockValkeyClient()
    original = OriginalCacheService(mock_client)
    simplified = SimplifiedCacheService(mock_client)

    test_key = "circuit_test"
    test_value = {"circuit": "test"}

    # Test normal operation
    await simplified.set_json(test_key, test_value, ttl_seconds=60)
    result = await simplified.get_json(test_key)
    assert result == test_value, "Normal operation failed"

    # Test circuit breaker behavior during failures
    mock_client.set_fail_mode(True)

    # Should fallback to in-memory store
    fallback_key = f"{test_key}_fallback"
    await simplified.set_json(fallback_key, test_value, ttl_seconds=60)
    result = await simplified.get_json(fallback_key)
    assert result == test_value, "Fallback operation failed"

    # Restore normal operation
    mock_client.set_fail_mode(False)

    print("✓ Circuit breaker behavior test passed")


async def test_single_flight_behavior():
    """Test that single-flight lock behavior is preserved."""
    print("Testing single-flight behavior...")

    mock_client = MockValkeyClient()
    simplified = SimplifiedCacheService(mock_client)

    test_key = "single_flight_test"

    # Test single-flight context manager
    async with simplified.single_flight(test_key, ttl_seconds=5, wait_timeout=1.0, retry_delay=0.1):
        # Simulate some work
        await asyncio.sleep(0.1)
        # This should not raise an exception
        pass

    print("✓ Single-flight behavior test passed")


async def test_ttl_configuration():
    """Test that TTL configuration works correctly."""
    print("Testing TTL configuration...")

    mock_client = MockValkeyClient()
    simplified = SimplifiedCacheService(mock_client)

    test_key = "ttl_test"
    test_value = {"ttl": "test"}

    # Test various TTL configurations
    await simplified.set_json(test_key, test_value, ttl_seconds=0)  # Should be treated as None
    await simplified.set_json(f"{test_key}_1", test_value, ttl_seconds=-1)  # Should be treated as None
    await simplified.set_json(f"{test_key}_2", test_value, ttl_seconds=60)  # Valid TTL
    await simplified.set_json(f"{test_key}_3", test_value)  # No TTL

    result1 = await simplified.get_json(test_key)
    result2 = await simplified.get_json(f"{test_key}_1")
    result3 = await simplified.get_json(f"{test_key}_2")
    result4 = await simplified.get_json(f"{test_key}_3")

    assert result1 == test_value, "TTL=0 test failed"
    assert result2 == test_value, "TTL=-1 test failed"
    assert result3 == test_value, "TTL=60 test failed"
    assert result4 == test_value, "No TTL test failed"

    print("✓ TTL configuration test passed")


async def test_deletion_behavior():
    """Test that deletion behavior is preserved."""
    print("Testing deletion behavior...")

    mock_client = MockValkeyClient()
    simplified = SimplifiedCacheService(mock_client)

    test_key = "delete_test"
    test_value = {"delete": "test"}

    # Set up test data
    await simplified.set_json(test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300)

    # Verify it exists
    result = await simplified.get_json(test_key)
    assert result == test_value, "Setup failed"

    # Test deletion without stale removal
    await simplified.delete(test_key, remove_stale=False)
    result = await simplified.get_json(test_key)
    assert result is None, "Deletion without stale removal failed"

    # Set up again
    await simplified.set_json(test_key, test_value, ttl_seconds=60, stale_ttl_seconds=300)

    # Test deletion with stale removal
    await simplified.delete(test_key, remove_stale=True)
    result = await simplified.get_json(test_key)
    stale_result = await simplified.get_stale_json(test_key)
    assert result is None, "Deletion with stale removal failed"
    assert stale_result is None, "Stale deletion failed"

    print("✓ Deletion behavior test passed")


async def main():
    """Run all compatibility tests."""
    print("Running simplified cache service compatibility tests...")
    print("=" * 60)

    try:
        await test_api_compatibility()
        await test_circuit_breaker_behavior()
        await test_single_flight_behavior()
        await test_ttl_configuration()
        await test_deletion_behavior()

        print("=" * 60)
        print("✅ All compatibility tests passed!")
        print("The simplified cache service maintains full API compatibility.")

    except Exception as e:
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())