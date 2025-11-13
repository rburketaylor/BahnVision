"""Unit tests for StationsSyncJob batching and status reporting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, List

import pytest
import pytest_asyncio

from app.jobs import stations_sync
from app.services.mvg_client import Station


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession):
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeStationRepository:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[int] = []
        self.records: list[stations_sync.StationPayload] = []
        self._call_counter = 0

    async def upsert_stations(self, payloads: list[stations_sync.StationPayload]) -> list[stations_sync.StationPayload]:
        self._call_counter += 1
        self.calls.append(len(payloads))
        if self.fail_on_call and self._call_counter == self.fail_on_call:
            raise RuntimeError("batch failure")
        self.records.extend(payloads)
        return payloads

    async def count_stations(self) -> int:
        return len(self.records)

    async def get_all_stations(self) -> list[Any]:
        return [
            type("StationRow", (), {"station_id": payload.station_id, "name": payload.name, "place": payload.place})
            for payload in self.records
        ]


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _patch_session_factory(monkeypatch: pytest.MonkeyPatch, session: FakeSession) -> None:
    def factory():
        return FakeSessionContext(session)

    monkeypatch.setattr(stations_sync, "AsyncSessionFactory", factory)


def _patch_repository(monkeypatch: pytest.MonkeyPatch, repo: FakeStationRepository) -> None:
    monkeypatch.setattr(stations_sync, "StationRepository", lambda session: repo)


def _patch_mvg_client(monkeypatch: pytest.MonkeyPatch, stations: List[Station]) -> None:
    class FakeMVGClient:
        async def get_all_stations(self_inner):
            return stations

    monkeypatch.setattr(stations_sync, "MVGClient", FakeMVGClient)


def _build_station(idx: int) -> Station:
    return Station(
        id=f"de:09162:{idx}",
        name=f"Station {idx}",
        place="Munich",
        latitude=48.0 + idx * 0.01,
        longitude=11.0 + idx * 0.01,
    )


@pytest.mark.asyncio
async def test_run_sync_batches_success(monkeypatch):
    stations = [_build_station(i) for i in range(5)]
    fake_repo = FakeStationRepository()
    fake_session = FakeSession()

    _patch_mvg_client(monkeypatch, stations)
    _patch_repository(monkeypatch, fake_repo)
    _patch_session_factory(monkeypatch, fake_session)

    job = stations_sync.StationsSyncJob(batch_size=2)
    stats = await job.run_sync()

    assert stats == {"total": 5, "upserted": 5, "errors": 0}
    assert fake_repo.calls == [2, 2, 1]
    assert fake_session.commit_calls == 1


@pytest.mark.asyncio
async def test_run_sync_records_batch_errors(monkeypatch):
    stations = [_build_station(i) for i in range(5)]
    fake_repo = FakeStationRepository(fail_on_call=2)
    fake_session = FakeSession()

    _patch_mvg_client(monkeypatch, stations)
    _patch_repository(monkeypatch, fake_repo)
    _patch_session_factory(monkeypatch, fake_session)

    job = stations_sync.StationsSyncJob(batch_size=2)
    stats = await job.run_sync()

    assert stats["total"] == 5
    assert stats["upserted"] == 3  # third batch still processed after failure
    assert stats["errors"] == 1
    assert fake_repo.calls == [2, 2, 1]


@pytest.mark.asyncio
async def test_get_sync_status_returns_sample(monkeypatch):
    fake_repo = FakeStationRepository()
    fake_repo.records = [
        stations_sync.StationPayload(
            station_id=f"station-{i}",
            name=f"Name {i}",
            place=f"Place {i}",
            latitude=48.0,
            longitude=11.0,
        )
        for i in range(6)
    ]

    _patch_repository(monkeypatch, fake_repo)
    _patch_session_factory(monkeypatch, FakeSession())

    status = await stations_sync.StationsSyncJob().get_sync_status()

    assert status["total_stations"] == 6
    assert len(status["sample_stations"]) == 5
    assert status["sample_stations"][0]["id"] == "station-0"


@pytest.mark.asyncio
async def test_get_sync_status_handles_errors(monkeypatch):
    class ErrorRepo:
        def __init__(self, *_):
            pass

        async def count_stations(self):
            raise RuntimeError("db down")

        async def get_all_stations(self):
            return []

    _patch_repository(monkeypatch, ErrorRepo())
    _patch_session_factory(monkeypatch, FakeSession())

    status = await stations_sync.StationsSyncJob().get_sync_status()

    assert status["total_stations"] == 0
    assert status["sample_stations"] == []
    assert "error" in status and "db down" in status["error"]
