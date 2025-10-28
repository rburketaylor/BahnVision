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
    response = api_client.get("/metrics")
    body = response.text

    # Check for key BahnVision metrics
    assert "bahnvision_cache_events_total" in body
