from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from app.api.v1.endpoints.mvg.shared import cache_keys
from app.services.cache import CacheService
from app.services.mvg_client import TransportType


def _wait_for_background_tasks() -> None:
    """Give background tasks a brief moment to complete."""
    time.sleep(0.01)


def test_departures_uses_cache_on_repeat_calls(
    api_client: TestClient,
    fake_mvg_client,
) -> None:
    params = {"station": "marienplatz"}

    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "miss"
    assert fake_mvg_client.departure_calls == 1

    cached = api_client.get("/api/v1/mvg/departures", params=params)
    assert cached.status_code == 200
    assert cached.headers["X-Cache-Status"] == "hit"
    assert fake_mvg_client.departure_calls == 1  # served from cache


def test_departures_returns_stale_when_mvg_errors(
    api_client: TestClient,
    cache_service: CacheService,
    fake_mvg_client,
) -> None:
    params = {"station": "marienplatz"}
    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200
    assert fake_mvg_client.departure_calls == 1

    cache_key = cache_keys.departures_cache_key("marienplatz", 10, 0, [])
    asyncio.run(cache_service.delete(cache_key))
    fake_mvg_client.fail_departures = True

    stale_response = api_client.get("/api/v1/mvg/departures", params=params)
    assert stale_response.status_code == 200
    assert stale_response.headers["X-Cache-Status"] == "stale-refresh"
    _wait_for_background_tasks()
    assert fake_mvg_client.departure_calls == 2  # background refresh attempted


def test_departures_served_when_valkey_unavailable(
    api_client: TestClient,
    cache_service: CacheService,
    fake_mvg_client,
) -> None:
    params = {"station": "isartor"}
    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200
    assert fake_mvg_client.departure_calls == 1

    # Simulate Valkey connectivity issues.
    cache_service._client.should_fail = True  # type: ignore[attr-defined]

    cached = api_client.get("/api/v1/mvg/departures", params=params)
    assert cached.status_code == 200
    assert cached.headers["X-Cache-Status"] == "hit"
    assert fake_mvg_client.departure_calls == 1  # no fresh MVG call


def test_route_planner_caches_and_reuses_results(
    api_client: TestClient,
    cache_service: CacheService,
    fake_mvg_client,
) -> None:
    params = {"origin": "marienplatz", "destination": "sendlinger tor"}

    response = api_client.get("/api/v1/mvg/routes/plan", params=params)
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "miss"
    assert fake_mvg_client.route_calls == 1

    cache_service._client.should_fail = True  # type: ignore[attr-defined]

    cached = api_client.get("/api/v1/mvg/routes/plan", params=params)
    assert cached.status_code == 200
    assert cached.headers["X-Cache-Status"] == "hit"
    assert fake_mvg_client.route_calls == 1  # response satisfied via cache


def test_request_id_header_is_always_emitted(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    generated_id = response.headers.get("X-Request-Id")
    assert generated_id is not None and generated_id != ""

    supplied_id = "test-request-id"
    echoed = api_client.get("/api/v1/health", headers={"X-Request-Id": supplied_id})
    assert echoed.status_code == 200
    assert echoed.headers.get("X-Request-Id") == supplied_id


def test_departures_handles_upstream_filter_failures(
    api_client: TestClient,
    fake_mvg_client,
) -> None:
    """Test that upstream failures for specific transport types are handled properly."""
    fake_mvg_client.fail_departures_for.add("BUS")
    params = [
        ("station", "marienplatz"),
        ("transport_type", "UBAHN"),
        ("transport_type", "BUS"),
    ]
    response = api_client.get("/api/v1/mvg/departures", params=params)

    # With the new architecture, upstream failures should result in HTTP errors
    # rather than partial payloads since filtering is done upstream
    assert response.status_code == 502  # Bad Gateway due to MVG error


def test_departures_cache_key_with_no_filters() -> None:
    """Test cache key generation when no transport filters are provided."""
    key = cache_keys.departures_cache_key("Marienplatz", 10, 0, [])
    assert key == "mvg:departures:marienplatz:10:0:all"


def test_departures_cache_key_with_single_filter() -> None:
    """Test cache key generation with a single transport filter."""
    key = cache_keys.departures_cache_key("Marienplatz", 10, 0, [TransportType.UBAHN])
    assert key == "mvg:departures:marienplatz:10:0:UBAHN"


def test_departures_cache_key_with_multiple_filters() -> None:
    """Test cache key generation with multiple transport filters (order-independent)."""
    # Test with different order to ensure sorting works
    filters1 = [TransportType.BUS, TransportType.TRAM]
    filters2 = [TransportType.TRAM, TransportType.BUS]

    key1 = cache_keys.departures_cache_key("Marienplatz", 10, 0, filters1)
    key2 = cache_keys.departures_cache_key("Marienplatz", 10, 0, filters2)

    # Both should generate the same key (sorted)
    assert key1 == key2 == "mvg:departures:marienplatz:10:0:BUS-TRAM"


def test_departures_cache_key_normalizes_station_name() -> None:
    """Test that station names are normalized in cache keys."""
    key1 = cache_keys.departures_cache_key("Marienplatz", 10, 0, [])
    key2 = cache_keys.departures_cache_key("  marienplatz  ", 10, 0, [])

    assert key1 == key2 == "mvg:departures:marienplatz:10:0:all"


def test_departures_filtered_result_count(api_client: TestClient, fake_mvg_client) -> None:
    """Test that filtered requests return up to limit for the requested type."""
    # Request only UBAHN departures with limit 3
    params = [
        ("station", "marienplatz"),
        ("transport_type", "UBAHN"),
        ("limit", "3"),
    ]

    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200

    body = response.json()
    departures = body["departures"]

    # Should return up to 3 UBAHN departures
    assert len(departures) <= 3
    for departure in departures:
        assert departure["transport_type"] == "UBAHN"


def test_departures_upstream_call_args(api_client: TestClient, fake_mvg_client) -> None:
    """Test that transport type filters are passed upstream to MVG client."""
    # Test with no filters
    params_no_filter = {"station": "marienplatz"}
    api_client.get("/api/v1/mvg/departures", params=params_no_filter)
    assert fake_mvg_client.last_departures_call["transport_types"] is None

    # Reset call counter
    fake_mvg_client.departure_calls = 0

    # Test with filters
    params_with_filter = [
        ("station", "marienplatz"),
        ("transport_type", "UBAHN"),
        ("transport_type", "BUS"),
    ]
    api_client.get("/api/v1/mvg/departures", params=params_with_filter)

    transport_types = fake_mvg_client.last_departures_call["transport_types"]
    assert transport_types is not None
    assert len(transport_types) == 2
    # Check that the transport types include UBAHN and BUS (order may vary)
    type_names = {t.name if hasattr(t, 'name') else str(t) for t in transport_types}
    assert "UBAHN" in type_names
    assert "BUS" in type_names


def test_departures_filter_switching_distinct_cache_keys(api_client: TestClient, cache_service: CacheService) -> None:
    """Test that switching filters doesn't serve stale filtered payloads across filters."""
    # First request with UBAHN filter
    params_ubahn = [("station", "marienplatz"), ("transport_type", "UBAHN")]
    response1 = api_client.get("/api/v1/mvg/departures", params=params_ubahn)
    assert response1.status_code == 200
    assert response1.headers["X-Cache-Status"] == "miss"

    # Second request with BUS filter should be a cache miss (different key)
    params_bus = [("station", "marienplatz"), ("transport_type", "BUS")]
    response2 = api_client.get("/api/v1/mvg/departures", params=params_bus)
    assert response2.status_code == 200
    assert response2.headers["X-Cache-Status"] == "miss"  # Different filter = different cache key

    # Third request with same UBAHN filter should be a cache hit
    response3 = api_client.get("/api/v1/mvg/departures", params=params_ubahn)
    assert response3.status_code == 200
    assert response3.headers["X-Cache-Status"] == "hit"

    # Verify responses have different transport types
    body1 = response1.json()
    body2 = response2.json()

    # All departures in first response should be UBAHN
    for departure in body1["departures"]:
        assert departure["transport_type"] == "UBAHN"

    # All departures in second response should be BUS
    for departure in body2["departures"]:
        assert departure["transport_type"] == "BUS"


def test_departures_api_duplicate_filters(api_client: TestClient, fake_mvg_client) -> None:
    """Test that duplicate transport_type parameters are deduplicated."""
    params = [
        ("station", "marienplatz"),
        ("transport_type", "UBAHN"),
        ("transport_type", "UBAHN"),  # Duplicate
    ]

    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200

    # Check that only one TransportType.UBAHN was passed to the client
    transport_types = fake_mvg_client.last_departures_call["transport_types"]
    assert len(transport_types) == 1
    assert transport_types[0] == TransportType.UBAHN

    # Verify response contains only UBAHN departures
    body = response.json()
    for departure in body["departures"]:
        assert departure["transport_type"] == "UBAHN"


def test_departures_api_synonym_duplicates(api_client: TestClient, fake_mvg_client) -> None:
    """Test that synonym transport_type parameters are deduplicated."""
    params = [
        ("station", "marienplatz"),
        ("transport_type", "S-Bahn"),
        ("transport_type", "SBAHN"),  # Synonym
    ]

    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200

    # Check that only one TransportType.SBAHN was passed to the client
    transport_types = fake_mvg_client.last_departures_call["transport_types"]
    assert len(transport_types) == 1
    assert transport_types[0] == TransportType.SBAHN

    # Verify response contains only SBAHN departures
    body = response.json()
    for departure in body["departures"]:
        assert departure["transport_type"] == "SBAHN"

    # Check cache key matches single-filter variant
    from app.api.v1.endpoints.mvg.shared import cache_keys
    expected_cache_key = cache_keys.departures_cache_key("marienplatz", 10, 0, [TransportType.SBAHN])
    # We can't directly verify the cache key from the API response, but we can verify
    # the behavior is consistent by making the same request again and checking for cache hit
    response2 = api_client.get("/api/v1/mvg/departures", params=params)
    assert response2.headers["X-Cache-Status"] == "hit"
