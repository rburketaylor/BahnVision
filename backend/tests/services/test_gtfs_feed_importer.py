"""
Unit tests for GTFS feed importer utilities.

These tests focus on the GTFSFeedImporter orchestration and data-shaping logic
without requiring a live database.
"""

from __future__ import annotations

import zipfile
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest

from app.services.gtfs_feed import GTFSFeedImporter, _clean_value


def _make_settings(tmp_path: Path, *, unlogged: bool = False):
    return SimpleNamespace(
        gtfs_storage_path=str(tmp_path),
        gtfs_feed_url="https://example.com/gtfs.zip",
        gtfs_use_unlogged_tables=unlogged,
        gtfs_download_timeout_seconds=5,
    )


def _make_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


class TestCleanValue:
    def test_none(self):
        assert _clean_value(None) is None

    def test_nan(self):
        assert _clean_value(float("nan")) is None

    def test_object_with_item(self):
        class Scalar:
            def __init__(self, value: int):
                self._value = value

            def item(self):
                return self._value

        assert _clean_value(Scalar(7)) == 7

    def test_val_compare_raises_is_tolerated(self):
        class Weird:
            def __ne__(self, other):  # noqa: D401 - test double
                raise RuntimeError("boom")

        obj = Weird()
        assert _clean_value(obj) is obj

    def test_item_raises_returns_original(self):
        class BadScalar:
            def item(self):
                raise RuntimeError("boom")

        obj = BadScalar()
        assert _clean_value(obj) is obj


class TestGTFSFeedImporterHelpers:
    def test_validate_feed_url_rejects_non_http(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        with pytest.raises(ValueError, match="must be http\\(s\\)"):
            importer._validate_feed_url("file:///tmp/feed.zip")

    @pytest.mark.asyncio
    async def test_import_feed_downloads_and_imports(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        fake_path = tmp_path / "downloaded.zip"
        fake_path.write_bytes(b"zip")

        with (
            patch.object(
                importer,
                "_download_feed",
                new_callable=AsyncMock,
                return_value=fake_path,
            ) as dl,
            patch.object(
                importer,
                "_import_from_path",
                new_callable=AsyncMock,
                return_value="gtfs_123",
            ) as imp,
        ):
            feed_id = await importer.import_feed()

        assert feed_id == "gtfs_123"
        dl.assert_awaited_once()
        imp.assert_awaited_once_with(fake_path, "https://example.com/gtfs.zip")

    @pytest.mark.asyncio
    async def test_import_from_path_sets_file_url(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        local_path = tmp_path / "feed.zip"
        local_path.write_bytes(b"zip")

        with patch.object(
            importer,
            "_import_from_path",
            new_callable=AsyncMock,
            return_value="gtfs_123",
        ) as imp:
            feed_id = await importer.import_from_path(local_path)

        assert feed_id == "gtfs_123"
        imp.assert_awaited_once_with(local_path, f"file://{local_path}")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("20250101", date(2025, 1, 1)),
            ("2025-01-02", date(2025, 1, 2)),
            (datetime(2025, 1, 3, 12, 0, 0), date(2025, 1, 3)),
        ],
    )
    def test_parse_gtfs_date_value_supports_common_inputs(
        self, tmp_path: Path, raw, expected: date
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        assert importer._parse_gtfs_date_value(raw) == expected

    def test_resolve_feed_dates_prefers_feed_info(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        feed_info_df = pl.DataFrame(
            {"feed_start_date": ["2025-01-01"], "feed_end_date": ["2025-01-31"]}
        )
        calendar_df = pl.DataFrame(
            {
                "service_id": ["svc"],
                "start_date": ["20240101"],
                "end_date": ["20241231"],
            }
        )

        start, end = importer._resolve_feed_dates(feed_info_df, calendar_df)
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 31)

    def test_resolve_feed_dates_falls_back_to_calendar_min_max(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        calendar_df = pl.DataFrame(
            {
                "service_id": ["a", "b"],
                "start_date": ["20250102", "20250101"],
                "end_date": ["20250109", "20250131"],
            }
        )

        start, end = importer._resolve_feed_dates(None, calendar_df)
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 31)

    def test_read_gtfs_table_from_path_missing_returns_none(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        assert importer._read_gtfs_table(tmp_path, "stops.txt") is None

    def test_read_gtfs_table_from_path_reads_csv(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        (tmp_path / "stops.txt").write_text(
            "stop_id,stop_name,stop_lat,stop_lon\ns1,A,1,2\n", encoding="utf-8"
        )
        df = importer._read_gtfs_table(tmp_path, "stops.txt")
        assert df is not None
        assert df.height == 1
        assert df["stop_name"].to_list() == ["A"]

    def test_read_gtfs_table_from_zip_nested_member(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "nested/stops.txt", "stop_id,stop_name,stop_lat,stop_lon\ns1,A,1,2\n"
            )

        with zipfile.ZipFile(zip_path) as zf:
            df = importer._read_gtfs_table(zf, "stops.txt")

        assert df is not None
        assert df.height == 1
        assert df["stop_id"].to_list() == ["s1"]

    def test_read_gtfs_table_from_zip_missing_returns_none(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("other.txt", "x\n")

        with zipfile.ZipFile(zip_path) as zf:
            df = importer._read_gtfs_table(zf, "stops.txt")

        assert df is None

    def test_convert_time_to_interval_over_24h_and_invalid(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        assert (
            importer._convert_time_to_interval("26:30:00")
            == "26 hours 30 minutes 0 seconds"
        )
        assert importer._convert_time_to_interval("not-a-time") is None

    def test_parse_gtfs_date_value_handles_date_nan_and_invalid(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        assert importer._parse_gtfs_date_value(date(2025, 1, 1)) == date(2025, 1, 1)
        assert importer._parse_gtfs_date_value(float("nan")) is None
        assert importer._parse_gtfs_date_value("not-a-date") is None

    def test_parse_gtfs_date_value_date_method_exception_falls_back_to_string(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))

        class WeirdDateLike:
            def date(self):
                raise RuntimeError("boom")

            def __str__(self):
                return "20250101"

        assert importer._parse_gtfs_date_value(WeirdDateLike()) == date(2025, 1, 1)

    def test_resolve_feed_dates_returns_none_when_calendar_missing(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        empty_calendar = pl.DataFrame(
            {
                "service_id": pl.Series([], dtype=pl.Utf8),
                "start_date": [],
                "end_date": [],
            }
        )
        start, end = importer._resolve_feed_dates(None, empty_calendar)
        assert start is None and end is None


class TestGTFSFeedImporterCopyShaping:
    @pytest.mark.asyncio
    async def test_copy_stops_adds_missing_columns(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))

        stops_df = pl.DataFrame(
            {
                "stop_id": ["s1"],
                "stop_name": ["A"],
                "stop_lat": [1.0],
                "stop_lon": [2.0],
            }
        )

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_stops(stops_df, "feed1")

        export_df = copy_df.call_args.args[0]
        assert export_df.columns == [
            "stop_id",
            "stop_name",
            "stop_lat",
            "stop_lon",
            "location_type",
            "parent_station",
            "platform_code",
            "feed_id",
        ]
        assert export_df["location_type"].to_list() == [0]
        assert export_df["feed_id"].to_list() == ["feed1"]

    @pytest.mark.asyncio
    async def test_copy_routes_fills_optional_columns(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        routes_df = pl.DataFrame({"route_id": ["r1"], "route_type": [2]})

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_routes(routes_df, "feed1")

        export_df = copy_df.call_args.args[0]
        assert export_df.columns == [
            "route_id",
            "agency_id",
            "route_short_name",
            "route_long_name",
            "route_type",
            "route_color",
            "feed_id",
        ]
        assert export_df["feed_id"].to_list() == ["feed1"]

    @pytest.mark.asyncio
    async def test_copy_trips_casts_direction_id_when_present(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        trips_df = pl.DataFrame(
            {
                "trip_id": ["t1"],
                "route_id": ["r1"],
                "service_id": ["svc1"],
                "direction_id": ["1"],
            }
        )

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_trips(trips_df, "feed1")

        export_df = copy_df.call_args.args[0]
        assert export_df["direction_id"].to_list() == [1]
        assert export_df["feed_id"].to_list() == ["feed1"]

    @pytest.mark.asyncio
    async def test_copy_stop_times_batch_normalizes_blanks_and_defaults(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        stop_times_df = pl.DataFrame(
            {
                "trip_id": ["t1"],
                "stop_id": ["s1"],
                "arrival_time": [""],
                "departure_time": [" 08:01:00 "],
                "stop_sequence": [1],
            }
        )

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_stop_times_batch(stop_times_df, "feed1")

        export_df = copy_df.call_args.args[0]
        assert export_df["arrival_time"].to_list() == [None]
        assert export_df["departure_time"].to_list() == ["08:01:00"]
        assert export_df["pickup_type"].to_list() == [0]
        assert export_df["drop_off_type"].to_list() == [0]

    @pytest.mark.asyncio
    async def test_copy_stop_times_batch_skips_empty(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        empty_df = pl.DataFrame(
            {
                "trip_id": pl.Series([], dtype=pl.Utf8),
                "stop_id": pl.Series([], dtype=pl.Utf8),
                "arrival_time": pl.Series([], dtype=pl.Utf8),
                "departure_time": pl.Series([], dtype=pl.Utf8),
                "stop_sequence": pl.Series([], dtype=pl.Int32),
            }
        )

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_stop_times_batch(empty_df, "feed1")

        copy_df.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_copy_calendar_shapes_both_tables(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        calendar_df = pl.DataFrame(
            {
                "service_id": ["svc1"],
                "monday": [1],
                "tuesday": [1],
                "wednesday": [1],
                "thursday": [1],
                "friday": [1],
                "saturday": [0],
                "sunday": [0],
                "start_date": ["2025-01-01"],
                "end_date": ["20250131"],
            }
        )
        calendar_dates_df = pl.DataFrame(
            {"service_id": ["svc1"], "date": ["2025-01-10"], "exception_type": [2]}
        )

        with patch.object(
            importer, "_copy_polars_df", new_callable=AsyncMock
        ) as copy_df:
            await importer._copy_calendar(calendar_df, calendar_dates_df, "feed1")

        assert copy_df.call_count == 2
        first_export_df = copy_df.call_args_list[0].args[0]
        second_export_df = copy_df.call_args_list[1].args[0]
        assert first_export_df["feed_id"].to_list() == ["feed1"]
        assert second_export_df["feed_id"].to_list() == ["feed1"]
        assert first_export_df.schema["start_date"] == pl.Date
        assert first_export_df.schema["end_date"] == pl.Date
        assert second_export_df.schema["date"] == pl.Date


class TestGTFSFeedImporterOrchestration:
    @pytest.mark.asyncio
    async def test_import_from_zip_orchestrates_reads_and_records_counts(
        self, tmp_path: Path
    ):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "stops.txt",
                "stop_id,stop_name,stop_lat,stop_lon\ns1,Alpha,1,2\ns2,Beta,3,4\n",
            )
            zf.writestr("routes.txt", "route_id,route_type\nr1,2\n")
            zf.writestr("trips.txt", "trip_id,route_id,service_id\nt1,r1,svc1\n")
            zf.writestr(
                "calendar.txt",
                "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                "svc1,1,1,1,1,1,0,0,20250101,20250131\n",
            )
            zf.writestr(
                "calendar_dates.txt",
                "service_id,date,exception_type\nsvc1,20250110,2\n",
            )
            zf.writestr(
                "feed_info.txt",
                "feed_start_date,feed_end_date\n2025-01-01,2025-01-31\n",
            )

        with (
            patch.object(importer, "_truncate_all_tables", new_callable=AsyncMock),
            patch.object(importer, "_copy_stops", new_callable=AsyncMock) as copy_stops,
            patch.object(
                importer, "_copy_routes", new_callable=AsyncMock
            ) as copy_routes,
            patch.object(importer, "_copy_trips", new_callable=AsyncMock) as copy_trips,
            patch.object(importer, "_copy_stop_times_from_zip", new_callable=AsyncMock),
            patch.object(
                importer, "_copy_calendar", new_callable=AsyncMock
            ) as copy_calendar,
            patch.object(
                importer, "_record_feed_info", new_callable=AsyncMock
            ) as record_feed,
        ):
            feed_id = await importer._import_from_path(
                zip_path, "https://example.com/gtfs.zip"
            )

        assert feed_id.startswith("gtfs_")
        assert copy_stops.await_count == 1
        assert copy_routes.await_count == 1
        assert copy_trips.await_count == 1
        assert copy_calendar.await_count == 1

        record_kwargs = record_feed.call_args.kwargs
        assert record_kwargs["feed_url"] == "https://example.com/gtfs.zip"
        assert record_kwargs["stop_count"] == 2
        assert record_kwargs["route_count"] == 1
        assert record_kwargs["trip_count"] == 1
        assert record_kwargs["feed_start_date"] == date(2025, 1, 1)
        assert record_kwargs["feed_end_date"] == date(2025, 1, 31)

    @pytest.mark.asyncio
    async def test_import_from_directory_exercises_directory_branch(
        self, tmp_path: Path
    ):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        feed_dir = tmp_path / "feed_dir"
        feed_dir.mkdir()
        (feed_dir / "stops.txt").write_text(
            "stop_id,stop_name,stop_lat,stop_lon\ns1,Alpha,1,2\n", encoding="utf-8"
        )
        (feed_dir / "routes.txt").write_text(
            "route_id,route_type\nr1,2\n", encoding="utf-8"
        )
        (feed_dir / "trips.txt").write_text(
            "trip_id,route_id,service_id\nt1,r1,svc1\n", encoding="utf-8"
        )
        (feed_dir / "calendar.txt").write_text(
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "svc1,1,1,1,1,1,0,0,20250101,20250131\n",
            encoding="utf-8",
        )
        (feed_dir / "calendar_dates.txt").write_text(
            "service_id,date,exception_type\nsvc1,20250110,2\n", encoding="utf-8"
        )
        (feed_dir / "feed_info.txt").write_text(
            "feed_start_date,feed_end_date\n2025-01-01,2025-01-31\n", encoding="utf-8"
        )

        with (
            patch.object(importer, "_truncate_all_tables", new_callable=AsyncMock),
            patch.object(importer, "_copy_stops", new_callable=AsyncMock),
            patch.object(importer, "_copy_routes", new_callable=AsyncMock),
            patch.object(importer, "_copy_trips", new_callable=AsyncMock),
            patch.object(
                importer, "_copy_stop_times_from_path", new_callable=AsyncMock
            ),
            patch.object(importer, "_copy_calendar", new_callable=AsyncMock),
            patch.object(
                importer, "_record_feed_info", new_callable=AsyncMock
            ) as record_feed,
        ):
            feed_id = await importer._import_from_path(feed_dir, "file://feed_dir")

        assert feed_id.startswith("gtfs_")
        assert record_feed.call_args.kwargs["stop_count"] == 1

    @pytest.mark.asyncio
    async def test_import_from_path_missing_raises_file_not_found(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        missing = tmp_path / "missing.zip"
        with pytest.raises(FileNotFoundError):
            await importer._import_from_path(missing, "file://missing.zip")

    @pytest.mark.asyncio
    async def test_import_from_path_rejects_non_zip_non_directory(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        text_file = tmp_path / "not_zip.txt"
        text_file.write_text("nope", encoding="utf-8")

        with pytest.raises(ValueError, match="must be a \\.zip file or a directory"):
            await importer._import_from_path(text_file, "file://not_zip.txt")

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_missing_file_recreates_indexes(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\ns1,A,1,2\n")

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ) as recreate,
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1")

        recreate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_reads_batches_and_recreates_indexes(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "nested/stop_times.txt",
                "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n",
            )

        class FakeReader:
            def __init__(self):
                self._called = False

            def next_batches(self, _n):
                if self._called:
                    return []
                self._called = True
                return [
                    pl.DataFrame(
                        {
                            "trip_id": ["t1"],
                            "stop_id": ["s1"],
                            "arrival_time": ["08:00:00"],
                            "departure_time": ["08:01:00"],
                            "stop_sequence": [1],
                        }
                    )
                ]

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(importer, "_read_csv_batched", return_value=FakeReader()),
            patch.object(
                importer, "_copy_stop_times_batch", new_callable=AsyncMock
            ) as copy_batch,
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ) as recreate,
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1", batch_size=10)

        copy_batch.assert_awaited_once()
        recreate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_logs_progress_every_10_batches(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "stop_times.txt",
                "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n",
            )

        class FakeReader:
            def __init__(self):
                self._count = 0

            def next_batches(self, _n):
                if self._count >= 10:
                    return []
                self._count += 1
                return [
                    pl.DataFrame(
                        {
                            "trip_id": [f"t{self._count}"],
                            "stop_id": ["s1"],
                            "arrival_time": ["08:00:00"],
                            "departure_time": ["08:01:00"],
                            "stop_sequence": [1],
                        }
                    )
                ]

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(importer, "_read_csv_batched", return_value=FakeReader()),
            patch.object(importer, "_copy_stop_times_batch", new_callable=AsyncMock),
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ),
            patch("app.services.gtfs_feed.logger") as mock_logger,
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1", batch_size=10)

        assert any(
            "Copied %s stop_times batches..." in str(call.args[0])
            for call in mock_logger.info.call_args_list
        )

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_path_reads_batches_and_recreates_indexes(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        feed_dir = tmp_path / "feed_dir"
        feed_dir.mkdir()
        (feed_dir / "stop_times.txt").write_text(
            "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n",
            encoding="utf-8",
        )

        class FakeReader:
            def __init__(self):
                self._called = False

            def next_batches(self, _n):
                if self._called:
                    return []
                self._called = True
                return [
                    pl.DataFrame(
                        {
                            "trip_id": ["t1"],
                            "stop_id": ["s1"],
                            "arrival_time": ["08:00:00"],
                            "departure_time": ["08:01:00"],
                            "stop_sequence": [1],
                        }
                    )
                ]

        with (
            patch.object(importer, "_read_csv_batched", return_value=FakeReader()),
            patch.object(
                importer, "_copy_stop_times_batch", new_callable=AsyncMock
            ) as copy_batch,
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ) as recreate,
        ):
            await importer._copy_stop_times_from_path(feed_dir, "feed1", batch_size=10)

        copy_batch.assert_awaited_once()
        recreate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_path_missing_file_recreates_indexes(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        feed_dir = tmp_path / "feed_dir"
        feed_dir.mkdir()

        with patch.object(
            importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
        ) as recreate:
            await importer._copy_stop_times_from_path(feed_dir, "feed1", batch_size=10)

        recreate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_path_logs_progress_every_10_batches(
        self, tmp_path: Path
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        feed_dir = tmp_path / "feed_dir"
        feed_dir.mkdir()
        (feed_dir / "stop_times.txt").write_text(
            "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n",
            encoding="utf-8",
        )

        class FakeReader:
            def __init__(self):
                self._count = 0

            def next_batches(self, _n):
                if self._count >= 10:
                    return []
                self._count += 1
                return [
                    pl.DataFrame(
                        {
                            "trip_id": [f"t{self._count}"],
                            "stop_id": ["s1"],
                            "arrival_time": ["08:00:00"],
                            "departure_time": ["08:01:00"],
                            "stop_sequence": [1],
                        }
                    )
                ]

        with (
            patch.object(importer, "_read_csv_batched", return_value=FakeReader()),
            patch.object(importer, "_copy_stop_times_batch", new_callable=AsyncMock),
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ),
            patch("app.services.gtfs_feed.logger") as mock_logger,
        ):
            await importer._copy_stop_times_from_path(feed_dir, "feed1", batch_size=10)

        assert any(
            "Copied %s stop_times batches..." in str(call.args[0])
            for call in mock_logger.info.call_args_list
        )


class TestGTFSFeedImporterDatabaseCommands:
    @pytest.mark.asyncio
    async def test_truncate_all_tables_sets_logged_mode_when_configured(
        self, tmp_path: Path
    ):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path, unlogged=False))

        await importer._truncate_all_tables()

        executed_sql = [
            call.args[0].text if hasattr(call.args[0], "text") else str(call.args[0])
            for call in session.execute.call_args_list
        ]
        assert any("TRUNCATE TABLE gtfs_stop_times" in stmt for stmt in executed_sql)
        assert any("ALTER TABLE gtfs_stops SET LOGGED" in stmt for stmt in executed_sql)
        assert not any(
            "ALTER TABLE gtfs_stops SET UNLOGGED" in stmt for stmt in executed_sql
        )

    @pytest.mark.asyncio
    async def test_truncate_all_tables_sets_unlogged_mode_when_configured(
        self, tmp_path: Path
    ):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path, unlogged=True))

        await importer._truncate_all_tables()

        executed_sql = [
            call.args[0].text if hasattr(call.args[0], "text") else str(call.args[0])
            for call in session.execute.call_args_list
        ]
        assert any(
            "ALTER TABLE gtfs_stops SET UNLOGGED" in stmt for stmt in executed_sql
        )

    @pytest.mark.asyncio
    async def test_recreate_stop_times_indexes_and_fks_executes_expected_sql(
        self, tmp_path: Path
    ):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        await importer._recreate_stop_times_indexes_and_fks()

        executed_sql = [
            call.args[0].text if hasattr(call.args[0], "text") else str(call.args[0])
            for call in session.execute.call_args_list
        ]
        assert any(
            "CREATE INDEX IF NOT EXISTS idx_gtfs_stop_times_stop" in stmt
            for stmt in executed_sql
        )
        assert any(
            "ALTER TABLE gtfs_stop_times ADD CONSTRAINT gtfs_stop_times_trip_id_fkey"
            in stmt
            for stmt in executed_sql
        )
        session.commit.assert_awaited()


class TestGTFSFeedImporterCopyPolarsDf:
    @pytest.mark.asyncio
    async def test_copy_polars_df_writes_and_deletes_temp_file(self, tmp_path: Path):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        class FakeConn:
            copy_to_table = AsyncMock()

        with patch.object(
            importer,
            "_get_asyncpg_conn",
            new_callable=AsyncMock,
            return_value=FakeConn(),
        ):
            tmp_csv = tmp_path / "tmp.csv"

            class FakeTmp:
                def __init__(self, name: str):
                    self.name = name

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            with patch(
                "app.services.gtfs_feed.tempfile.NamedTemporaryFile",
                return_value=FakeTmp(str(tmp_csv)),
            ):
                df = pl.DataFrame({"a": [1]})
                await importer._copy_polars_df(df, "gtfs_table", columns=["a"])

        FakeConn.copy_to_table.assert_awaited_once()
        assert not tmp_csv.exists()

    @pytest.mark.asyncio
    async def test_copy_polars_df_skips_empty_df(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        empty_df = pl.DataFrame({"a": pl.Series([], dtype=pl.Int64)})

        with patch.object(
            importer, "_get_asyncpg_conn", new_callable=AsyncMock
        ) as get_conn:
            await importer._copy_polars_df(empty_df, "gtfs_table", columns=["a"])

        get_conn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_copy_polars_df_logs_when_temp_cleanup_fails(self, tmp_path: Path):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        class FakeConn:
            copy_to_table = AsyncMock()

        tmp_csv = tmp_path / "tmp.csv"

        class FakeTmp:
            def __init__(self, name: str):
                self.name = name

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with (
            patch.object(
                importer,
                "_get_asyncpg_conn",
                new_callable=AsyncMock,
                return_value=FakeConn(),
            ),
            patch(
                "app.services.gtfs_feed.tempfile.NamedTemporaryFile",
                return_value=FakeTmp(str(tmp_csv)),
            ),
            patch("app.services.gtfs_feed.Path.unlink", side_effect=OSError("nope")),
            patch("app.services.gtfs_feed.logger") as mock_logger,
        ):
            df = pl.DataFrame({"a": [1]})
            await importer._copy_polars_df(df, "gtfs_table", columns=["a"])

        assert mock_logger.warning.called


class TestGTFSFeedImporterNetworkAndPersistence:
    @pytest.mark.asyncio
    async def test_download_feed_writes_file(self, tmp_path: Path):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))

        class FakeResponse:
            content = b"zip-bytes"

            def raise_for_status(self):
                return None

        class FakeClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, _url):
                return FakeResponse()

        with patch("app.services.gtfs_feed.httpx.AsyncClient", FakeClient):
            path = await importer._download_feed("https://example.com/gtfs.zip")

        assert path.exists()
        assert path.read_bytes() == b"zip-bytes"
        assert path.suffix == ".zip"

    @pytest.mark.asyncio
    async def test_record_feed_info_executes_insert_and_commits(self, tmp_path: Path):
        session = _make_session()
        importer = GTFSFeedImporter(session, _make_settings(tmp_path))

        await importer._record_feed_info(
            feed_id="gtfs_1",
            feed_url="https://example.com/gtfs.zip",
            feed_start_date=date(2025, 1, 1),
            feed_end_date=date(2025, 1, 31),
            stop_count=1,
            route_count=2,
            trip_count=3,
        )

        session.execute.assert_awaited_once()
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_asyncpg_conn_returns_driver_connection(self, tmp_path: Path):
        driver = object()
        dbapi = MagicMock(driver_connection=driver)
        raw = AsyncMock(get_raw_connection=AsyncMock(return_value=dbapi))
        session = _make_session()
        session.connection = AsyncMock(return_value=raw)

        importer = GTFSFeedImporter(session, _make_settings(tmp_path))
        assert await importer._get_asyncpg_conn() is driver


class TestGTFSFeedImporterCsvBatchCompatibility:
    def test_read_csv_batched_uses_dtypes_fallback_when_schema_overrides_unsupported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        calls: list[dict] = []

        def fake_read_csv_batched(*args, **kwargs):
            calls.append(kwargs)
            if "schema_overrides" in kwargs:
                raise TypeError("schema_overrides unsupported")
            return MagicMock()

        monkeypatch.setattr(pl, "read_csv_batched", fake_read_csv_batched)
        importer._read_csv_batched("stop_times.txt", batch_size=10)

        assert len(calls) == 2
        assert "schema_overrides" in calls[0]
        assert "dtypes" in calls[1]


class TestGTFSFeedImporterZipExtraction:
    """Tests for ZIP file extraction compatibility with Polars.

    These tests verify that stop_times.txt is properly extracted to a temporary
    file before being read by Polars, since polars.read_csv_batched() doesn't
    support ZipExtFile objects directly.
    """

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_extracts_to_temp_file(self, tmp_path: Path):
        """Test that stop_times.txt is extracted to a temp file for processing."""
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"

        # Create a minimal stop_times.txt in a ZIP
        stop_times_content = (
            "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n"
            "t1,s1,08:00:00,08:01:00,1\n"
        )
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("stop_times.txt", stop_times_content)

        extracted_path = None

        def capture_read_csv_batched(source, *, batch_size):
            nonlocal extracted_path
            extracted_path = source
            # Return a fake reader that produces one batch
            return FakeReader()

        class FakeReader:
            def __init__(self):
                self._called = False

            def next_batches(self, _n):
                if self._called:
                    return []
                self._called = True
                return [
                    pl.DataFrame(
                        {
                            "trip_id": ["t1"],
                            "stop_id": ["s1"],
                            "arrival_time": ["08:00:00"],
                            "departure_time": ["08:01:00"],
                            "stop_sequence": [1],
                        }
                    )
                ]

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(importer, "_read_csv_batched", capture_read_csv_batched),
            patch.object(importer, "_copy_stop_times_batch", new_callable=AsyncMock),
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ),
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1", batch_size=10)

        # Verify that _read_csv_batched received a file path (string), not a ZipExtFile
        assert extracted_path is not None
        assert isinstance(extracted_path, str), (
            f"Expected file path string, got {type(extracted_path).__name__}"
        )
        # The temp file should end with .csv
        assert extracted_path.endswith(".csv")

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_cleans_up_temp_file(self, tmp_path: Path):
        """Test that the temporary file is cleaned up after processing."""
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"

        stop_times_content = (
            "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n"
            "t1,s1,08:00:00,08:01:00,1\n"
        )
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("stop_times.txt", stop_times_content)

        temp_file_path = None

        def capture_read_csv_batched(source, *, batch_size):
            nonlocal temp_file_path
            temp_file_path = source

            class FakeReader:
                def next_batches(self, _n):
                    return []

            return FakeReader()

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(importer, "_read_csv_batched", capture_read_csv_batched),
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ),
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1", batch_size=10)

        # Verify the temp file was cleaned up
        assert temp_file_path is not None
        assert not Path(temp_file_path).exists(), "Temp file should be deleted"

    @pytest.mark.asyncio
    async def test_copy_stop_times_from_zip_handles_nested_paths(self, tmp_path: Path):
        """Test extraction works for nested stop_times.txt paths in ZIP."""
        importer = GTFSFeedImporter(_make_session(), _make_settings(tmp_path))
        zip_path = tmp_path / "feed.zip"

        stop_times_content = (
            "trip_id,stop_id,arrival_time,departure_time,stop_sequence\n"
            "t1,s1,08:00:00,08:01:00,1\n"
        )
        # Create with nested path
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("gtfs/stop_times.txt", stop_times_content)

        extracted_path = None

        def capture_read_csv_batched(source, *, batch_size):
            nonlocal extracted_path
            extracted_path = source

            class FakeReader:
                def next_batches(self, _n):
                    return []

            return FakeReader()

        with (
            zipfile.ZipFile(zip_path) as zf,
            patch.object(importer, "_read_csv_batched", capture_read_csv_batched),
            patch.object(
                importer, "_recreate_stop_times_indexes_and_fks", new_callable=AsyncMock
            ),
        ):
            await importer._copy_stop_times_from_zip(zf, "feed1", batch_size=10)

        # Verify extraction worked for nested path
        assert extracted_path is not None
        assert isinstance(extracted_path, str)
