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
