from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models import Base


class GTFSStop(Base):
    __tablename__ = "gtfs_stops"

    stop_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    stop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    stop_lat: Mapped[float | None] = mapped_column(Float)
    stop_lon: Mapped[float | None] = mapped_column(Float)
    location_type: Mapped[int | None] = mapped_column(SmallInteger, default=0)
    parent_station: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("gtfs_stops.stop_id", ondelete="SET NULL"),
        index=True,
    )
    platform_code: Mapped[str | None] = mapped_column(String(16))

    __table_args__ = (
        Index(
            "idx_gtfs_stops_name_trgm",
            "stop_name",
            postgresql_using="gin",
            postgresql_ops={"stop_name": "gin_trgm_ops"},
        ),
    )


class GTFSRoute(Base):
    __tablename__ = "gtfs_routes"

    route_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agency_id: Mapped[str | None] = mapped_column(String(64))
    route_short_name: Mapped[str | None] = mapped_column(String(64))
    route_long_name: Mapped[str | None] = mapped_column(String(255))
    route_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    route_color: Mapped[str | None] = mapped_column(String(6))

    trips: Mapped[list[GTFSTrip]] = relationship(back_populates="route")


class GTFSTrip(Base):
    __tablename__ = "gtfs_trips"

    trip_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    route_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("gtfs_routes.route_id"),
        nullable=False,
    )
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trip_headsign: Mapped[str | None] = mapped_column(String(255))
    direction_id: Mapped[int | None] = mapped_column(SmallInteger)

    route: Mapped[GTFSRoute] = relationship(back_populates="trips")
    stop_times: Mapped[list[GTFSStopTime]] = relationship(back_populates="trip")


class GTFSStopTime(Base):
    __tablename__ = "gtfs_stop_times"

    trip_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("gtfs_trips.trip_id"),
        primary_key=True,
        nullable=False,
    )
    stop_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("gtfs_stops.stop_id"),
        nullable=False,
    )
    arrival_seconds: Mapped[int | None] = mapped_column(Integer)
    departure_seconds: Mapped[int | None] = mapped_column(Integer)
    stop_sequence: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, nullable=False
    )
    pickup_type: Mapped[int | None] = mapped_column(SmallInteger, default=0)
    drop_off_type: Mapped[int | None] = mapped_column(SmallInteger, default=0)

    trip: Mapped[GTFSTrip] = relationship(back_populates="stop_times")
    stop: Mapped[GTFSStop] = relationship()


class GTFSCalendar(Base):
    __tablename__ = "gtfs_calendar"

    service_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class GTFSCalendarDate(Base):
    __tablename__ = "gtfs_calendar_dates"

    service_id: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    exception_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (PrimaryKeyConstraint("service_id", "date"),)


class GTFSFeedInfo(Base):
    __tablename__ = "gtfs_feed_info"

    feed_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    feed_url: Mapped[str | None] = mapped_column(String(512))
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    feed_start_date: Mapped[date | None] = mapped_column(Date)
    feed_end_date: Mapped[date | None] = mapped_column(Date)
    stop_count: Mapped[int | None] = mapped_column(Integer)
    route_count: Mapped[int | None] = mapped_column(Integer)
    trip_count: Mapped[int | None] = mapped_column(Integer)
