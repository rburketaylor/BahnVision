from __future__ import annotations

from app.core.database import get_session
from app.services.cache import get_cache_service


def test_health_endpoint_returns_ok(api_client):
    """Test health endpoint returns 200 with status ok, version, and uptime."""
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))


def test_health_endpoint_no_side_effects(api_client):
    """Test health endpoint is idempotent and returns consistent structure."""
    # Call health endpoint multiple times
    for _ in range(3):
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data


def test_ready_endpoint_returns_ready(api_client):
    """Readiness should return ready when DB/cache checks pass."""
    response = api_client.get("/api/v1/ready")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "ok"
    assert data["errors"] == {}


def test_ready_endpoint_returns_503_when_db_unavailable(api_client):
    """Readiness should fail when DB check fails."""

    class _FailingSession:
        async def execute(self, _stmt):
            raise RuntimeError("db unavailable")

    api_client.app.dependency_overrides[get_session] = lambda: _FailingSession()

    response = api_client.get("/api/v1/ready")
    assert response.status_code == 503

    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "error"
    assert data["checks"]["cache"] == "ok"
    assert "database" in data["errors"]


def test_ready_endpoint_returns_503_when_cache_unavailable(api_client):
    """Readiness should fail when cache check fails."""

    class _FailingCache:
        async def get_json(self, _key: str):
            raise RuntimeError("cache unavailable")

    api_client.app.dependency_overrides[get_cache_service] = lambda: _FailingCache()

    response = api_client.get("/api/v1/ready")
    assert response.status_code == 503

    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "error"
    assert "cache" in data["errors"]
