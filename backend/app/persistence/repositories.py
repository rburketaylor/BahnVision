from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence import models


@dataclass(slots=True, kw_only=True)
class StationPayload:
    station_id: str
    name: str
    place: str
    latitude: float
    longitude: float
    transport_modes: Sequence[str] = field(default_factory=tuple)
    timezone: str = "Europe/Berlin"


@dataclass(slots=True, kw_only=True)
class TransitLinePayload:
    line_id: str
    transport_mode: models.TransportMode
    operator: str = "UNKNOWN"
    description: str | None = None
    color_hex: str | None = None


@dataclass(slots=True, kw_only=True)
class DepartureObservationPayload:
    station_id: str
    line_id: str
    transport_mode: models.TransportMode
    planned_departure: datetime
    ingestion_run_id: int | None = None
    direction: str | None = None
    destination: str | None = None
    observed_departure: datetime | None = None
    delay_seconds: int | None = None
    platform: str | None = None
    status: models.DepartureStatus = models.DepartureStatus.UNKNOWN
    cancellation_reason: str | None = None
    remarks: Sequence[str] = field(default_factory=tuple)
    crowding_level: int | None = None
    source: str = "transit"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(slots=True, kw_only=True)
class WeatherObservationPayload:
    provider: str
    observed_at: datetime
    latitude: float
    longitude: float
    ingestion_run_id: int | None = None
    station_id: str | None = None
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: float | None = None
    wind_speed_mps: float | None = None
    wind_gust_mps: float | None = None
    wind_direction_deg: int | None = None
    pressure_hpa: float | None = None
    visibility_km: float | None = None
    precipitation_mm: float | None = None
    precipitation_type: str | None = None
    condition: models.WeatherCondition = models.WeatherCondition.UNKNOWN
    alerts: Sequence[str] = field(default_factory=tuple)
    source_payload: dict[str, Any] | None = None


@dataclass(slots=True, kw_only=True)
class DepartureWeatherLinkPayload:
    departure_id: int
    weather_id: int
    offset_minutes: int
    relationship_type: str = "closest"


class TransitDataRepository:
    """Encapsulates persistence logic for historical transit and weather data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_station(self, payload: StationPayload) -> models.Station | None:
        stmt = insert(models.Station).values(
            station_id=payload.station_id,
            name=payload.name,
            place=payload.place,
            latitude=payload.latitude,
            longitude=payload.longitude,
            transport_modes=list(payload.transport_modes),
            timezone=payload.timezone,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[models.Station.station_id],
            set_={
                "name": stmt.excluded.name,
                "place": stmt.excluded.place,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "transport_modes": stmt.excluded.transport_modes,
                "timezone": stmt.excluded.timezone,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        await self._session.execute(stmt)
        return await self._session.get(models.Station, payload.station_id)

    async def upsert_transit_line(
        self, payload: TransitLinePayload
    ) -> models.TransitLine | None:
        stmt = insert(models.TransitLine).values(
            line_id=payload.line_id,
            transport_mode=payload.transport_mode,
            operator=payload.operator,
            description=payload.description,
            color_hex=payload.color_hex,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=[models.TransitLine.line_id])
        await self._session.execute(stmt)
        transit_line = await self._session.get(models.TransitLine, payload.line_id)
        if transit_line is None:
            # If insert skipped (existing row), update mutable columns.
            await self._session.execute(
                update(models.TransitLine)
                .where(models.TransitLine.line_id == payload.line_id)
                .values(
                    transport_mode=payload.transport_mode,
                    operator=payload.operator,
                    description=payload.description,
                    color_hex=payload.color_hex,
                )
            )
            transit_line = await self._session.get(models.TransitLine, payload.line_id)
        return transit_line

    async def create_ingestion_run(
        self,
        *,
        job_name: str,
        source: str,
        started_at: datetime | None = None,
        context: dict[str, Any] | None = None,
    ) -> models.IngestionRun:
        ingestion_run = models.IngestionRun(
            job_name=job_name,
            source=source,
            started_at=started_at or datetime.now(timezone.utc),
            context=context,
        )
        self._session.add(ingestion_run)
        await self._session.flush()
        return ingestion_run

    async def complete_ingestion_run(
        self,
        ingestion_run_id: int,
        *,
        status: str = models.IngestionStatus.SUCCESS.value,
        records_inserted: int = 0,
        completed_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        await self._session.execute(
            update(models.IngestionRun)
            .where(models.IngestionRun.id == ingestion_run_id)
            .values(
                status=status,
                records_inserted=records_inserted,
                completed_at=completed_at or datetime.now(timezone.utc),
                notes=notes,
            )
        )

    async def record_departure_observations(
        self, departures: Iterable[DepartureObservationPayload]
    ) -> int:
        rows = [
            {
                "station_id": item.station_id,
                "line_id": item.line_id,
                "ingestion_run_id": item.ingestion_run_id,
                "direction": item.direction,
                "destination": item.destination,
                "planned_departure": item.planned_departure,
                "observed_departure": item.observed_departure,
                "delay_seconds": item.delay_seconds,
                "platform": item.platform,
                "transport_mode": item.transport_mode,
                "status": item.status,
                "cancellation_reason": item.cancellation_reason,
                "remarks": list(item.remarks),
                "crowding_level": item.crowding_level,
                "source": item.source,
                "valid_from": item.valid_from,
                "valid_to": item.valid_to,
                "raw_payload": item.raw_payload,
            }
            for item in departures
        ]
        if not rows:
            return 0
        stmt = insert(models.DepartureObservation).values(rows)
        result = await self._session.execute(
            stmt.returning(models.DepartureObservation.id)
        )
        return len(list(result.scalars()))

    async def record_weather_observations(
        self, weather_samples: Iterable[WeatherObservationPayload]
    ) -> int:
        rows = [
            {
                "provider": item.provider,
                "observed_at": item.observed_at,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "ingestion_run_id": item.ingestion_run_id,
                "station_id": item.station_id,
                "temperature_c": item.temperature_c,
                "feels_like_c": item.feels_like_c,
                "humidity_percent": item.humidity_percent,
                "wind_speed_mps": item.wind_speed_mps,
                "wind_gust_mps": item.wind_gust_mps,
                "wind_direction_deg": item.wind_direction_deg,
                "pressure_hpa": item.pressure_hpa,
                "visibility_km": item.visibility_km,
                "precipitation_mm": item.precipitation_mm,
                "precipitation_type": item.precipitation_type,
                "condition": item.condition,
                "alerts": list(item.alerts),
                "source_payload": item.source_payload,
            }
            for item in weather_samples
        ]
        if not rows:
            return 0
        stmt = insert(models.WeatherObservation).values(rows)
        result = await self._session.execute(
            stmt.returning(models.WeatherObservation.id)
        )
        return len(list(result.scalars()))

    async def link_departure_weather(
        self, links: Iterable[DepartureWeatherLinkPayload]
    ) -> int:
        rows = [
            {
                "departure_id": item.departure_id,
                "weather_id": item.weather_id,
                "offset_minutes": item.offset_minutes,
                "relationship_type": item.relationship_type,
            }
            for item in links
        ]
        if not rows:
            return 0
        stmt = insert(models.DepartureWeatherLink).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=[
                models.DepartureWeatherLink.departure_id,
                models.DepartureWeatherLink.weather_id,
            ]
        )
        await self._session.execute(stmt)
        return len(rows)

    async def fetch_recent_departures(
        self,
        *,
        limit: int = 100,
    ) -> list[models.DepartureObservation]:
        stmt = (
            select(models.DepartureObservation)
            .order_by(models.DepartureObservation.planned_departure.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class StationRepository:
    """Repository for station persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_station(self, payload: StationPayload) -> models.Station:
        """Insert or update a station."""
        stmt = insert(models.Station).values(
            station_id=payload.station_id,
            name=payload.name,
            place=payload.place,
            latitude=payload.latitude,
            longitude=payload.longitude,
            transport_modes=list(payload.transport_modes),
            timezone=payload.timezone,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[models.Station.station_id],
            set_={
                "name": stmt.excluded.name,
                "place": stmt.excluded.place,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "transport_modes": stmt.excluded.transport_modes,
                "timezone": stmt.excluded.timezone,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the upserted station
        select_stmt = select(models.Station).where(
            models.Station.station_id == payload.station_id
        )
        station_result = await self._session.execute(select_stmt)
        station = station_result.scalar_one()

        await self._session.commit()
        return station

    async def upsert_stations(
        self, payloads: list[StationPayload]
    ) -> list[models.Station]:
        """Bulk insert or update multiple stations."""
        if not payloads:
            return []

        rows = [
            {
                "station_id": payload.station_id,
                "name": payload.name,
                "place": payload.place,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "transport_modes": list(payload.transport_modes),
                "timezone": payload.timezone,
            }
            for payload in payloads
        ]

        # asyncpg caps positional parameters at 32767, so chunk the bulk upsert
        # to avoid InterfaceError when persisting the ~4.7k stations.
        params_per_row = 7
        max_rows_per_batch = 32767 // params_per_row
        chunked_rows = [
            rows[i : i + max_rows_per_batch]
            for i in range(0, len(rows), max_rows_per_batch)
        ]

        for batch in chunked_rows:
            stmt = insert(models.Station).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=[models.Station.station_id],
                set_={
                    "name": stmt.excluded.name,
                    "place": stmt.excluded.place,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "transport_modes": stmt.excluded.transport_modes,
                    "timezone": stmt.excluded.timezone,
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(stmt)

        await self._session.flush()

        # Return the upserted stations (chunked to respect asyncpg param limits)
        station_ids = [payload.station_id for payload in payloads]
        max_params = 32767
        stations: list[models.Station] = []
        for i in range(0, len(station_ids), max_params):
            chunk = station_ids[i : i + max_params]
            select_stmt = select(models.Station).where(
                models.Station.station_id.in_(chunk)
            )
            result = await self._session.execute(select_stmt)
            stations.extend(result.scalars().all())

        await self._session.commit()
        return stations

    async def get_station_by_id(self, station_id: str) -> models.Station | None:
        """Get a station by its ID."""
        stmt = select(models.Station).where(models.Station.station_id == station_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_stations(
        self, query: str, limit: int = 10
    ) -> list[models.Station]:
        """Search stations by name or place using database queries."""
        search_pattern = f"%{query.lower()}%"

        stmt = (
            select(models.Station)
            .where(
                (
                    models.Station.name.ilike(search_pattern)
                    | models.Station.place.ilike(search_pattern)
                )
            )
            .order_by(
                # Prioritize exact name matches
                models.Station.name.ilike(query.lower()).desc(),
                # Then prioritize name matches over place matches
                models.Station.name.ilike(search_pattern).desc(),
                models.Station.name,
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_stations(self) -> list[models.Station]:
        """Get all stations from the database."""
        stmt = select(models.Station).order_by(models.Station.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_stations(self) -> int:
        """Get the total number of stations in the database."""
        stmt = select(func.count(models.Station.station_id))
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def delete_station(self, station_id: str) -> bool:
        """Delete a station by ID. Returns True if station was deleted."""
        stmt = select(models.Station).where(models.Station.station_id == station_id)
        result = await self._session.execute(stmt)
        station = result.scalar_one_or_none()

        if station:
            await self._session.delete(station)
            await self._session.flush()
            return True
        return False
