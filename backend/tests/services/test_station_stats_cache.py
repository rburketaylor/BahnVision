import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.station_stats_service import StationStatsService


@pytest.fixture
def mock_cache():
    return AsyncMock()


@pytest.fixture
def mock_gtfs_schedule():
    schedule = AsyncMock()
    # Mock stop info
    mock_stop = MagicMock()
    mock_stop.stop_name = "Test Station"
    schedule.get_stop_by_id = AsyncMock(return_value=mock_stop)
    return schedule


@pytest.fixture
def station_stats_service(mock_gtfs_schedule, mock_cache):
    return StationStatsService(
        session=AsyncMock(), gtfs_schedule=mock_gtfs_schedule, cache=mock_cache
    )


@pytest.mark.asyncio
async def test_station_stats_caches_result(station_stats_service, mock_cache):
    """Station stats should be cached."""
    mock_cache.get_json.return_value = None
    mock_cache.get_stale_json.return_value = None
    mock_cache.get.return_value = None  # Station name cache miss

    # Mock the DB result
    mock_result = MagicMock()
    mock_result.all.return_value = []
    station_stats_service._session.execute = AsyncMock(return_value=mock_result)

    await station_stats_service.get_station_stats("stop_123", "24h")

    mock_cache.get_json.assert_called()
    mock_cache.set_json.assert_called()
    key = mock_cache.set_json.call_args[0][0]
    assert (
        key == "station_stats:stop_123:24h:60:1"
    )  # includes bucket_width_minutes + include_network_averages


@pytest.mark.asyncio
async def test_network_averages_cached_separately(station_stats_service, mock_cache):
    """Network averages should have their own cache entry."""
    mock_cache.get_json.return_value = None
    mock_cache.get_stale_json.return_value = None
    mock_cache.get.return_value = None  # Station name cache miss

    # Mock DB results with at least one row to trigger network average fetch
    mock_row = MagicMock()
    mock_row.total_departures = 10
    mock_row.cancelled_count = 1
    mock_row.delayed_count = 1
    mock_row.route_type = 3

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    # For _get_network_averages query
    mock_network_row = MagicMock(total=100, cancelled=5, delayed=10)
    mock_result.one_or_none.return_value = mock_network_row

    station_stats_service._session.execute = AsyncMock(return_value=mock_result)

    await station_stats_service.get_station_stats("stop_123", "24h")

    # Should have called get_json for both station_stats AND network_averages
    keys = [call[0][0] for call in mock_cache.get_json.call_args_list]
    assert any("station_stats:" in k for k in keys)
    assert any("network_averages:" in k for k in keys)


@pytest.mark.asyncio
async def test_network_averages_uses_heatmap_overview_cache_fast_path(
    station_stats_service, mock_cache
):
    """Network averages should be derived from heatmap overview cache when available."""
    mock_cache.get.return_value = None  # Station name cache miss
    mock_cache.get_stale_json.return_value = None

    # First get_json calls: station_stats miss + network_averages miss.
    # Then provide a cached heatmap overview response for the fast path.
    heatmap_overview_cached = {
        "time_range": {"from": "2025-01-01T00:00:00Z", "to": "2025-01-02T00:00:00Z"},
        "points": [],
        "summary": {
            "total_stations": 1,
            "total_departures": 100,
            "total_cancellations": 10,
            "overall_cancellation_rate": 0.1,
            "total_delays": 20,
            "overall_delay_rate": 0.2,
            "most_affected_station": None,
            "most_affected_line": None,
        },
        "total_impacted_stations": 0,
    }

    async def get_json_side_effect(key: str):
        if key == "heatmap:overview:24h:all:60":
            return heatmap_overview_cached
        return None

    mock_cache.get_json.side_effect = get_json_side_effect

    # Mock station-level DB query with at least one row (so network averages are needed).
    mock_row = MagicMock()
    mock_row.total_departures = 10
    mock_row.cancelled_count = 1
    mock_row.delayed_count = 1
    mock_row.route_type = 3

    station_query_result = MagicMock()
    station_query_result.all.return_value = [mock_row]

    # If a second DB execute happens (for network averages), fail the test.
    station_stats_service._session.execute = AsyncMock(
        side_effect=[
            station_query_result,
            AssertionError("Should not query DB for network averages"),
        ]
    )

    result = await station_stats_service.get_station_stats("stop_123", "24h")
    # If we got here without triggering the second DB execute, the fast path worked.
    assert result is not None
