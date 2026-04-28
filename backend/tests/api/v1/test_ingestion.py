"""API tests for ingestion status endpoint."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import FastAPI
import httpx
import pytest

from app.api.v1.endpoints.ingestion import router as ingestion_router
from app.core.database import get_session
from app.models.gtfs import GTFSFeedInfo


class _FakeProgressTracker:
    def __init__(self, payload=None):
        self.payload = payload or {
            "state": "idle",
            "phase": None,
            "message": None,
            "percent": None,
            "rows_processed": None,
            "rows_total": None,
            "started_at": None,
            "updated_at": None,
            "finished_at": None,
            "error_type": None,
            "error_message": None,
        }

    async def get(self) -> dict:
        return self.payload


class _FakeResult:
    def __init__(self, *, one_or_none=None, scalar_value=None):
        self._one_or_none = one_or_none
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self._one_or_none

    def scalar(self):
        return self._scalar_value


class _FakeSession:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.execute_calls = 0

    async def execute(self, *_args, **_kwargs):
        self.execute_calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeHarvester:
    def get_status(self) -> dict:
        return {
            "is_running": True,
            "last_harvest_at": datetime(2026, 1, 20, 10, 0, tzinfo=timezone.utc),
            "stations_updated_last_harvest": 15,
        }


def _build_app(session: _FakeSession, *, harvester=None) -> FastAPI:
    app = FastAPI()
    app.include_router(ingestion_router, prefix="/api/v1/system")

    async def _session_override():
        yield session

    app.dependency_overrides[get_session] = _session_override
    if harvester is not None:
        app.state.harvester = harvester

    return app


async def _get_ingestion_status(
    app: FastAPI, *, raise_server_exceptions: bool = True
) -> httpx.Response:
    transport = httpx.ASGITransport(
        app=app, raise_app_exceptions=raise_server_exceptions
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/api/v1/system/ingestion-status")


@pytest.fixture(autouse=True)
def _mock_progress_tracker(monkeypatch):
    tracker = _FakeProgressTracker()
    monkeypatch.setattr(
        "app.api.v1.endpoints.ingestion.get_gtfs_import_progress_tracker",
        lambda: tracker,
    )
    return tracker


@pytest.mark.asyncio
async def test_ingestion_status_success_uses_fast_row_estimate():
    feed_info = GTFSFeedInfo(
        feed_id="gtfs_20260120_100000",
        feed_url="https://example.com/gtfs.zip",
        downloaded_at=datetime(2026, 1, 20, 9, 0, tzinfo=timezone.utc),
        feed_start_date=date(2026, 1, 1),
        feed_end_date=date(2026, 12, 31),
        stop_count=100,
        route_count=20,
        trip_count=500,
    )
    session = _FakeSession(
        outcomes=[
            _FakeResult(one_or_none=feed_info),
            _FakeResult(one_or_none=1234),
        ]
    )

    app = _build_app(session, harvester=_FakeHarvester())
    response = await _get_ingestion_status(app)

    assert response.status_code == 200
    payload = response.json()

    assert payload["gtfs_feed"]["feed_id"] == "gtfs_20260120_100000"
    assert payload["gtfs_feed"]["is_expired"] is False
    assert payload["gtfs_feed"]["import_progress"]["state"] == "idle"

    assert payload["gtfs_rt_harvester"]["is_running"] is True
    assert payload["gtfs_rt_harvester"]["stations_updated_last_harvest"] == 15
    assert payload["gtfs_rt_harvester"]["total_stats_records"] == 1234

    # Feed select + fast estimate query.
    assert session.execute_calls == 2


@pytest.mark.asyncio
async def test_ingestion_status_falls_back_to_exact_count_when_estimates_fail():
    feed_info = GTFSFeedInfo(
        feed_id="gtfs_20260110_010000",
        feed_url="https://example.com/gtfs.zip",
        downloaded_at=datetime(2026, 1, 10, 1, 0, tzinfo=timezone.utc),
        feed_start_date=date(2025, 1, 1),
        feed_end_date=date(2025, 12, 31),
        stop_count=80,
        route_count=18,
        trip_count=420,
    )
    session = _FakeSession(
        outcomes=[
            _FakeResult(one_or_none=feed_info),
            RuntimeError("pg_stat_all_tables unavailable"),
            _FakeResult(one_or_none=None),
            _FakeResult(scalar_value=77),
        ]
    )

    app = _build_app(session)
    response = await _get_ingestion_status(app)

    assert response.status_code == 200
    payload = response.json()

    # feed_end_date in 2025 is expired relative to current UTC date.
    assert payload["gtfs_feed"]["is_expired"] is True
    assert payload["gtfs_rt_harvester"]["is_running"] is False
    assert payload["gtfs_rt_harvester"]["total_stats_records"] == 77

    # Feed select + estimate attempt + reltuples attempt + exact count.
    assert session.execute_calls == 4


@pytest.mark.asyncio
async def test_ingestion_status_returns_500_when_all_count_paths_fail():
    feed_info = GTFSFeedInfo(
        feed_id="gtfs_20260108_010000",
        downloaded_at=datetime(2026, 1, 8, 1, 0, tzinfo=timezone.utc),
    )
    session = _FakeSession(
        outcomes=[
            _FakeResult(one_or_none=feed_info),
            RuntimeError("pg_stat failure"),
            RuntimeError("pg_class failure"),
            RuntimeError("count failure"),
        ]
    )

    app = _build_app(session)
    response = await _get_ingestion_status(app, raise_server_exceptions=False)

    assert response.status_code == 500


@pytest.mark.asyncio
async def test_ingestion_status_includes_running_import_progress(
    _mock_progress_tracker,
):
    _mock_progress_tracker.payload = {
        "state": "running",
        "phase": "copy_stop_times",
        "message": "Copying stop_times.txt",
        "percent": 72.4,
        "rows_processed": 36_200_000,
        "rows_total": 50_000_000,
        "started_at": "2026-01-20T10:00:00+00:00",
        "updated_at": "2026-01-20T10:05:00+00:00",
        "finished_at": None,
        "error_type": None,
        "error_message": None,
    }
    session = _FakeSession(
        outcomes=[
            _FakeResult(one_or_none=None),
            _FakeResult(one_or_none=0),
        ]
    )

    app = _build_app(session)
    response = await _get_ingestion_status(app)

    assert response.status_code == 200
    progress = response.json()["gtfs_feed"]["import_progress"]
    assert progress["state"] == "running"
    assert progress["phase"] == "copy_stop_times"
    assert progress["percent"] == 72.4
    assert progress["rows_processed"] == 36_200_000


@pytest.mark.asyncio
async def test_ingestion_status_includes_failed_import_progress(_mock_progress_tracker):
    _mock_progress_tracker.payload = {
        "state": "failed",
        "phase": "validate",
        "message": "Validating GTFS feed",
        "percent": 20,
        "rows_processed": None,
        "rows_total": None,
        "started_at": "2026-01-20T10:00:00+00:00",
        "updated_at": "2026-01-20T10:01:00+00:00",
        "finished_at": "2026-01-20T10:01:00+00:00",
        "error_type": "GTFSFeedValidationError",
        "error_message": "stops.txt is required and cannot be empty",
    }
    session = _FakeSession(
        outcomes=[
            _FakeResult(one_or_none=None),
            _FakeResult(one_or_none=0),
        ]
    )

    app = _build_app(session)
    response = await _get_ingestion_status(app)

    assert response.status_code == 200
    progress = response.json()["gtfs_feed"]["import_progress"]
    assert progress["state"] == "failed"
    assert progress["error_type"] == "GTFSFeedValidationError"
