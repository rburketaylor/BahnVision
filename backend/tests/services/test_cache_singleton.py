from app.services.cache import get_cache_service


def test_cache_service_is_singleton():
    """CacheService should be a singleton to preserve state."""
    service1 = get_cache_service()
    service2 = get_cache_service()
    assert service1 is service2
