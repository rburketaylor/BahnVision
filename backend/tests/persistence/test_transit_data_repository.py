"""Integration tests for TransitDataRepository behavior."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.persistence import models
from app.persistence.repositories import (
    DepartureObservationPayload,
    DepartureWeatherLinkPayload,
    StationPayload,
    TransitDataRepository,
    TransitLinePayload,
    WeatherObservationPayload,
)


TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://bahnvision:bahnvision@localhost:5432/bahnvision",
)


async def _truncate_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                TRUNCATE TABLE
                    departure_weather_links,
                    weather_observations,
                    departure_observations,
                    route_snapshots,
                    ingestion_runs,
                    transit_lines,
                    stations
                RESTART IDENTITY CASCADE
                """
            )
        )


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await _truncate_tables(engine)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await _truncate_tables(engine)
    await engine.dispose()


def _station_payload() -> StationPayload:
    return StationPayload(
        station_id="de:09162:1",
        name="Marienplatz",
        place="Munich",
        latitude=48.137154,
        longitude=11.576124,
        transport_modes=("UBAHN", "SBAHN"),
        timezone="Europe/Berlin",
    )


def _transit_line_payload() -> TransitLinePayload:
    return TransitLinePayload(
        line_id="U3",
        transport_mode=models.TransportMode.UBAHN,
        operator="MVG",
        description="U3 main line",
        color_hex="#FF5500",
    )


@pytest.mark.asyncio
async def test_record_departure_and_weather_observations(db_session):
    repo = TransitDataRepository(db_session)
    await repo.upsert_station(_station_payload())
    await repo.upsert_transit_line(_transit_line_payload())

    ingestion_run = await repo.create_ingestion_run(
        job_name="stations_sync",
        source=models.IngestionSource.MVG_DEPARTURES,
    )

    now = datetime.now(timezone.utc)
    departures_count = await repo.record_departure_observations(
        [
            DepartureObservationPayload(
                station_id="de:09162:1",
                line_id="U3",
                transport_mode=models.TransportMode.UBAHN,
                planned_departure=now + timedelta(minutes=5),
                observed_departure=now + timedelta(minutes=6),
                ingestion_run_id=ingestion_run.id,
                direction="North",
                destination="Olympiazentrum",
                delay_seconds=60,
                platform="1",
                status=models.DepartureStatus.DELAYED,
                remarks=("crowded",),
                raw_payload={"source": "test"},
            ),
            DepartureObservationPayload(
                station_id="de:09162:1",
                line_id="U3",
                transport_mode=models.TransportMode.UBAHN,
                planned_departure=now + timedelta(minutes=10),
                observed_departure=now + timedelta(minutes=10),
                ingestion_run_id=ingestion_run.id,
                direction="South",
                destination="Fürstenried West",
                delay_seconds=0,
                platform="2",
                status=models.DepartureStatus.ON_TIME,
                remarks=("clear",),
            ),
        ]
    )

    assert departures_count == 2

    weather_count = await repo.record_weather_observations(
        [
            WeatherObservationPayload(
                provider="dwd",
                observed_at=now,
                latitude=48.137154,
                longitude=11.576124,
                ingestion_run_id=ingestion_run.id,
                station_id="de:09162:1",
                temperature_c=18.5,
                humidity_percent=55.0,
                wind_speed_mps=3.2,
                precipitation_mm=0.0,
                condition=models.WeatherCondition.CLEAR,
                alerts=("uv",),
                source_payload={"station": "test"},
            )
        ]
    )

    assert weather_count == 1

    recent = await repo.fetch_recent_departures(limit=5)
    assert len(recent) == 2
    assert recent[0].planned_departure >= recent[1].planned_departure
    assert all(departure.station_id == "de:09162:1" for departure in recent)


@pytest.mark.asyncio
async def test_link_departure_weather_is_idempotent(db_session):
    repo = TransitDataRepository(db_session)
    await repo.upsert_station(_station_payload())
    await repo.upsert_transit_line(_transit_line_payload())
    ingestion_run = await repo.create_ingestion_run(
        job_name="stations_sync",
        source=models.IngestionSource.MVG_DEPARTURES,
    )

    now = datetime.now(timezone.utc)
    await repo.record_departure_observations(
        [
            DepartureObservationPayload(
                station_id="de:09162:1",
                line_id="U3",
                transport_mode=models.TransportMode.UBAHN,
                planned_departure=now,
                observed_departure=now,
                ingestion_run_id=ingestion_run.id,
                status=models.DepartureStatus.ON_TIME,
                direction="North",
                destination="Olympiazentrum",
            )
        ]
    )
    await repo.record_weather_observations(
        [
            WeatherObservationPayload(
                provider="dwd",
                observed_at=now,
                latitude=48.137154,
                longitude=11.576124,
                station_id="de:09162:1",
                ingestion_run_id=ingestion_run.id,
                condition=models.WeatherCondition.CLEAR,
            )
        ]
    )

    departure_id = (
        await db_session.execute(select(models.DepartureObservation.id))
    ).scalar_one()
    weather_id = (
        await db_session.execute(select(models.WeatherObservation.id))
    ).scalar_one()

    link_payload = [
        DepartureWeatherLinkPayload(
            departure_id=departure_id,
            weather_id=weather_id,
            offset_minutes=5,
            relationship_type="nearest",
        )
    ]

    first_insert = await repo.link_departure_weather(link_payload)
    second_insert = await repo.link_departure_weather(link_payload)

    assert first_insert == 1
    assert second_insert == 1

    total_links = await db_session.execute(
        select(func.count(models.DepartureWeatherLink.departure_id))
    )
    assert total_links.scalar_one() == 1
