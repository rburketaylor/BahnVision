from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TransportMode(str, enum.Enum):
    UBAHN = "UBAHN"
    SBAHN = "SBAHN"
    TRAM = "TRAM"
    BUS = "BUS"
    REGIONAL = "REGIONAL"


class DepartureStatus(str, enum.Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class WeatherCondition(str, enum.Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    STORM = "storm"
    FOG = "fog"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ExternalStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    DOWNSTREAM_ERROR = "DOWNSTREAM_ERROR"
    TIMEOUT = "TIMEOUT"


class IngestionSource(str, enum.Enum):
    MVG_DEPARTURES = "MVG_DEPARTURES"
    MVG_STATIONS = "MVG_STATIONS"
    WEATHER = "WEATHER"


class IngestionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


transport_mode_enum = SqlEnum(
    TransportMode,
    name="transport_mode",
)
departure_status_enum = SqlEnum(
    DepartureStatus,
    name="departure_status",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)
weather_condition_enum = SqlEnum(
    WeatherCondition,
    name="weather_condition",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)
external_status_enum = SqlEnum(
    ExternalStatus,
    name="external_status",
)
ingestion_source_enum = SqlEnum(
    IngestionSource,
    name="ingestion_source",
)
ingestion_status_enum = SqlEnum(
    IngestionStatus,
    name="ingestion_status",
)


class Station(Base):
    __tablename__ = "stations"

    station_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    place: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    transport_modes: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        default=list,
        server_default="{}",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Berlin",
        server_default="Europe/Berlin",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    departures: Mapped[list["DepartureObservation"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )
    weather_observations: Mapped[list["WeatherObservation"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )


class TransitLine(Base):
    __tablename__ = "transit_lines"

    line_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    transport_mode: Mapped[TransportMode] = mapped_column(transport_mode_enum.copy(), nullable=False)
    operator: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="MVG",
        server_default="MVG",
    )
    description: Mapped[str | None] = mapped_column(String(255))
    color_hex: Mapped[str | None] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    departures: Mapped[list["DepartureObservation"]] = relationship(
        back_populates="transit_line",
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[IngestionSource] = mapped_column(
        ingestion_source_enum.copy(),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[IngestionStatus] = mapped_column(
        ingestion_status_enum.copy(),
        nullable=False,
        default=IngestionStatus.RUNNING,
        server_default=IngestionStatus.RUNNING.value,
    )
    records_inserted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    notes: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    departures: Mapped[list["DepartureObservation"]] = relationship(
        back_populates="ingestion_run",
    )
    weather_observations: Mapped[list["WeatherObservation"]] = relationship(
        back_populates="ingestion_run",
    )

    __table_args__ = (
        Index("ix_ingestion_runs_job_started", "job_name", "started_at"),
    )


class DepartureObservation(Base):
    __tablename__ = "departure_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(
        ForeignKey("stations.station_id", ondelete="cascade"),
        nullable=False,
    )
    line_id: Mapped[str] = mapped_column(
        ForeignKey("transit_lines.line_id", ondelete="restrict"),
        nullable=False,
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="set null"),
    )
    direction: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    planned_departure: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    observed_departure: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    delay_seconds: Mapped[int | None] = mapped_column(Integer)
    platform: Mapped[str | None] = mapped_column(String(16))
    transport_mode: Mapped[TransportMode] = mapped_column(transport_mode_enum.copy(), nullable=False)
    status: Mapped[DepartureStatus] = mapped_column(departure_status_enum.copy(), nullable=False, default=DepartureStatus.UNKNOWN, server_default=DepartureStatus.UNKNOWN.value)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        server_default="{}",
        nullable=False,
    )
    crowding_level: Mapped[int | None] = mapped_column(
        Integer,
        doc="Crowding score reported by MVG if available (0-100).",
    )
    source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="mvg",
        server_default="mvg",
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    station: Mapped[Station] = relationship(back_populates="departures")
    transit_line: Mapped[TransitLine] = relationship(back_populates="departures")
    ingestion_run: Mapped[IngestionRun | None] = relationship(
        back_populates="departures"
    )
    weather_links: Mapped[list["DepartureWeatherLink"]] = relationship(
        back_populates="departure",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_departures_station_planned",
            "station_id",
            "planned_departure",
        ),
        Index(
            "ix_departures_line_planned",
            "line_id",
            "planned_departure",
        ),
    )


class RouteSnapshot(Base):
    __tablename__ = "route_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    origin_station_id: Mapped[str] = mapped_column(
        ForeignKey("stations.station_id", ondelete="cascade"),
        nullable=False,
    )
    destination_station_id: Mapped[str] = mapped_column(
        ForeignKey("stations.station_id", ondelete="cascade"),
        nullable=False,
    )
    requested_filters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    itineraries: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    mvg_status: Mapped[ExternalStatus] = mapped_column(
        external_status_enum.copy(),
        nullable=False,
        default=ExternalStatus.SUCCESS,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_route_snapshots_requested_at",
            "requested_at",
            postgresql_where=text("requested_at IS NOT NULL"),
        ),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_id: Mapped[str | None] = mapped_column(
        ForeignKey("stations.station_id", ondelete="set null"),
    )
    ingestion_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="set null"),
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    feels_like_c: Mapped[float | None] = mapped_column(Numeric(5, 2))
    humidity_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    wind_speed_mps: Mapped[float | None] = mapped_column(Numeric(5, 2))
    wind_gust_mps: Mapped[float | None] = mapped_column(Numeric(5, 2))
    wind_direction_deg: Mapped[int | None] = mapped_column(Integer)
    pressure_hpa: Mapped[float | None] = mapped_column(Numeric(6, 2))
    visibility_km: Mapped[float | None] = mapped_column(Numeric(5, 2))
    precipitation_mm: Mapped[float | None] = mapped_column(Numeric(5, 2))
    precipitation_type: Mapped[str | None] = mapped_column(String(32))
    condition: Mapped[WeatherCondition] = mapped_column(
        weather_condition_enum.copy(),
        nullable=False,
        default=WeatherCondition.UNKNOWN,
        server_default=WeatherCondition.UNKNOWN.value,
    )
    alerts: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        server_default="{}",
        nullable=False,
    )
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    station: Mapped[Station | None] = relationship(back_populates="weather_observations")
    ingestion_run: Mapped[IngestionRun | None] = relationship(
        back_populates="weather_observations"
    )
    departures: Mapped[list["DepartureWeatherLink"]] = relationship(
        back_populates="weather",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_weather_location_time",
            "latitude",
            "longitude",
            "observed_at",
        ),
    )


class DepartureWeatherLink(Base):
    __tablename__ = "departure_weather_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    departure_id: Mapped[int] = mapped_column(
        ForeignKey("departure_observations.id", ondelete="cascade"),
        nullable=False,
    )
    weather_id: Mapped[int] = mapped_column(
        ForeignKey("weather_observations.id", ondelete="cascade"),
        nullable=False,
    )
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="closest",
        server_default="closest",
    )

    departure: Mapped[DepartureObservation] = relationship(back_populates="weather_links")
    weather: Mapped[WeatherObservation] = relationship(back_populates="departures")

    __table_args__ = (
        UniqueConstraint(
            "departure_id",
            "weather_id",
            name="uq_departure_weather_unique",
        ),
    )
