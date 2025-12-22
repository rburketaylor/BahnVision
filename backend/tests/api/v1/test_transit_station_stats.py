"""
Additional unit tests for Transit stops endpoints.

Targets station stats/trends + nearby endpoints to raise meaningful coverage by
exercising response shaping, headers, and not-found branches.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import api_router
from app.api.v1.endpoints.transit import stops as stops_module
from app.models.station_stats import StationStats, StationTrends, TrendDataPoint


@dataclass
class FakeStopRow:
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None


class FakeStationStatsService:
    def __init__(self, *, stats: StationStats | None, trends: StationTrends | None):
        self._stats = stats
        self._trends = trends
        self.calls: list[tuple] = []

    async def get_station_stats(self, stop_id: str, time_range: str):
        self.calls.append(("stats", stop_id, time_range))
        return self._stats

    async def get_station_trends(self, stop_id: str, time_range: str, granularity: str):
        self.calls.append(("trends", stop_id, time_range, granularity))
        return self._trends


class FakeGTFSScheduleService:
    def __init__(self, _db):
        pass

    async def get_nearby_stops(
        self, _lat: float, _lon: float, _radius_km: float, _limit: int
    ):
        return [
            FakeStopRow(stop_id="s1", stop_name="A", stop_lat=1.0, stop_lon=2.0),
            FakeStopRow(stop_id="s2", stop_name="B", stop_lat=None, stop_lon=None),
        ]


@pytest.fixture
def test_app():
    @asynccontextmanager
    async def null_lifespan(app: FastAPI):
        yield {}

    app = FastAPI(lifespan=null_lifespan)
    app.include_router(api_router, prefix="/api/v1")
    yield app
    app.dependency_overrides.clear()


def _client_for(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestStationStatsEndpoint:
    def test_station_stats_returns_200_and_cache_header(self, test_app: FastAPI):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        fake_service = FakeStationStatsService(
            stats=StationStats(
                station_id="s1",
                station_name="A",
                time_range="24h",
                total_departures=10,
                cancelled_count=1,
                cancellation_rate=0.1,
                delayed_count=2,
                delay_rate=0.2,
                network_avg_cancellation_rate=None,
                network_avg_delay_rate=None,
                performance_score=80,
                by_transport=[],
                data_from=now,
                data_to=now,
            ),
            trends=None,
        )
        test_app.dependency_overrides[stops_module.get_station_stats_service] = (
            lambda: fake_service
        )
        client = _client_for(test_app)

        resp = client.get("/api/v1/transit/stops/s1/stats?time_range=24h")
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=300"
        assert resp.json()["station_id"] == "s1"

    def test_station_stats_returns_404_when_missing(self, test_app: FastAPI):
        fake_service = FakeStationStatsService(stats=None, trends=None)
        test_app.dependency_overrides[stops_module.get_station_stats_service] = (
            lambda: fake_service
        )
        client = _client_for(test_app)

        resp = client.get("/api/v1/transit/stops/missing/stats")
        assert resp.status_code == 404


class TestStationTrendsEndpoint:
    def test_station_trends_returns_200_and_cache_header(self, test_app: FastAPI):
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        fake_service = FakeStationStatsService(
            stats=None,
            trends=StationTrends(
                station_id="s1",
                station_name="A",
                time_range="24h",
                granularity="daily",
                data_points=[
                    TrendDataPoint(
                        timestamp=now,
                        total_departures=10,
                        cancelled_count=1,
                        cancellation_rate=0.1,
                        delayed_count=2,
                        delay_rate=0.2,
                    )
                ],
                avg_cancellation_rate=0.1,
                avg_delay_rate=0.2,
                peak_cancellation_rate=0.1,
                peak_delay_rate=0.2,
                data_from=now,
                data_to=now,
            ),
        )
        test_app.dependency_overrides[stops_module.get_station_stats_service] = (
            lambda: fake_service
        )
        client = _client_for(test_app)

        resp = client.get(
            "/api/v1/transit/stops/s1/trends?time_range=24h&granularity=daily"
        )
        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=300"
        assert resp.json()["data_points"][0]["total_departures"] == 10

    def test_station_trends_returns_404_when_missing(self, test_app: FastAPI):
        fake_service = FakeStationStatsService(stats=None, trends=None)
        test_app.dependency_overrides[stops_module.get_station_stats_service] = (
            lambda: fake_service
        )
        client = _client_for(test_app)

        resp = client.get("/api/v1/transit/stops/missing/trends")
        assert resp.status_code == 404


class TestNearbyStopsEndpoint:
    def test_nearby_stops_converts_rows_and_sets_cache_header(
        self, test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeSettings:
            gtfs_stop_cache_ttl_seconds = 123

        test_app.dependency_overrides[stops_module.get_session] = lambda: object()
        test_app.dependency_overrides[stops_module.get_cache_service] = lambda: object()

        monkeypatch.setattr(
            stops_module, "GTFSScheduleService", FakeGTFSScheduleService
        )
        monkeypatch.setattr(stops_module, "get_settings", lambda: FakeSettings())
        client = _client_for(test_app)
        resp = client.get("/api/v1/transit/stops/nearby?latitude=1&longitude=2")

        assert resp.status_code == 200
        assert resp.headers["Cache-Control"] == "public, max-age=123"
        data = resp.json()
        assert data[0]["id"] == "s1"
        assert data[0]["latitude"] == 1.0
        assert data[1]["latitude"] == 0.0


class TestStopsDependencyFactories:
    @pytest.mark.asyncio
    async def test_get_transit_data_service_wires_dependencies(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        fake_cache = object()
        fake_db = object()
        schedule_instance = object()
        realtime_instance = object()
        service_instance = object()

        schedule_cls = MagicMock(return_value=schedule_instance)
        realtime_cls = MagicMock(return_value=realtime_instance)
        transit_data_cls = MagicMock(return_value=service_instance)

        monkeypatch.setattr(stops_module, "GTFSScheduleService", schedule_cls)
        monkeypatch.setattr(stops_module, "GtfsRealtimeService", realtime_cls)
        monkeypatch.setattr(stops_module, "TransitDataService", transit_data_cls)

        result = await stops_module.get_transit_data_service(
            cache=fake_cache, db=fake_db
        )

        assert result is service_instance
        schedule_cls.assert_called_once_with(fake_db)
        realtime_cls.assert_called_once_with(fake_cache)
        transit_data_cls.assert_called_once_with(
            fake_cache, schedule_instance, realtime_instance, fake_db
        )

    @pytest.mark.asyncio
    async def test_get_station_stats_service_wires_dependencies(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        fake_db = object()
        schedule_instance = object()
        service_instance = object()

        schedule_cls = MagicMock(return_value=schedule_instance)
        stats_service_cls = MagicMock(return_value=service_instance)

        monkeypatch.setattr(stops_module, "GTFSScheduleService", schedule_cls)
        monkeypatch.setattr(stops_module, "StationStatsService", stats_service_cls)

        result = await stops_module.get_station_stats_service(db=fake_db)

        assert result is service_instance
        schedule_cls.assert_called_once_with(fake_db)
        stats_service_cls.assert_called_once_with(fake_db, schedule_instance)
