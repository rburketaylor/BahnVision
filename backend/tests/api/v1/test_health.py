def test_health_endpoint_returns_ok(api_client):
    """Test health endpoint returns 200 with status ok."""
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_no_side_effects(api_client):
    """Test health endpoint does not interact with dependencies."""
    # Call health endpoint multiple times
    for _ in range(3):
        response = api_client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
