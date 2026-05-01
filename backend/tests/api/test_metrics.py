from prometheus_client import CONTENT_TYPE_LATEST


def test_metrics_endpoint_returns_200(api_client):
    """Test that /metrics endpoint is accessible and returns 200."""
    response = api_client.get("/metrics")
    assert response.status_code == 200


def test_metrics_content_type(api_client):
    """Test that /metrics returns Prometheus content type."""
    response = api_client.get("/metrics")
    assert response.headers["content-type"] == CONTENT_TYPE_LATEST


def test_metrics_contains_bahnvision_metrics(api_client):
    """Test that /metrics response contains expected metric names."""
    api_client.get("/api/v1/health")
    response = api_client.get("/metrics")
    body = response.text

    # Check for key BahnVision metrics
    assert "bahnvision_cache_events_total" in body
    assert "bahnvision_api_request_duration_seconds" in body


def test_api_responses_include_server_timing(api_client):
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["Server-Timing"].startswith("app;dur=")


def test_error_responses_include_server_timing_and_request_id(api_client):
    response = api_client.get(
        "/api/v1/does-not-exist", headers={"X-Request-Id": "external-id"}
    )

    assert response.status_code == 404
    assert "app;dur=" in response.headers["Server-Timing"]
    assert response.headers["X-Request-Id"] == "external-id"
