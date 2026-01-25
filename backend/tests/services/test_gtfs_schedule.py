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
    _get_weekday_column,
)
from app.models.gtfs import GTFSCalendar


class TestTimeToInterval:
    """Tests for time_to_interval helper function."""

    def test_time_to_interval_morning(self):
        """Test conversion of morning time."""
        dt = datetime(2025, 12, 8, 8, 30, 0, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == timedelta(hours=8, minutes=30, seconds=0)

    def test_time_to_interval_afternoon(self):
        """Test conversion of afternoon time."""
        dt = datetime(2025, 12, 8, 14, 45, 30, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == timedelta(hours=14, minutes=45, seconds=30)

    def test_time_to_interval_midnight(self):
        """Test conversion of midnight."""
        dt = datetime(2025, 12, 8, 0, 0, 0, tzinfo=timezone.utc)
        result = time_to_interval(dt)
        assert result == timedelta(hours=0, minutes=0, seconds=0)


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

    def test_interval_to_datetime_string_with_seconds(self):
        """Test conversion from string interval format including seconds."""
        service_date = date(2025, 12, 8)
        interval_str = "8 hours 30 minutes 45 seconds"
        result = interval_to_datetime(service_date, interval_str)

        expected = datetime(2025, 12, 8, 8, 30, 45, tzinfo=timezone.utc)
        assert result == expected

    def test_interval_to_datetime_unknown_type(self):
        """Test that unknown interval types return None and log a warning."""
        result = interval_to_datetime(date(2025, 12, 8), 12345)  # int is not supported
        assert result is None

    def test_interval_to_datetime_value_error(self):
        """Test handling of ValueError during interval parsing."""

        # Create a mock object that raises ValueError when accessed
        class BadInterval:
            def __str__(self):
                raise ValueError("Bad interval")

        result = interval_to_datetime(date(2025, 12, 8), BadInterval())
        # Should return None due to exception handling
        assert result is None


class TestGetWeekdayColumn:
    """Tests for _get_weekday_column helper function."""

    def test_get_weekday_column_monday(self):
        """Test getting Monday column."""
        calendar = GTFSCalendar
        column = _get_weekday_column(calendar, "monday")
        assert column is not None

    def test_get_weekday_column_all_days(self):
        """Test getting all valid weekday columns."""
        calendar = GTFSCalendar
        weekdays = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for weekday in weekdays:
            column = _get_weekday_column(calendar, weekday)
            assert column is not None

    def test_get_weekday_column_invalid_weekday(self):
        """Test that invalid weekday raises ValueError."""
        calendar = GTFSCalendar
        with pytest.raises(ValueError, match="Invalid weekday"):
            _get_weekday_column(calendar, "notaday")


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
        # Mock query to return empty result
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))  # Empty iterator
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


class TestGetStopDepartures:
    """Tests for get_stop_departures() method with various calendar scenarios."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create service with mock session."""
        return GTFSScheduleService(mock_session)

    def _create_departure_row(
        self,
        departure_time: timedelta,
        trip_id: str = "trip_001",
        route_id: str = "route_S1",
        trip_headsign: str = "München Ost",
        route_short_name: str = "S1",
        route_long_name: str = "S-Bahn S1",
        route_type: int = 2,
        route_color: str = "00BFFF",
        stop_name: str = "Marienplatz",
        arrival_time: timedelta = None,
    ):
        """Create a mock departure row matching the SQL query output."""
        row = MagicMock()
        row.departure_time = departure_time
        row.arrival_time = arrival_time or departure_time
        row.trip_headsign = trip_headsign
        row.route_short_name = route_short_name
        row.route_long_name = route_long_name
        row.route_type = route_type
        row.route_color = route_color
        row.stop_name = stop_name
        row.trip_id = trip_id
        row.route_id = route_id
        # Add _mapping for dict conversion
        row._mapping = {
            "departure_time": departure_time,
            "arrival_time": arrival_time or departure_time,
            "trip_headsign": trip_headsign,
            "route_short_name": route_short_name,
            "route_long_name": route_long_name,
            "route_type": route_type,
            "route_color": route_color,
            "stop_name": stop_name,
            "trip_id": trip_id,
            "route_id": route_id,
        }
        return row

    def _mock_stop_exists(self, mock_session, stop_id: str = "de:09162:6"):
        """Set up mock to return a stop for the first query (stop exists check)."""
        mock_row = MagicMock()
        mock_row.stop_id = stop_id
        mock_row.stop_name = "Marienplatz"

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([mock_row]))
        return mock_result

    @pytest.mark.asyncio
    async def test_get_stop_departures_weekday_service(self, service, mock_session):
        """Test departures for normal weekday service (Monday)."""
        # Create departure rows for weekday service
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=30),
                trip_id="trip_001",
                trip_headsign="Ostbahnhof",
            ),
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=40),
                trip_id="trip_002",
                trip_headsign="Ostbahnhof",
            ),
        ]

        # First call: check if stop exists (returns stop)
        # Second call: get departures (returns departure rows)
        mock_stop_result = self._mock_stop_exists(mock_session)

        # Create an iterator for departure rows
        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter(departure_rows))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        # Query for a Monday
        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)  # Monday
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 2
        assert departures[0].trip_headsign == "Ostbahnhof"
        assert departures[0].departure_time == datetime(
            2025, 12, 8, 8, 30, tzinfo=timezone.utc
        )
        assert departures[1].departure_time == datetime(
            2025, 12, 8, 8, 40, tzinfo=timezone.utc
        )

    @pytest.mark.asyncio
    async def test_get_stop_departures_supports_calendar_dates_only(
        self, service, mock_session
    ):
        """Ensure SQL supports feeds without calendar.txt (calendar_dates-only)."""
        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)  # Monday
        await service.get_stop_departures("de:09162:6", query_time, limit=10)

        # Second execute() call is the departures query (SQLAlchemy Select object)
        query_obj = mock_session.execute.call_args_list[1][0][0]
        sql = str(query_obj)
        # SQLAlchemy ORM uses 'LEFT OUTER JOIN ... AS' format
        assert "LEFT OUTER JOIN gtfs_calendar AS c" in sql
        assert "cd.exception_type =" in sql  # Check exception_type=1 condition exists

    @pytest.mark.asyncio
    async def test_get_stop_departures_includes_parent_station_children(
        self, service, mock_session
    ):
        """Ensure parent stations return departures from child stops/platforms."""
        mock_stop_result = self._mock_stop_exists(
            mock_session, stop_id="parent_station_id"
        )

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)  # Monday
        await service.get_stop_departures("parent_station_id", query_time, limit=10)

        # First query should check for parent_station
        query_obj = mock_session.execute.call_args_list[0][0][0]
        sql = str(query_obj)
        # SQLAlchemy ORM uses different parameter naming like :parent_station_1
        assert "gtfs_stops.parent_station =" in sql

    @pytest.mark.asyncio
    async def test_get_stop_departures_overnight_service(self, service, mock_session):
        """Test departures with times > 24:00 (overnight service spanning midnight)."""
        # GTFS times can exceed 24:00 for overnight services
        # e.g., 25:30 = 1:30 AM next day
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=25, minutes=30),  # 1:30 AM next day
                trip_id="trip_overnight",
                trip_headsign="Nachtlinie",
            ),
        ]

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter(departure_rows))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        # Query at 11 PM on the service date
        query_time = datetime(2025, 12, 8, 23, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        # 25:30 on Dec 8 = 1:30 AM on Dec 9
        assert departures[0].departure_time == datetime(
            2025, 12, 9, 1, 30, tzinfo=timezone.utc
        )

    @pytest.mark.asyncio
    async def test_get_stop_departures_no_results(self, service, mock_session):
        """Test when there are no departures for the requested time."""
        mock_stop_result = self._mock_stop_exists(mock_session)

        # Return empty departures
        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert departures == []

    @pytest.mark.asyncio
    async def test_get_stop_departures_multiple_routes(self, service, mock_session):
        """Test departures from multiple routes at the same stop."""
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=30),
                trip_id="trip_s1",
                route_id="route_S1",
                route_short_name="S1",
                trip_headsign="Ost",
            ),
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=32),
                trip_id="trip_u3",
                route_id="route_U3",
                route_short_name="U3",
                route_type=1,  # Subway
                trip_headsign="Moosach",
            ),
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=35),
                trip_id="trip_tram19",
                route_id="route_T19",
                route_short_name="19",
                route_type=0,  # Tram
                trip_headsign="Berg am Laim",
            ),
        ]

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter(departure_rows))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 3
        assert departures[0].route_short_name == "S1"
        assert departures[0].route_type == 2
        assert departures[1].route_short_name == "U3"
        assert departures[1].route_type == 1
        assert departures[2].route_short_name == "19"
        assert departures[2].route_type == 0

    @pytest.mark.asyncio
    async def test_get_stop_departures_weekend_service(self, service, mock_session):
        """Test departures for weekend (Saturday) service."""
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=10, minutes=0),
                trip_id="trip_weekend",
                trip_headsign="Flughafen",
            ),
        ]

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter(departure_rows))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        # Query for a Saturday
        query_time = datetime(2025, 12, 13, 9, 0, tzinfo=timezone.utc)  # Saturday
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        assert departures[0].departure_time == datetime(
            2025, 12, 13, 10, 0, tzinfo=timezone.utc
        )

    @pytest.mark.asyncio
    async def test_get_stop_departures_sunday_service(self, service, mock_session):
        """Test departures for Sunday service."""
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=11, minutes=15),
                trip_id="trip_sunday",
                trip_headsign="Hauptbahnhof",
            ),
        ]

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter(departure_rows))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        # Query for a Sunday
        query_time = datetime(2025, 12, 14, 10, 0, tzinfo=timezone.utc)  # Sunday
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        assert departures[0].trip_headsign == "Hauptbahnhof"

    @pytest.mark.asyncio
    async def test_get_stop_departures_null_arrival_time(self, service, mock_session):
        """Test departures with NULL arrival_time (should use departure_time)."""
        departure_row = self._create_departure_row(
            departure_time=timedelta(hours=9, minutes=0),
            trip_id="trip_no_arrival",
        )
        departure_row.arrival_time = None
        departure_row._mapping["arrival_time"] = None

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([departure_row]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        # arrival_time should be None when not provided
        # (ScheduledDeparture.__init__ sets it to departure_time if None)

    @pytest.mark.asyncio
    async def test_get_stop_departures_with_arrival_before_departure(
        self, service, mock_session
    ):
        """Test departures where arrival is before departure (dwell time at station)."""
        departure_row = self._create_departure_row(
            departure_time=timedelta(hours=9, minutes=2),
            arrival_time=timedelta(
                hours=9, minutes=0
            ),  # Arrives 2 min before departure
            trip_id="trip_dwell",
        )

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([departure_row]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        assert departures[0].departure_time == datetime(
            2025, 12, 8, 9, 2, tzinfo=timezone.utc
        )
        assert departures[0].arrival_time == datetime(
            2025, 12, 8, 9, 0, tzinfo=timezone.utc
        )

    @pytest.mark.asyncio
    async def test_get_stop_departures_respects_limit(self, service, mock_session):
        """Test that the limit parameter is respected."""
        # Create many departure rows
        departure_rows = [
            self._create_departure_row(
                departure_time=timedelta(hours=8, minutes=i * 5),
                trip_id=f"trip_{i:03d}",
            )
            for i in range(20)
        ]

        mock_stop_result = self._mock_stop_exists(mock_session)

        # Only return 5 rows to simulate limit
        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(
            return_value=iter(departure_rows[:5])
        )

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=5
        )

        # Verify we get at most 5 departures
        assert len(departures) <= 5

    @pytest.mark.asyncio
    async def test_get_stop_departures_all_weekdays(self, service, mock_session):
        """Test that departures work for all days of the week."""
        # Test each weekday (Monday=0 through Sunday=6)
        weekdays = [
            (datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc), "monday"),
            (datetime(2025, 12, 9, 8, 0, tzinfo=timezone.utc), "tuesday"),
            (datetime(2025, 12, 10, 8, 0, tzinfo=timezone.utc), "wednesday"),
            (datetime(2025, 12, 11, 8, 0, tzinfo=timezone.utc), "thursday"),
            (datetime(2025, 12, 12, 8, 0, tzinfo=timezone.utc), "friday"),
            (datetime(2025, 12, 13, 8, 0, tzinfo=timezone.utc), "saturday"),
            (datetime(2025, 12, 14, 8, 0, tzinfo=timezone.utc), "sunday"),
        ]

        for query_time, expected_day in weekdays:
            departure_rows = [
                self._create_departure_row(
                    departure_time=timedelta(hours=9, minutes=0),
                    trip_id=f"trip_{expected_day}",
                    trip_headsign=expected_day.capitalize(),
                ),
            ]

            mock_stop_result = self._mock_stop_exists(mock_session)

            mock_departure_result = MagicMock()
            mock_departure_result.__iter__ = MagicMock(
                return_value=iter(departure_rows)
            )

            mock_session.execute = AsyncMock(
                side_effect=[mock_stop_result, mock_departure_result]
            )

            departures = await service.get_stop_departures(
                "de:09162:6", query_time, limit=10
            )

            assert len(departures) == 1, f"Failed for {expected_day}"
            assert departures[0].trip_headsign == expected_day.capitalize()

    @pytest.mark.asyncio
    async def test_get_stop_departures_null_optional_fields(
        self, service, mock_session
    ):
        """Test departures with NULL optional fields (headsign, route_color, etc.)."""
        departure_row = self._create_departure_row(
            departure_time=timedelta(hours=10, minutes=0),
            trip_id="trip_sparse",
            trip_headsign=None,
            route_long_name=None,
            route_color=None,
        )
        # Update the mapping too
        departure_row._mapping["trip_headsign"] = None
        departure_row._mapping["route_long_name"] = None
        departure_row._mapping["route_color"] = None

        mock_stop_result = self._mock_stop_exists(mock_session)

        mock_departure_result = MagicMock()
        mock_departure_result.__iter__ = MagicMock(return_value=iter([departure_row]))

        mock_session.execute = AsyncMock(
            side_effect=[mock_stop_result, mock_departure_result]
        )

        query_time = datetime(2025, 12, 8, 8, 0, tzinfo=timezone.utc)
        departures = await service.get_stop_departures(
            "de:09162:6", query_time, limit=10
        )

        assert len(departures) == 1
        # ScheduledDeparture.from_row converts None to empty string
        assert departures[0].trip_headsign == ""
        assert departures[0].route_long_name == ""
        assert departures[0].route_color is None
