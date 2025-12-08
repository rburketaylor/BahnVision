"""
Unit tests for GTFSScheduleService.

Tests schedule queries, stop search, and nearby stops functionality.
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.gtfs_schedule import (
    GTFSScheduleService,
    ScheduledDeparture,
    StopNotFoundError,
    time_to_interval,
    interval_to_datetime,
)


class TestTimeToInterval:
    """Tests for time_to_interval helper function."""

    def test_time_to_interval_morning(self):
        """Test conversion of morning time."""
        dt = datetime(2025, 12, 8, 8, 30, 0, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == "8 hours 30 minutes 0 seconds"

    def test_time_to_interval_afternoon(self):
        """Test conversion of afternoon time."""
        dt = datetime(2025, 12, 8, 14, 45, 30, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == "14 hours 45 minutes 30 seconds"

    def test_time_to_interval_midnight(self):
        """Test conversion of midnight."""
        dt = datetime(2025, 12, 8, 0, 0, 0, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == "0 hours 0 minutes 0 seconds"


class TestIntervalToDatetime:
    """Tests for interval_to_datetime helper function."""

    def test_interval_to_datetime_with_timedelta(self):
        """Test conversion from timedelta."""
        service_date = date(2025, 12, 8)
        interval = timedelta(hours=8, minutes=30)
        result = interval_to_datetime(service_date, interval)

        expected = datetime(2025, 12, 8, 8, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_interval_to_datetime_over_24h(self):
        """Test conversion of times > 24 hours (overnight service)."""
        service_date = date(2025, 12, 8)
        interval = timedelta(hours=25, minutes=30)  # 1:30 AM next day
        result = interval_to_datetime(service_date, interval)

        # Should be 2025-12-09 01:30:00
        expected = datetime(2025, 12, 9, 1, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_interval_to_datetime_string_format(self):
        """Test conversion from string interval format."""
        service_date = date(2025, 12, 8)
        interval_str = "8 hours 30 minutes 0 seconds"
        result = interval_to_datetime(service_date, interval_str)

        expected = datetime(2025, 12, 8, 8, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_interval_to_datetime_none(self):
        """Test that None returns None."""
        result = interval_to_datetime(date(2025, 12, 8), None)
        assert result is None

    def test_interval_to_datetime_invalid_format(self):
        """Test that unrecognized string format defaults to midnight.

        The parser doesn't raise for unrecognized strings, it just
        returns midnight (0:0:0 delta) on the service date.
        """
        result = interval_to_datetime(date(2025, 12, 8), "invalid")
        # Parser returns midnight (00:00:00) for strings without hours/minutes/seconds
        expected = datetime(2025, 12, 8, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected


class TestScheduledDeparture:
    """Tests for ScheduledDeparture dataclass."""

    def test_scheduled_departure_creation(self):
        """Test creating a ScheduledDeparture."""
        dep = ScheduledDeparture(
            departure_time=datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc),
            trip_headsign="Ostbahnhof",
            route_short_name="S1",
            route_long_name="Freising - München - Ostbahnhof",
            route_type=2,
            route_color="00BFFF",
            stop_name="München Hbf",
            trip_id="trip_001",
            route_id="1-S1-1",
        )

        assert dep.trip_headsign == "Ostbahnhof"
        assert dep.route_short_name == "S1"
        assert dep.route_type == 2

    def test_scheduled_departure_arrival_defaults_to_departure(self):
        """Test that arrival_time defaults to departure_time if not provided."""
        dep_time = datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc)
        dep = ScheduledDeparture(
            departure_time=dep_time,
            trip_headsign="Test",
            route_short_name="T1",
            route_long_name="Test Route",
            route_type=3,
            route_color=None,
            stop_name="Test Stop",
            trip_id="t1",
            route_id="r1",
        )

        assert dep.arrival_time == dep_time

    def test_scheduled_departure_from_row(self):
        """Test creating ScheduledDeparture from database row."""
        # Create a mock row object
        mock_row = MagicMock()
        mock_row.departure_time = datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc)
        mock_row.trip_headsign = "Ostbahnhof"
        mock_row.route_short_name = "S1"
        mock_row.route_long_name = "Test Route"
        mock_row.route_type = 2
        mock_row.route_color = "00BFFF"
        mock_row.stop_name = "München Hbf"
        mock_row.trip_id = "trip_001"
        mock_row.route_id = "1-S1-1"
        mock_row.arrival_time = None

        dep = ScheduledDeparture.from_row(mock_row)

        assert dep.trip_headsign == "Ostbahnhof"
        assert dep.route_short_name == "S1"

    def test_scheduled_departure_from_row_none_values(self):
        """Test handling of None values in row."""
        mock_row = MagicMock()
        mock_row.departure_time = datetime(2025, 12, 8, 8, 30, tzinfo=timezone.utc)
        mock_row.trip_headsign = None
        mock_row.route_short_name = None
        mock_row.route_long_name = None
        mock_row.route_type = 3
        mock_row.route_color = None
        mock_row.stop_name = "Test"
        mock_row.trip_id = "t1"
        mock_row.route_id = "r1"

        dep = ScheduledDeparture.from_row(mock_row)

        assert dep.trip_headsign == ""
        assert dep.route_short_name == ""
        assert dep.route_long_name == ""


class TestGTFSScheduleService:
    """Tests for GTFSScheduleService."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create service with mock session."""
        return GTFSScheduleService(mock_session)

    @pytest.mark.asyncio
    async def test_get_stop_departures_stop_not_found(self, service, mock_session):
        """Test that StopNotFoundError is raised for unknown stops."""
        # Mock _get_stop to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(StopNotFoundError, match="not found"):
            await service.get_stop_departures(
                "unknown_stop", datetime.now(timezone.utc)
            )

    @pytest.mark.asyncio
    async def test_get_departures_for_stop_alias(self, service):
        """Test that get_departures_for_stop is an alias for get_stop_departures."""
        with patch.object(
            service, "get_stop_departures", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = []

            await service.get_departures_for_stop(
                "stop1", datetime.now(timezone.utc), 10
            )

            mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_stops_by_name(self, service, mock_session):
        """Test searching stops by name."""
        mock_stop = MagicMock()
        mock_stop.stop_id = "de:09162:6"
        mock_stop.stop_name = "München Hbf"

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_stop])
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_session.execute = AsyncMock(return_value=mock_result)

        stops = await service.search_stops("München", limit=10)

        assert len(stops) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_stops_limit(self, service, mock_session):
        """Test that limit is applied to stop search."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        await service.search_stops("Test", limit=5)

        # Verify the query was executed
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_stops_no_results(self, service, mock_session):
        """Test search with no results."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        stops = await service.search_stops("NonexistentStation123")

        assert stops == []

    @pytest.mark.asyncio
    async def test_get_all_stops(self, service, mock_session):
        """Test getting all stops."""
        mock_stops = [
            MagicMock(stop_id="s1"),
            MagicMock(stop_id="s2"),
            MagicMock(stop_id="s3"),
        ]
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=mock_stops))
                )
            )
        )

        stops = await service.get_all_stops(limit=100)

        assert len(stops) == 3
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_stops_respects_limit(self, service, mock_session):
        """Test that get_all_stops respects the limit parameter."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        await service.get_all_stops(limit=50)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_stops_empty_database(self, service, mock_session):
        """Test get_all_stops with empty database."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        stops = await service.get_all_stops()

        assert stops == []

    @pytest.mark.asyncio
    async def test_get_nearby_stops(self, service, mock_session):
        """Test finding stops near a location."""
        mock_stops = [MagicMock(stop_id="nearby1"), MagicMock(stop_id="nearby2")]
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=mock_stops))
                )
            )
        )

        stops = await service.get_nearby_stops(
            lat=48.1403, lon=11.5583, radius_km=1.0, limit=10
        )

        assert len(stops) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_nearby_stops_radius_filter(self, service, mock_session):
        """Test that radius filter is applied."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        # Test with different radii
        await service.get_nearby_stops(lat=48.0, lon=11.0, radius_km=0.5)
        await service.get_nearby_stops(lat=48.0, lon=11.0, radius_km=5.0)

        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_nearby_stops_empty_area(self, service, mock_session):
        """Test nearby stops in empty area."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )
        )

        stops = await service.get_nearby_stops(lat=0.0, lon=0.0, radius_km=1.0)

        assert stops == []

    @pytest.mark.asyncio
    async def test_get_route_details(self, service, mock_session):
        """Test getting route details."""
        mock_route = MagicMock()
        mock_route.route_id = "1-S1-1"
        mock_route.route_short_name = "S1"

        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=mock_route)
            )
        )

        route = await service.get_route_details("1-S1-1")

        assert route is not None
        assert route.route_id == "1-S1-1"

    @pytest.mark.asyncio
    async def test_get_route_details_not_found(self, service, mock_session):
        """Test getting non-existent route."""
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        route = await service.get_route_details("unknown")

        assert route is None
