"""Integration tests for StationRepository against Postgres.

These tests require a running PostgreSQL database. They will be automatically
skipped if the database is not available (uses shared conftest.py).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.persistence.repositories import StationPayload, StationRepository

# All tests in this file are integration tests
pytestmark = pytest.mark.integration


def _build_station_payload(
    idx: int, *, name: str | None = None, place: str = "Munich"
) -> StationPayload:
    return StationPayload(
        station_id=f"de:09162:{idx}",
        name=name or f"Station {idx}",
        place=place,
        latitude=48.0 + idx * 0.001,
        longitude=11.0 + idx * 0.001,
        transport_modes=("UBAHN", "BUS") if idx % 2 == 0 else ("UBAHN",),
        timezone="Europe/Berlin",
    )


@pytest.mark.asyncio
async def test_upsert_stations_handles_large_batches(db_session):
    """Bulk upsert should chunk inserts when exceeding asyncpg param limits."""
    repo = StationRepository(db_session)
    params_per_row = 7
    chunk_threshold = (32767 // params_per_row) + 5  # exceed internal batch size

    payloads = [_build_station_payload(i) for i in range(chunk_threshold)]

    inserted = await repo.upsert_stations(payloads)

    assert len(inserted) == chunk_threshold
    assert await repo.count_stations() == chunk_threshold

    target_id = payloads[10].station_id
    updated_payload = replace(payloads[10], name="Station 10 Updated")
    await repo.upsert_stations([updated_payload])

    db_session.expire_all()
    updated_station = await repo.get_station_by_id(target_id)
    assert updated_station is not None
    assert updated_station.name == "Station 10 Updated"


@pytest.mark.asyncio
async def test_search_and_delete_behaviors(db_session):
    """Ensure search ordering prioritizes exact matches and delete returns flags."""
    repo = StationRepository(db_session)
    await repo.upsert_stations(
        [
            _build_station_payload(1, name="Marienplatz"),
            _build_station_payload(2, name="Marienplatz Nord"),
            _build_station_payload(3, name="Pasing", place="Marienplatz District"),
        ]
    )

    results = await repo.search_stations("Marienplatz", limit=5)
    ordered_ids = [station.station_id for station in results]
    assert ordered_ids == ["de:09162:1", "de:09162:2", "de:09162:3"]

    assert await repo.count_stations() == 3
    assert await repo.delete_station("de:09162:2") is True
    assert await repo.count_stations() == 2
    assert await repo.delete_station("does-not-exist") is False
