import pytest
from unittest.mock import AsyncMock
from dataclasses import dataclass
from app.services.transit_data import TransitDataService


@dataclass
class MockStop:
    stop_id: str
    stop_name: str
    stop_lat: float = 0.0
    stop_lon: float = 0.0


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get_json = AsyncMock(return_value=None)
    cache.set_json = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def mock_gtfs_schedule():
    schedule = AsyncMock()
    schedule.search_stops = AsyncMock(
        return_value=[MockStop(stop_id="123", stop_name="Hauptbahnhof")]
    )
    return schedule


@pytest.fixture
def transit_data_service(mock_cache, mock_gtfs_schedule):
    service = TransitDataService(
        cache_service=mock_cache,
        gtfs_schedule=mock_gtfs_schedule,
        gtfs_realtime=AsyncMock(),
        db_session=AsyncMock(),
    )
    return service


@pytest.mark.asyncio
async def test_search_stops_caches_result(
    transit_data_service, mock_cache, mock_gtfs_schedule
):
    """Search results should be cached."""
    mock_cache.get_json.return_value = None  # Cache miss

    result = await transit_data_service.search_stops("hauptbahnhof", limit=5)

    assert len(result) == 1
    assert result[0].stop_id == "123"

    # Verify cache.set_json was called
    mock_cache.set_json.assert_called_once()
    call_args = mock_cache.set_json.call_args
    assert "stop_search:hauptbahnhof:5" in call_args[0][0]


@pytest.mark.asyncio
async def test_search_stops_returns_cached(
    transit_data_service, mock_cache, mock_gtfs_schedule
):
    """Cached search results should be returned without DB query."""
    cached_data = [
        {"stop_id": "123", "stop_name": "Test", "stop_lat": 0, "stop_lon": 0}
    ]
    mock_cache.get_json.return_value = cached_data

    result = await transit_data_service.search_stops("test", limit=5)

    assert len(result) == 1
    assert result[0].stop_id == "123"
    assert result[0].stop_name == "Test"

    # DB search should NOT have been called
    mock_gtfs_schedule.search_stops.assert_not_called()
