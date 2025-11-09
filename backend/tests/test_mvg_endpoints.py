from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from app.api.v1.endpoints import mvg as mvg_module
from app.services.cache import CacheService


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

    cache_key = mvg_module._departures_cache_key("marienplatz", 10, 0, [])
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


def test_departures_marks_partial_payloads(
    api_client: TestClient,
    fake_mvg_client,
) -> None:
    fake_mvg_client.fail_departures_for.add("BUS")
    params = [
        ("station", "marienplatz"),
        ("transport_type", "ubahn"),
        ("transport_type", "bus"),
    ]
    response = api_client.get("/api/v1/mvg/departures", params=params)
    assert response.status_code == 200
    body = response.json()
    assert body["partial"] is True
    assert response.headers["X-Cache-Status"] == "miss"
