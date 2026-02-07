import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from app.services.transit_data import TransitDataService


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get_json = AsyncMock(return_value=None)
    cache.get_stale_json = AsyncMock(return_value=None)
    cache.set_json = AsyncMock(return_value=True)
    cache.mget_json = AsyncMock(return_value={})
    return cache


@pytest.fixture
def transit_data_service(mock_cache):
    service = TransitDataService(
        cache_service=mock_cache,
        gtfs_schedule=AsyncMock(),
        gtfs_realtime=AsyncMock(),
        db_session=AsyncMock(),
    )
    return service


@pytest.mark.asyncio
async def test_departures_uses_stale_fallback(transit_data_service, mock_cache):
    """Should return stale data when fresh cache miss."""
    mock_cache.get_json.return_value = None  # Fresh miss
    # Mock data that from_dict can handle
    stale_data = [
        {
            "trip_id": "1",
            "route_id": "A",
            "route_short_name": "A",
            "route_long_name": "Route A",
            "trip_headsign": "Dest",
            "stop_id": "stop_1",
            "stop_name": "Stop 1",
            "scheduled_departure": datetime.now(timezone.utc).isoformat(),
            "schedule_relationship": "SCHEDULED",
        }
    ]
    mock_cache.get_stale_json.return_value = stale_data  # Stale hit

    result = await transit_data_service.get_departures_for_stop("stop_1")

    assert len(result) == 1
    assert result[0].trip_id == "1"
    mock_cache.get_stale_json.assert_called_once()


@pytest.mark.asyncio
async def test_departures_cache_key_no_time_bucket(transit_data_service, mock_cache):
    """Cache key should not include time bucket."""
    mock_cache.get_json.return_value = None

    # Mock dependencies to avoid errors
    transit_data_service.gtfs_schedule.get_departures_for_stop = AsyncMock(
        return_value=[]
    )

    await transit_data_service.get_departures_for_stop("stop_1", limit=10)

    # Check any call to get_json
    key = mock_cache.get_json.call_args[0][0]
    # Expected: departures:stop_1:10:0:none:True
    assert key == "departures:stop_1:10:0:none:True"
