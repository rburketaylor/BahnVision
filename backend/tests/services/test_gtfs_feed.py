"""
Unit tests for GTFSFeedImporter service.

Tests feed download, parsing, and persistence functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import polars as pl

from app.services.gtfs_feed import (
    GTFSFeedImporter,
    _clean_value,
)


class TestCleanValue:
    """Tests for _clean_value helper function."""

    def test_clean_value_none(self):
        """Test that None returns None."""
        assert _clean_value(None) is None

    def test_clean_value_nan(self):
        """Test that NaN returns None."""
        import numpy as np

        assert _clean_value(np.nan) is None
        assert _clean_value(float("nan")) is None

    def test_clean_value_numpy_int(self):
        """Test numpy int conversion."""
        import numpy as np

        assert _clean_value(np.int64(42)) == 42
        assert isinstance(_clean_value(np.int64(42)), int)

    def test_clean_value_numpy_float(self):
        """Test numpy float conversion."""
        import numpy as np

        result = _clean_value(np.float64(3.14))
        assert result == pytest.approx(3.14)

    def test_clean_value_regular_types(self):
        """Test that regular Python types pass through."""
        assert _clean_value(42) == 42
        assert _clean_value("text") == "text"
        assert _clean_value(3.14) == 3.14


class TestGTFSFeedImporter:
    """Tests for GTFSFeedImporter class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_feed_url = "https://download.gtfs.de/germany/full/latest.zip"
        settings.gtfs_storage_path = "/tmp/gtfs_test"
        settings.gtfs_download_timeout_seconds = 300
        settings.gtfs_use_unlogged_tables = True
        return settings

    @pytest.fixture
    def mock_session(self):
        """Create mock async database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        # Mock the connection chain for asyncpg
        mock_raw_conn = AsyncMock()
        mock_dbapi_conn = MagicMock()
        mock_driver_conn = AsyncMock()
        mock_driver_conn.copy_to_table = AsyncMock()

        mock_dbapi_conn.driver_connection = mock_driver_conn
        mock_raw_conn.get_raw_connection = AsyncMock(return_value=mock_dbapi_conn)
        session.connection = AsyncMock(return_value=mock_raw_conn)

        return session

    @pytest.fixture
    def importer(self, mock_session, mock_settings):
        """Create importer with mocked dependencies."""
        with patch.object(Path, "mkdir"):
            return GTFSFeedImporter(mock_session, mock_settings)

    def test_validate_feed_url_https(self, importer):
        """Test that HTTPS URLs are accepted."""
        # Should not raise - verify it returns None (success)
        result = importer._validate_feed_url(
            "https://download.gtfs.de/germany/full/latest.zip"
        )
        assert result is None, "HTTPS URL validation should succeed"

    def test_validate_feed_url_http(self, importer):
        """Test that HTTP URLs are accepted."""
        # Should not raise - verify it returns None (success)
        result = importer._validate_feed_url("http://example.com/gtfs.zip")
        assert result is None, "HTTP URL validation should succeed"

    def test_validate_feed_url_invalid_protocol(self, importer):
        """Test that invalid protocols are rejected."""
        with pytest.raises(ValueError, match="must be http"):
            importer._validate_feed_url("ftp://example.com/gtfs.zip")

    def test_validate_feed_url_file_protocol(self, importer):
        """Test that file:// protocol is rejected."""
        with pytest.raises(ValueError, match="must be http"):
            importer._validate_feed_url("file:///local/path/gtfs.zip")

    def test_convert_time_to_interval_standard(self, importer):
        """Test conversion of standard GTFS time."""
        result = importer._convert_time_to_interval("08:30:00")
        assert result == "8 hours 30 minutes 0 seconds"

    def test_convert_time_to_interval_over_24h(self, importer):
        """Test conversion of GTFS time > 24 hours."""
        result = importer._convert_time_to_interval("26:30:00")
        assert result == "26 hours 30 minutes 0 seconds"

    def test_convert_time_to_interval_midnight(self, importer):
        """Test conversion of midnight."""
        result = importer._convert_time_to_interval("00:00:00")
        assert result == "0 hours 0 minutes 0 seconds"

    def test_convert_time_to_interval_none(self, importer):
        """Test that None input returns None."""
        result = importer._convert_time_to_interval(None)
        assert result is None

    def test_convert_time_to_interval_invalid(self, importer):
        """Test that invalid format returns None."""
        result = importer._convert_time_to_interval("invalid")
        assert result is None

    @pytest.mark.asyncio
    async def test_download_feed_creates_file(self, importer, mock_settings):
        """Test that feed download creates a local file."""
        with patch("app.services.gtfs_feed.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.content = b"fake zip content"
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_instance.__aexit__ = AsyncMock()
            mock_client.return_value = mock_client_instance

            with patch("builtins.open", MagicMock()):
                result = await importer._download_feed(mock_settings.gtfs_feed_url)

                assert result is not None
                mock_client_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_truncate_all_tables(self, importer, mock_session):
        """Test that truncate drops FKs, indexes, and truncates tables."""
        await importer._truncate_all_tables()

        # Should have multiple execute calls
        assert mock_session.execute.call_count >= 5
        assert mock_session.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_copy_stops_empty_df(self, importer):
        """Test that empty DataFrame is handled gracefully."""
        empty_df = pl.DataFrame()
        # Should not raise - verify it returns early without error
        result = await importer._copy_stops(empty_df, "test_feed")
        assert result is None, "Empty DataFrame should be handled gracefully"

    @pytest.mark.asyncio
    async def test_copy_stops_with_data(self, importer, mock_session):
        """Test copying stops with valid data."""
        stops_df = pl.DataFrame(
            {
                "stop_id": ["stop1", "stop2"],
                "stop_name": ["Stop One", "Stop Two"],
                "stop_lat": [48.14, 48.15],
                "stop_lon": [11.55, 11.56],
                "location_type": [0, 1],
                "parent_station": [None, "stop1"],
                "platform_code": [None, "1"],
            }
        )

        await importer._copy_stops(stops_df, "test_feed")

        # Verify copy_to_table was called on the mock driver connection
        raw_conn = await mock_session.connection()
        dbapi_conn = await raw_conn.get_raw_connection()
        asyncpg_conn = dbapi_conn.driver_connection
        asyncpg_conn.copy_to_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_routes_empty_df(self, importer):
        """Test that empty DataFrame is handled gracefully."""
        empty_df = pl.DataFrame()
        # Should not raise - verify it returns early without error
        result = await importer._copy_routes(empty_df, "test_feed")
        assert result is None, "Empty DataFrame should be handled gracefully"

    @pytest.mark.asyncio
    async def test_copy_trips_empty_df(self, importer):
        """Test that empty DataFrame is handled gracefully."""
        empty_df = pl.DataFrame()
        # Should not raise - verify it returns early without error
        result = await importer._copy_trips(empty_df, "test_feed")
        assert result is None, "Empty DataFrame should be handled gracefully"

    @pytest.mark.asyncio
    async def test_copy_trips_missing_direction_id_casts_int16(self, importer):
        """Ensure missing direction_id becomes nullable Int16 for COPY."""
        trips_df = pl.DataFrame(
            {
                "trip_id": ["trip1"],
                "route_id": ["route1"],
                "service_id": ["service1"],
                "trip_headsign": ["Headsign"],
            }
        )
        captured = {}

        async def fake_copy(df, table_name, columns):
            captured["df"] = df
            captured["table_name"] = table_name
            captured["columns"] = columns

        importer._copy_polars_df = AsyncMock(side_effect=fake_copy)

        await importer._copy_trips(trips_df, "test_feed")

        assert captured["table_name"] == "gtfs_trips"
        assert "direction_id" in captured["columns"]
        assert captured["df"].schema["direction_id"] == pl.Int16
        assert captured["df"]["direction_id"].null_count() == 1

    @pytest.mark.asyncio
    async def test_record_feed_info(self, importer, mock_session):
        """Test recording feed metadata."""
        await importer._record_feed_info(
            feed_id="test_feed",
            feed_url="https://example.com",
            feed_start_date=None,
            feed_end_date=None,
            stop_count=2,
            route_count=1,
            trip_count=3,
        )

        mock_session.execute.assert_called()
        mock_session.commit.assert_called()


class TestGTFSFeedImporterIntegration:
    """Integration-style tests for GTFSFeedImporter."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.gtfs_feed_url = "https://download.gtfs.de/germany/full/latest.zip"
        settings.gtfs_storage_path = "/tmp/gtfs_test"
        settings.gtfs_download_timeout_seconds = 300
        settings.gtfs_use_unlogged_tables = True
        return settings

    @pytest.mark.asyncio
    async def test_import_feed_validates_url(self, mock_settings):
        """Test that import_feed validates the URL."""
        mock_session = AsyncMock()

        with patch.object(Path, "mkdir"):
            importer = GTFSFeedImporter(mock_session, mock_settings)

        with pytest.raises(ValueError):
            await importer.import_feed("ftp://invalid-protocol.com/gtfs.zip")

    @pytest.mark.asyncio
    async def test_import_feed_http_error(self, mock_settings):
        """Test handling HTTP errors during download."""
        mock_session = AsyncMock()

        with patch.object(Path, "mkdir"):
            importer = GTFSFeedImporter(mock_session, mock_settings)

        import httpx

        # Mock the _download_feed method directly to raise HTTP error
        with patch.object(importer, "_download_feed") as mock_download:
            mock_download.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )

            with pytest.raises(httpx.HTTPStatusError):
                await importer.import_feed()
