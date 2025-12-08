from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Interval,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
)
from sqlalchemy.orm import relationship

from app.persistence.models import Base


class GTFSStop(Base):
    __tablename__ = "gtfs_stops"

    stop_id = Column(String(64), primary_key=True)
    stop_name = Column(String(255), nullable=False, index=True)
    stop_lat = Column(Numeric(9, 6))
    stop_lon = Column(Numeric(9, 6))
    location_type = Column(SmallInteger, default=0)
    parent_station = Column(String(64))
    platform_code = Column(String(16))
    feed_id = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GTFSRoute(Base):
    __tablename__ = "gtfs_routes"

    route_id = Column(String(64), primary_key=True)
    agency_id = Column(String(64))
    route_short_name = Column(String(64))
    route_long_name = Column(String(255))
    route_type = Column(SmallInteger, nullable=False)
    route_color = Column(String(6))
    feed_id = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)

    trips = relationship("GTFSTrip", back_populates="route")


class GTFSTrip(Base):
    __tablename__ = "gtfs_trips"

    trip_id = Column(String(64), primary_key=True)
    route_id = Column(String(64), ForeignKey("gtfs_routes.route_id"), nullable=False)
    service_id = Column(String(64), nullable=False, index=True)
    trip_headsign = Column(String(255))
    direction_id = Column(SmallInteger)
    feed_id = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)

    route = relationship("GTFSRoute", back_populates="trips")
    stop_times = relationship("GTFSStopTime", back_populates="trip")


class GTFSStopTime(Base):
    __tablename__ = "gtfs_stop_times"

    id = Column(Integer, primary_key=True)
    trip_id = Column(String(64), ForeignKey("gtfs_trips.trip_id"), nullable=False)
    stop_id = Column(String(64), ForeignKey("gtfs_stops.stop_id"), nullable=False)
    arrival_time = Column(Interval)
    departure_time = Column(Interval)
    stop_sequence = Column(SmallInteger, nullable=False)
    pickup_type = Column(SmallInteger, default=0)
    drop_off_type = Column(SmallInteger, default=0)
    feed_id = Column(String(32))

    trip = relationship("GTFSTrip", back_populates="stop_times")
    stop = relationship("GTFSStop")


class GTFSCalendar(Base):
    __tablename__ = "gtfs_calendar"

    service_id = Column(String(64), primary_key=True)
    monday = Column(Boolean, nullable=False)
    tuesday = Column(Boolean, nullable=False)
    wednesday = Column(Boolean, nullable=False)
    thursday = Column(Boolean, nullable=False)
    friday = Column(Boolean, nullable=False)
    saturday = Column(Boolean, nullable=False)
    sunday = Column(Boolean, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    feed_id = Column(String(32))


class GTFSCalendarDate(Base):
    __tablename__ = "gtfs_calendar_dates"

    service_id = Column(String(64), nullable=False)
    date = Column(Date, nullable=False)
    exception_type = Column(SmallInteger, nullable=False)  # 1=added, 2=removed
    feed_id = Column(String(32))

    __table_args__ = (PrimaryKeyConstraint("service_id", "date"),)


class GTFSFeedInfo(Base):
    __tablename__ = "gtfs_feed_info"

    feed_id = Column(String(32), primary_key=True)
    feed_url = Column(String(512))
    downloaded_at = Column(DateTime, nullable=False)
    feed_start_date = Column(Date)
    feed_end_date = Column(Date)
    stop_count = Column(Integer)
    route_count = Column(Integer)
    trip_count = Column(Integer)
