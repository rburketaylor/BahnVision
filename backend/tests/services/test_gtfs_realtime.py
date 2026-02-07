"""
Unit tests for GTFS Real-Time service functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.services.cache import CacheService
from app.services.gtfs_realtime import (
    GtfsRealtimeService,
    TripUpdate,
    VehiclePosition,
    ServiceAlert,
)


@pytest.fixture
def mock_cache_service():
    """Create a mock cache service."""
    cache_service = AsyncMock(spec=CacheService)
    cache_service.set_json = AsyncMock()
    cache_service.get_json = AsyncMock()
    cache_service.mget_json = AsyncMock()
    cache_service.mset_json = AsyncMock()
    return cache_service


@pytest.fixture
def gtfs_service(mock_cache_service):
    """Create GTFS-RT service with mocked dependencies."""
    with patch("app.services.gtfs_realtime.get_settings") as mock_settings:
        mock_settings.return_value.gtfs_rt_timeout_seconds = 10
        mock_settings.return_value.gtfs_rt_circuit_breaker_threshold = 3
        mock_settings.return_value.gtfs_rt_circuit_breaker_recovery_seconds = 60
        mock_settings.return_value.gtfs_rt_cache_ttl_seconds = 30
        mock_settings.return_value.gtfs_rt_feed_url = "https://example.com/gtfs-rt.pb"

        service = GtfsRealtimeService(mock_cache_service)
        return service


class TestTripUpdates:
    """Test trip update functionality."""

    @pytest.mark.asyncio
    async def test_store_trip_updates_with_indexing(
        self, gtfs_service, mock_cache_service
    ):
        """Test that trip updates are stored with stop-based indexing."""
        trip_updates = [
            TripUpdate(
                trip_id="trip1",
                route_id="route1",
                stop_id="stop1",
                stop_sequence=1,
                arrival_delay=60,
                departure_delay=60,
            ),
            TripUpdate(
                trip_id="trip2",
                route_id="route1",
                stop_id="stop1",
                stop_sequence=2,
                arrival_delay=120,
                departure_delay=120,
            ),
            TripUpdate(
                trip_id="trip1",
                route_id="route1",
                stop_id="stop2",
                stop_sequence=2,
                arrival_delay=90,
                departure_delay=90,
            ),
        ]

        await gtfs_service._store_trip_updates(trip_updates)

        # Should call mset_json once for all stop keys
        assert mock_cache_service.mset_json.call_count == 1

        # Check that individual set_json is NOT called (batch writes replace individual calls)
        assert mock_cache_service.set_json.call_count == 0

        # Verify the batch call contains the trip updates grouped by stop
        call_items = mock_cache_service.mset_json.call_args[0][0]
        assert "trip_updates:stop:stop1" in call_items
        assert "trip_updates:stop:stop2" in call_items

        # Verify content
        stop1_updates = call_items["trip_updates:stop:stop1"]
        assert len(stop1_updates) == 2
        stop1_trip_ids = {u["trip_id"] for u in stop1_updates}
        assert "trip1" in stop1_trip_ids
        assert "trip2" in stop1_trip_ids

    @pytest.mark.asyncio
    async def test_get_trip_updates_for_stop(self, gtfs_service, mock_cache_service):
        """Test retrieving trip updates for a specific stop."""
        # Mock the get_json response
        mock_cache_service.get_json.return_value = [
            {
                "trip_id": "trip1",
                "route_id": "route1",
                "stop_id": "stop1",
                "stop_sequence": 1,
                "arrival_delay": 60,
                "departure_delay": 60,
                "schedule_relationship": "SCHEDULED",
            },
            {
                "trip_id": "trip2",
                "route_id": "route1",
                "stop_id": "stop1",
                "stop_sequence": 2,
                "arrival_delay": 120,
                "departure_delay": 120,
                "schedule_relationship": "SCHEDULED",
            },
        ]

        result = await gtfs_service.get_trip_updates_for_stop("stop1")

        assert len(result) == 2
        # Note: Dict order may vary, so check both exist
        trip_ids = {tu.trip_id for tu in result}
        assert trip_ids == {"trip1", "trip2"}
        assert all(tu.stop_id == "stop1" for tu in result)

        # Verify mget_json is NOT called
        assert mock_cache_service.mget_json.call_count == 0

    @pytest.mark.asyncio
    async def test_get_trip_updates_for_empty_stop(
        self, gtfs_service, mock_cache_service
    ):
        """Test retrieving trip updates for a stop with no updates."""
        mock_cache_service.get_json.return_value = None

        result = await gtfs_service.get_trip_updates_for_stop("empty_stop")

        assert result == []


class TestVehiclePositions:
    """Test vehicle position functionality."""

    @pytest.mark.asyncio
    async def test_store_vehicle_positions_with_trip_indexing(
        self, gtfs_service, mock_cache_service
    ):
        """Test that vehicle positions are stored with trip-based indexing."""
        vehicle_positions = [
            VehiclePosition(
                trip_id="trip1",
                vehicle_id="vehicle1",
                route_id="route1",
                latitude=48.1351,
                longitude=11.5820,
            ),
            VehiclePosition(
                trip_id="trip2",
                vehicle_id="vehicle2",
                route_id="route1",
                latitude=48.1352,
                longitude=11.5821,
            ),
            VehiclePosition(
                trip_id="",  # Empty trip_id
                vehicle_id="vehicle3",
                route_id="route2",
                latitude=48.1353,
                longitude=11.5822,
            ),
        ]

        await gtfs_service._store_vehicle_positions(vehicle_positions)

        # Verify batch writes are used (Issue 6: GTFS-RT Batch Writes)
        # Should call mset_json once with all vehicle positions and trip indexes
        assert mock_cache_service.mset_json.call_count == 1

        # Check that individual set_json is NOT called
        assert mock_cache_service.set_json.call_count == 0

        # Verify the batch call contains vehicle positions and trip indexes
        batch_items = mock_cache_service.mset_json.call_args[0][0]
        assert "vehicle_position:vehicle1" in batch_items
        assert "vehicle_position:vehicle2" in batch_items
        assert "vehicle_position:vehicle3" in batch_items
        # trip indexes for non-empty trip_id vehicles
        assert "vehicle_position:trip:trip1" in batch_items
        assert "vehicle_position:trip:trip2" in batch_items

    @pytest.mark.asyncio
    async def test_get_vehicle_position_by_trip(self, gtfs_service, mock_cache_service):
        """Test retrieving vehicle position by trip ID."""
        mock_vehicle_data = {
            "trip_id": "trip1",
            "vehicle_id": "vehicle1",
            "route_id": "route1",
            "latitude": 48.1351,
            "longitude": 11.5820,
        }
        mock_cache_service.get_json.return_value = mock_vehicle_data

        result = await gtfs_service.get_vehicle_position_by_trip("trip1")

        assert result is not None
        assert result.trip_id == "trip1"
        assert result.vehicle_id == "vehicle1"
        assert result.latitude == 48.1351

    @pytest.mark.asyncio
    async def test_get_vehicle_position_by_vehicle_id(
        self, gtfs_service, mock_cache_service
    ):
        """Test retrieving vehicle position by vehicle ID."""
        mock_vehicle_data = {
            "trip_id": "trip1",
            "vehicle_id": "vehicle1",
            "route_id": "route1",
            "latitude": 48.1351,
            "longitude": 11.5820,
        }
        mock_cache_service.get_json.return_value = mock_vehicle_data

        result = await gtfs_service.get_vehicle_position("vehicle1")

        assert result is not None
        assert result.vehicle_id == "vehicle1"

    @pytest.mark.asyncio
    async def test_get_vehicle_positions_by_trips(
        self, gtfs_service, mock_cache_service
    ):
        """Test retrieving multiple vehicle positions by trip IDs in batch."""
        # Mock the mget_json response
        mock_cache_service.mget_json.return_value = {
            "vehicle_position:trip:trip1": {
                "trip_id": "trip1",
                "vehicle_id": "vehicle1",
                "route_id": "route1",
                "latitude": 48.1351,
                "longitude": 11.5820,
            },
            "vehicle_position:trip:trip2": {
                "trip_id": "trip2",
                "vehicle_id": "vehicle2",
                "route_id": "route1",
                "latitude": 48.1352,
                "longitude": 11.5821,
            },
            "vehicle_position:trip:trip3": None,  # Trip with no vehicle position
        }

        result = await gtfs_service.get_vehicle_positions_by_trips(
            ["trip1", "trip2", "trip3"]
        )

        assert len(result) == 2
        assert "trip1" in result
        assert "trip2" in result
        assert "trip3" not in result  # Should not include None values
        assert result["trip1"].vehicle_id == "vehicle1"
        assert result["trip2"].vehicle_id == "vehicle2"

    @pytest.mark.asyncio
    async def test_get_vehicle_positions_by_trips_empty_list(
        self, gtfs_service, mock_cache_service
    ):
        """Test batch vehicle positions with empty trip list."""
        result = await gtfs_service.get_vehicle_positions_by_trips([])

        assert result == {}
        mock_cache_service.mget_json.assert_not_called()


class TestServiceAlerts:
    """Test service alert functionality."""

    @pytest.mark.asyncio
    async def test_store_alerts_with_route_indexing(
        self, gtfs_service, mock_cache_service
    ):
        """Test that service alerts are stored with route-based indexing."""
        alerts = [
            ServiceAlert(
                alert_id="alert1",
                cause="TECHNICAL_PROBLEM",
                effect="SIGNIFICANT_DELAYS",
                header_text="Delays on Route 1",
                description_text="Technical issues causing delays",
                affected_routes={"route1", "route2"},
                affected_stops={"stop1", "stop2"},
            ),
            ServiceAlert(
                alert_id="alert2",
                cause="ACCIDENT",
                effect="DETOUR",
                header_text="Route 3 Detour",
                description_text="Accident on Route 3",
                affected_routes={"route3"},
                affected_stops={"stop3"},
            ),
        ]

        await gtfs_service._store_alerts(alerts)

        # Verify batch writes are used (Issue 6: GTFS-RT Batch Writes)
        # Should call mset_json once: combined alerts and route indexes
        assert mock_cache_service.mset_json.call_count == 1

        # Check that individual set_json is NOT called
        assert mock_cache_service.set_json.call_count == 0

        # Verify the batch call contains both alerts and route indexes
        batch_items = mock_cache_service.mset_json.call_args[0][0]

        # Alerts
        assert "service_alert:alert1" in batch_items
        assert "service_alert:alert2" in batch_items

        # Route indexes
        assert "service_alerts:route:route1" in batch_items
        assert "service_alerts:route:route2" in batch_items
        assert "service_alerts:route:route3" in batch_items

    @pytest.mark.asyncio
    async def test_get_alerts_for_route(self, gtfs_service, mock_cache_service):
        """Test retrieving alerts for a specific route."""
        # Mock the index response (first call gets the route index)
        mock_cache_service.get_json.return_value = ["alert1", "alert2"]

        # Mock the mget_json response for batch fetch
        mock_cache_service.mget_json.return_value = {
            "service_alert:alert1": {
                "alert_id": "alert1",
                "cause": "TECHNICAL_PROBLEM",
                "effect": "SIGNIFICANT_DELAYS",
                "header_text": "Delays on Route 1",
                "description_text": "Technical issues causing delays",
                "affected_routes": ["route1", "route2"],
                "affected_stops": ["stop1", "stop2"],
            },
            "service_alert:alert2": {
                "alert_id": "alert2",
                "cause": "ACCIDENT",
                "effect": "DETOUR",
                "header_text": "Route 3 Detour",
                "description_text": "Accident on Route 3",
                "affected_routes": ["route3"],
                "affected_stops": ["stop3"],
            },
        }

        result = await gtfs_service.get_alerts_for_route("route1")

        assert len(result) == 2
        # Note: Dict order may vary, so check by alert_id
        alert_ids = {alert.alert_id for alert in result}
        assert alert_ids == {"alert1", "alert2"}

    @pytest.mark.asyncio
    async def test_get_alerts_for_empty_route(self, gtfs_service, mock_cache_service):
        """Test retrieving alerts for a route with no alerts."""
        mock_cache_service.get_json.return_value = None

        result = await gtfs_service.get_alerts_for_route("empty_route")

        assert result == []


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self, gtfs_service):
        """Test that circuit breaker starts in CLOSED state."""
        assert gtfs_service._circuit_breaker_state["state"] == "CLOSED"
        assert gtfs_service._circuit_breaker_state["failures"] == 0

    def test_circuit_breaker_opens_after_threshold(self, gtfs_service):
        """Test that circuit breaker opens after failure threshold."""
        # Record failures up to threshold
        for _ in range(3):
            gtfs_service._record_failure()

        assert gtfs_service._circuit_breaker_state["state"] == "OPEN"

    def test_circuit_breaker_closes_on_success(self, gtfs_service):
        """Test that circuit breaker closes on success."""
        # Open the circuit breaker first
        gtfs_service._record_failure()
        gtfs_service._record_failure()
        gtfs_service._record_failure()
        assert gtfs_service._circuit_breaker_state["state"] == "OPEN"

        # Record success
        gtfs_service._record_success()

        assert gtfs_service._circuit_breaker_state["state"] == "CLOSED"
        assert gtfs_service._circuit_breaker_state["failures"] == 0

    def test_circuit_breaker_prevents_requests_when_open(self, gtfs_service):
        """Test that circuit breaker prevents requests when OPEN."""
        # Open the circuit breaker
        gtfs_service._record_failure()
        gtfs_service._record_failure()
        gtfs_service._record_failure()

        assert not gtfs_service._check_circuit_breaker()

    def test_circuit_breaker_allows_requests_when_closed(self, gtfs_service):
        """Test that circuit breaker allows requests when CLOSED."""
        assert gtfs_service._check_circuit_breaker()


class TestDataModels:
    """Test data model functionality."""

    def test_trip_update_timestamp_default(self):
        """Test that TripUpdate sets default timestamp."""
        before = datetime.now(timezone.utc)
        tu = TripUpdate(
            trip_id="trip1",
            route_id="route1",
            stop_id="stop1",
            stop_sequence=1,
            schedule_relationship="SCHEDULED",
        )
        after = datetime.now(timezone.utc)

        assert tu.timestamp is not None
        assert before <= tu.timestamp <= after

    def test_vehicle_position_timestamp_default(self):
        """Test that VehiclePosition sets default timestamp."""
        before = datetime.now(timezone.utc)
        vp = VehiclePosition(
            trip_id="trip1",
            vehicle_id="vehicle1",
            route_id="route1",
            latitude=48.1351,
            longitude=11.5820,
        )
        after = datetime.now(timezone.utc)

        assert vp.timestamp is not None
        assert before <= vp.timestamp <= after

    def test_service_alert_timestamp_default(self):
        """Test that ServiceAlert sets default timestamp."""
        before = datetime.now(timezone.utc)
        alert = ServiceAlert(
            alert_id="alert1",
            cause="TECHNICAL_PROBLEM",
            effect="SIGNIFICANT_DELAYS",
            header_text="Test Alert",
            description_text="Test Description",
            affected_routes={"route1"},
            affected_stops={"stop1"},
        )
        after = datetime.now(timezone.utc)

        assert alert.timestamp is not None
        assert before <= alert.timestamp <= after

    def test_map_schedule_relationship_includes_canceled(self, gtfs_service):
        """Schedule relationship mapping should include CANCELED."""
        assert gtfs_service._map_schedule_relationship(4) == "CANCELED"
