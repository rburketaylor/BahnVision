from datetime import datetime, timezone

import pytest

from app.models.mvg import DeparturesResponse, RouteResponse, StationSearchResponse
from tests.api.conftest import CacheScenario, MVGClientScenario


# ========== Departures Endpoint Tests ==========


def test_departures_cache_hit(api_client, fake_cache):
    """Test departures endpoint with cache hit scenario."""
    cached_payload = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "departures": [
            {
                "planned_time": "2025-01-15T10:00:00Z",
                "realtime_time": "2025-01-15T10:02:00Z",
                "delay_minutes": 2,
                "platform": "1",
                "realtime": True,
                "line": "U3",
                "destination": "Fürstenried West",
                "transport_type": "UBAHN",
                "icon": "mdi-subway",
                "cancelled": False,
                "messages": [],
            }
        ],
    }
    fake_cache.configure(
        "mvg:departures:marienplatz:10:0:all", CacheScenario(fresh_value=cached_payload)
    )

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "hit"

    # Validate response structure
    data = response.json()
    validated = DeparturesResponse.model_validate(data)
    assert validated.station.name == "Marienplatz"
    assert len(validated.departures) == 1


def test_departures_stale_refresh(api_client, fake_cache, fake_mvg_client):
    """Test departures endpoint with stale-refresh workflow."""
    stale_payload = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "departures": [
            {
                "planned_time": "2025-01-15T09:00:00Z",
                "realtime_time": "2025-01-15T09:00:00Z",
                "delay_minutes": 0,
                "platform": "1",
                "realtime": False,
                "line": "U3",
                "destination": "Fürstenried West",
                "transport_type": "UBAHN",
                "icon": "mdi-subway",
                "cancelled": False,
                "messages": [],
            }
        ],
    }
    fake_cache.configure(
        "mvg:departures:marienplatz:10:0:all", CacheScenario(stale_value=stale_payload)
    )

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "stale-refresh"

    # Verify background refresh would have been scheduled
    # (We can't directly test background tasks in TestClient, but the response validates the flow)
    data = response.json()
    validated = DeparturesResponse.model_validate(data)
    assert validated.station.name == "Marienplatz"


def test_departures_cache_miss(api_client, fake_cache, fake_mvg_client):
    """Test departures endpoint with cache miss and fresh fetch."""
    # No cache configured, should fetch from MVG client
    fake_cache.configure("mvg:departures:marienplatz:10:0:all", CacheScenario())

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "miss"

    # Verify MVG client was called
    assert fake_mvg_client.call_count_departures == 1

    # Verify cache was updated
    assert len(fake_cache.recorded_sets) > 0


def test_departures_validation_error_invalid_transport(api_client):
    """Test departures endpoint with invalid transport_type parameter."""
    response = api_client.get(
        "/api/v1/mvg/departures?station=Marienplatz&transport_type=invalid_type"
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_departures_station_not_found(api_client, fake_cache, fake_mvg_client):
    """Test departures endpoint when station is not found."""
    scenario = MVGClientScenario(not_found_station=True)
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:departures:unknown:10:0:all", CacheScenario())

    response = api_client.get("/api/v1/mvg/departures?station=unknown")
    assert response.status_code == 404
    assert "X-Cache-Status" not in response.headers or response.headers["X-Cache-Status"] != "hit"


def test_departures_mvg_service_error(api_client, fake_cache, fake_mvg_client):
    """Test departures endpoint when MVG service fails."""
    scenario = MVGClientScenario(fail_departures=True)
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:departures:marienplatz:10:0:all", CacheScenario())

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 502
    assert "Failed to retrieve departures" in response.json()["detail"]


def test_departures_lock_timeout_with_stale(api_client, fake_cache):
    """Test departures endpoint when stale data is available initially.

    When stale data exists at the first check, endpoint returns it immediately
    with stale-refresh status rather than attempting lock acquisition.
    """
    stale_payload = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "departures": [],
    }
    fake_cache.configure(
        "mvg:departures:marienplatz:10:0:all", CacheScenario(stale_value=stale_payload)
    )

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "stale-refresh"


def test_departures_lock_timeout_no_stale(api_client, fake_cache):
    """Test departures endpoint when lock timeout occurs without stale data."""
    fake_cache.configure("mvg:departures:marienplatz:10:0:all", CacheScenario())
    fake_cache.set_lock_timeout(True)

    response = api_client.get("/api/v1/mvg/departures?station=Marienplatz")
    assert response.status_code == 503
    assert "Timed out" in response.json()["detail"]


@pytest.mark.parametrize(
    "transport_filter,expected_segment",
    [
        (["UBAHN"], "UBAHN"),
        (["SBAHN", "UBAHN"], "SBAHN-UBAHN"),
        ([], "all"),
    ],
)
def test_departures_transport_filters(api_client, fake_cache, transport_filter, expected_segment):
    """Test departures endpoint with various transport type filters."""
    cache_key = f"mvg:departures:marienplatz:10:0:{expected_segment.lower()}"
    cached_payload = {
        "station": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "departures": [],
    }
    fake_cache.configure(cache_key, CacheScenario(fresh_value=cached_payload))

    params = "station=Marienplatz"
    for t in transport_filter:
        params += f"&transport_type={t}"

    response = api_client.get(f"/api/v1/mvg/departures?{params}")
    assert response.status_code == 200


# ========== Route Planning Endpoint Tests ==========


def test_route_cache_hit(api_client, fake_cache):
    """Test route endpoint with cache hit scenario."""
    cached_payload = {
        "origin": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "destination": {
            "id": "de:09162:70",
            "name": "Hauptbahnhof",
            "place": "München",
            "latitude": 48.140,
            "longitude": 11.558,
        },
        "plans": [
            {
                "duration_minutes": 10,
                "transfers": 0,
                "departure": {
                    "id": "de:09162:6",
                    "name": "Marienplatz",
                    "place": "München",
                    "latitude": 48.137,
                    "longitude": 11.575,
                    "planned_time": "2025-01-15T10:00:00Z",
                    "realtime_time": "2025-01-15T10:00:00Z",
                    "platform": "1",
                    "transport_type": "UBAHN",
                    "line": "U4",
                    "destination": "Westendstraße",
                    "delay_minutes": 0,
                    "messages": [],
                },
                "arrival": {
                    "id": "de:09162:70",
                    "name": "Hauptbahnhof",
                    "place": "München",
                    "latitude": 48.140,
                    "longitude": 11.558,
                    "planned_time": "2025-01-15T10:10:00Z",
                    "realtime_time": "2025-01-15T10:10:00Z",
                    "platform": "2",
                    "transport_type": "UBAHN",
                    "line": "U4",
                    "destination": "Westendstraße",
                    "delay_minutes": 0,
                    "messages": [],
                },
                "legs": [],
            }
        ],
    }
    fake_cache.configure(
        "mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario(fresh_value=cached_payload)
    )

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "hit"

    data = response.json()
    validated = RouteResponse.model_validate(data)
    assert validated.origin.name == "Marienplatz"
    assert validated.destination.name == "Hauptbahnhof"


def test_route_stale_refresh(api_client, fake_cache):
    """Test route endpoint with stale-refresh workflow."""
    stale_payload = {
        "origin": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "destination": {
            "id": "de:09162:70",
            "name": "Hauptbahnhof",
            "place": "München",
            "latitude": 48.140,
            "longitude": 11.558,
        },
        "plans": [],
    }
    fake_cache.configure(
        "mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario(stale_value=stale_payload)
    )

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "stale-refresh"


def test_route_cache_miss(api_client, fake_cache, fake_mvg_client):
    """Test route endpoint with cache miss."""
    fake_cache.configure("mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario())

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "miss"
    assert fake_mvg_client.call_count_route == 1


def test_route_mutually_exclusive_times(api_client):
    """Test route endpoint rejects both departure_time and arrival_time."""
    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
        "&departure_time=2025-01-15T10:00:00Z&arrival_time=2025-01-15T11:00:00Z"
    )
    assert response.status_code == 422
    assert "either departure_time or arrival_time" in response.json()["detail"].lower()


def test_route_not_found(api_client, fake_cache, fake_mvg_client):
    """Test route endpoint when no route is available."""
    scenario = MVGClientScenario(not_found_route=True)
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario())

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 404

    # Verify not-found was written to cache
    assert len(fake_cache.recorded_sets) > 0
    for written_key, written_value, _, _ in fake_cache.recorded_sets:
        if written_key == "mvg:route:marienplatz:hauptbahnhof:now:all":
            assert written_value.get("__status") == "not_found"
            break
    else:  # pragma: no cover - defensive guard for future regressions
        raise AssertionError("route cache write not recorded")


def test_route_service_error(api_client, fake_cache, fake_mvg_client):
    """Test route endpoint when MVG service fails."""
    scenario = MVGClientScenario(fail_route=True)
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario())

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 502


def test_route_lock_timeout(api_client, fake_cache):
    """Test route endpoint with lock timeout and no stale data."""
    fake_cache.configure("mvg:route:marienplatz:hauptbahnhof:now:all", CacheScenario())
    fake_cache.set_lock_timeout(True)

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof"
    )
    assert response.status_code == 503


def test_route_transport_filter_parsing(api_client, fake_cache):
    """Test route endpoint accepts transport filters."""
    cached_payload = {
        "origin": {
            "id": "de:09162:6",
            "name": "Marienplatz",
            "place": "München",
            "latitude": 48.137,
            "longitude": 11.575,
        },
        "destination": {
            "id": "de:09162:70",
            "name": "Hauptbahnhof",
            "place": "München",
            "latitude": 48.140,
            "longitude": 11.558,
        },
        "plans": [],
    }
    fake_cache.configure(
        "mvg:route:marienplatz:hauptbahnhof:now:ubahn", CacheScenario(fresh_value=cached_payload)
    )

    response = api_client.get(
        "/api/v1/mvg/routes/plan?origin=Marienplatz&destination=Hauptbahnhof&transport_type=UBAHN"
    )
    assert response.status_code == 200


# ========== Station Search Endpoint Tests ==========


def test_station_search_cache_hit(api_client, fake_cache):
    """Test station search endpoint with cache hit."""
    cached_payload = {
        "query": "Marienplatz",
        "results": [
            {
                "id": "de:09162:6",
                "name": "Marienplatz",
                "place": "München",
                "latitude": 48.137,
                "longitude": 11.575,
            }
        ],
    }
    fake_cache.configure(
        "mvg:stations:search:marienplatz:8", CacheScenario(fresh_value=cached_payload)
    )

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "hit"

    data = response.json()
    validated = StationSearchResponse.model_validate(data)
    assert validated.query == "Marienplatz"
    assert len(validated.results) == 1


def test_station_search_stale_refresh(api_client, fake_cache):
    """Test station search with stale-refresh workflow."""
    stale_payload = {
        "query": "Marienplatz",
        "results": [
            {
                "id": "de:09162:6",
                "name": "Marienplatz",
                "place": "München",
                "latitude": 48.137,
                "longitude": 11.575,
            }
        ],
    }
    fake_cache.configure(
        "mvg:stations:search:marienplatz:8", CacheScenario(stale_value=stale_payload)
    )

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "stale-refresh"


def test_station_search_cache_miss(api_client, fake_cache, fake_mvg_client):
    """Test station search with fresh fetch."""
    fake_cache.configure("mvg:stations:search:marienplatz:8", CacheScenario())

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "miss"
    assert fake_mvg_client.call_count_station_list == 1


def test_station_search_not_found(api_client, fake_cache, fake_mvg_client):
    """Test station search when no stations match."""
    scenario = MVGClientScenario(station_search_result=[])
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:stations:search:unknown:8", CacheScenario())

    response = api_client.get("/api/v1/mvg/stations/search?query=unknown")
    assert response.status_code == 404

    # Verify not-found marker was cached
    assert len(fake_cache.recorded_sets) > 0
    for written_key, written_value, _, _ in fake_cache.recorded_sets:
        if written_key == "mvg:stations:search:unknown:8":
            assert written_value.get("__status") == "not_found"
            break
    else:  # pragma: no cover - defensive guard for future regressions
        raise AssertionError("station search cache write not recorded")


def test_station_search_service_error(api_client, fake_cache, fake_mvg_client):
    """Test station search when MVG service fails."""
    scenario = MVGClientScenario(fail_station_list=True)
    fake_mvg_client.configure(scenario)
    fake_cache.configure("mvg:stations:search:marienplatz:8", CacheScenario())

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 502


def test_station_search_lock_timeout_with_stale(api_client, fake_cache):
    """Test station search when stale data is available initially.

    When stale data exists at the first check, endpoint returns it immediately
    with stale-refresh status rather than attempting lock acquisition.
    """
    stale_payload = {"query": "Marienplatz", "results": []}
    fake_cache.configure(
        "mvg:stations:search:marienplatz:8", CacheScenario(stale_value=stale_payload)
    )

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 200
    assert response.headers["X-Cache-Status"] == "stale-refresh"


def test_station_search_lock_timeout_no_stale(api_client, fake_cache):
    """Test station search with lock timeout and no stale data."""
    fake_cache.configure("mvg:stations:search:marienplatz:8", CacheScenario())
    fake_cache.set_lock_timeout(True)

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz")
    assert response.status_code == 503


def test_station_search_custom_limit(api_client, fake_cache):
    """Test station search with custom limit parameter."""
    cached_payload = {"query": "Marienplatz", "results": []}
    fake_cache.configure(
        "mvg:stations:search:marienplatz:15", CacheScenario(fresh_value=cached_payload)
    )

    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz&limit=15")
    assert response.status_code == 200


def test_station_search_validates_limit_bounds(api_client):
    """Test station search validates limit parameter bounds."""
    # Test limit too high
    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz&limit=100")
    assert response.status_code == 422

    # Test limit too low
    response = api_client.get("/api/v1/mvg/stations/search?query=Marienplatz&limit=0")
    assert response.status_code == 422
