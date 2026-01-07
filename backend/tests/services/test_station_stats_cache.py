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

    # Mock the DB result
    mock_result = MagicMock()
    mock_result.all.return_value = []
    station_stats_service._session.execute = AsyncMock(return_value=mock_result)

    await station_stats_service.get_station_stats("stop_123", "24h")

    mock_cache.get_json.assert_called()
    mock_cache.set_json.assert_called()
    key = mock_cache.set_json.call_args[0][0]
    assert key == "station_stats:stop_123:24h"


@pytest.mark.asyncio
async def test_network_averages_cached_separately(station_stats_service, mock_cache):
    """Network averages should have their own cache entry."""
    mock_cache.get_json.return_value = None

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
