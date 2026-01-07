import pytest
from unittest.mock import AsyncMock
from app.services.gtfs_realtime import GtfsRealtimeService, TripUpdate


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.mset_json = AsyncMock(return_value=None)
    cache.set_json = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def gtfs_realtime_service(mock_cache):
    return GtfsRealtimeService(cache_service=mock_cache)


@pytest.mark.asyncio
async def test_store_trip_updates_uses_batch(gtfs_realtime_service, mock_cache):
    """Trip updates should be stored in batch."""
    updates = [
        TripUpdate(trip_id="T1", route_id="R1", stop_id="S1", stop_sequence=1),
        TripUpdate(trip_id="T2", route_id="R1", stop_id="S2", stop_sequence=2),
    ]

    await gtfs_realtime_service._store_trip_updates(updates)

    # Should call mset_json (once for updates, once for indexes)
    assert mock_cache.mset_json.call_count == 2
    # Individual set_json should NOT be called
    assert mock_cache.set_json.call_count == 0

    # Verify the batch content
    first_call_args = mock_cache.mset_json.call_args_list[0][0][0]
    assert "trip_update:T1:S1" in first_call_args
    assert "trip_update:T2:S2" in first_call_args
