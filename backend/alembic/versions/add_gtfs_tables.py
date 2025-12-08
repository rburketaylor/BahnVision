"""Add GTFS tables

Revision ID: add_gtfs_tables
Revises: 0d6132be0bb0
Create Date: 2025-12-04 20:15:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_gtfs_tables"
down_revision: Union[str, None] = "0d6132be0bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gtfs_stops table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_stops (
            stop_id VARCHAR(64) PRIMARY KEY,
            stop_name VARCHAR(255) NOT NULL,
            stop_lat NUMERIC(9, 6),
            stop_lon NUMERIC(9, 6),
            location_type SMALLINT,
            parent_station VARCHAR(64),
            platform_code VARCHAR(16),
            feed_id VARCHAR(32),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """
    )
    op.create_index(
        op.f("ix_gtfs_stops_stop_name"), "gtfs_stops", ["stop_name"], unique=False
    )

    # Create gtfs_routes table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_routes (
            route_id VARCHAR(64) PRIMARY KEY,
            agency_id VARCHAR(64),
            route_short_name VARCHAR(64),
            route_long_name VARCHAR(255),
            route_type SMALLINT NOT NULL,
            route_color VARCHAR(6),
            feed_id VARCHAR(32),
            created_at TIMESTAMP
        )
    """
    )

    # Create gtfs_trips table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_trips (
            trip_id VARCHAR(64) PRIMARY KEY,
            route_id VARCHAR(64) NOT NULL REFERENCES gtfs_routes(route_id),
            service_id VARCHAR(64) NOT NULL,
            trip_headsign VARCHAR(255),
            direction_id SMALLINT,
            feed_id VARCHAR(32),
            created_at TIMESTAMP
        )
    """
    )
    op.create_index(
        op.f("ix_gtfs_trips_service_id"), "gtfs_trips", ["service_id"], unique=False
    )

    # Create gtfs_stop_times table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_stop_times (
            id SERIAL PRIMARY KEY,
            trip_id VARCHAR(64) NOT NULL,
            stop_id VARCHAR(64) NOT NULL,
            arrival_time INTERVAL,
            departure_time INTERVAL,
            stop_sequence SMALLINT NOT NULL,
            pickup_type SMALLINT,
            drop_off_type SMALLINT,
            feed_id VARCHAR(32),
            FOREIGN KEY (stop_id) REFERENCES gtfs_stops(stop_id),
            FOREIGN KEY (trip_id) REFERENCES gtfs_trips(trip_id)
        )
    """
    )
    op.create_index(
        "idx_gtfs_stop_times_stop", "gtfs_stop_times", ["stop_id"], unique=False
    )
    op.create_index(
        "idx_gtfs_stop_times_trip", "gtfs_stop_times", ["trip_id"], unique=False
    )

    # Create gtfs_calendar table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_calendar (
            service_id VARCHAR(64) PRIMARY KEY,
            monday BOOLEAN NOT NULL,
            tuesday BOOLEAN NOT NULL,
            wednesday BOOLEAN NOT NULL,
            thursday BOOLEAN NOT NULL,
            friday BOOLEAN NOT NULL,
            saturday BOOLEAN NOT NULL,
            sunday BOOLEAN NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            feed_id VARCHAR(32)
        )
    """
    )
    op.create_index(
        "idx_gtfs_calendar_active",
        "gtfs_calendar",
        ["start_date", "end_date"],
        unique=False,
    )

    # Create gtfs_calendar_dates table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_calendar_dates (
            service_id VARCHAR(64) NOT NULL,
            date DATE NOT NULL,
            exception_type SMALLINT NOT NULL,
            feed_id VARCHAR(32),
            PRIMARY KEY (service_id, date)
        )
    """
    )
    op.create_index(
        "idx_gtfs_calendar_dates_lookup",
        "gtfs_calendar_dates",
        ["date", "service_id"],
        unique=False,
    )

    # Create gtfs_feed_info table (UNLOGGED for faster bulk imports - data is rebuildable)
    op.execute(
        """
        CREATE UNLOGGED TABLE gtfs_feed_info (
            feed_id VARCHAR(32) PRIMARY KEY,
            feed_url VARCHAR(512),
            downloaded_at TIMESTAMP NOT NULL,
            feed_start_date DATE,
            feed_end_date DATE,
            stop_count INTEGER,
            route_count INTEGER,
            trip_count INTEGER
        )
    """
    )

    # Performance indexes
    op.create_index(
        "idx_gtfs_stop_times_departure_lookup",
        "gtfs_stop_times",
        ["stop_id", "departure_time"],
        unique=False,
    )
    op.create_index(
        "idx_gtfs_stops_location", "gtfs_stops", ["stop_lat", "stop_lon"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_gtfs_stops_location", table_name="gtfs_stops")
    op.drop_index("idx_gtfs_stop_times_departure_lookup", table_name="gtfs_stop_times")
    op.drop_table("gtfs_feed_info")
    op.drop_index("idx_gtfs_calendar_dates_lookup", table_name="gtfs_calendar_dates")
    op.drop_table("gtfs_calendar_dates")
    op.drop_index("idx_gtfs_calendar_active", table_name="gtfs_calendar")
    op.drop_table("gtfs_calendar")
    op.drop_index("idx_gtfs_stop_times_trip", table_name="gtfs_stop_times")
    op.drop_index("idx_gtfs_stop_times_stop", table_name="gtfs_stop_times")
    op.drop_table("gtfs_stop_times")
    op.drop_index(op.f("ix_gtfs_trips_service_id"), table_name="gtfs_trips")
    op.drop_table("gtfs_trips")
    op.drop_table("gtfs_routes")
    op.drop_index(op.f("ix_gtfs_stops_stop_name"), table_name="gtfs_stops")
    op.drop_table("gtfs_stops")
