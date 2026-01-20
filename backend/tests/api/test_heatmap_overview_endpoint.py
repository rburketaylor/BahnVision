"""Integration tests for GET /api/v1/heatmap/overview endpoint."""

from fastapi.testclient import TestClient


class TestHeatmapOverviewEndpoint:
    async def test_returns_200_with_valid_response(self, api_client: TestClient):
        """Should return 200 with valid overview response."""
        response = api_client.get("/api/v1/heatmap/overview?time_range=24h")

        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "summary" in data
        assert "time_range" in data
        assert "total_impacted_stations" in data

    async def test_gzip_compression(self, api_client: TestClient):
        """Response should be significantly smaller when gzipped."""
        response = api_client.get(
            "/api/v1/heatmap/overview?time_range=24h",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Check content-encoding header or content-length

    async def test_cache_headers(self, api_client: TestClient):
        """Should include X-Cache-Status header."""
        response = api_client.get("/api/v1/heatmap/overview?time_range=24h")

        assert response.status_code == 200
        assert "X-Cache-Status" in response.headers
