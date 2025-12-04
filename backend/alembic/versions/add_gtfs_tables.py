"""Add GTFS tables

Revision ID: add_gtfs_tables
Revises: 0d6132be0bb0
Create Date: 2025-12-04 20:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "add_gtfs_tables"
down_revision: Union[str, None] = "0d6132be0bb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create gtfs_stops table
    op.create_table(
        "gtfs_stops",
        sa.Column("stop_id", sa.String(length=64), nullable=False),
        sa.Column("stop_name", sa.String(length=255), nullable=False),
        sa.Column("stop_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("stop_lon", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("location_type", sa.SmallInteger(), nullable=True),
        sa.Column("parent_station", sa.String(length=64), nullable=True),
        sa.Column("platform_code", sa.String(length=16), nullable=True),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("stop_id"),
    )
    op.create_index(
        op.f("ix_gtfs_stops_stop_name"), "gtfs_stops", ["stop_name"], unique=False
    )

    # Create gtfs_routes table
    op.create_table(
        "gtfs_routes",
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("agency_id", sa.String(length=64), nullable=True),
        sa.Column("route_short_name", sa.String(length=64), nullable=True),
        sa.Column("route_long_name", sa.String(length=255), nullable=True),
        sa.Column("route_type", sa.SmallInteger(), nullable=False),
        sa.Column("route_color", sa.String(length=6), nullable=True),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("route_id"),
    )

    # Create gtfs_trips table
    op.create_table(
        "gtfs_trips",
        sa.Column("trip_id", sa.String(length=64), nullable=False),
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("trip_headsign", sa.String(length=255), nullable=True),
        sa.Column("direction_id", sa.SmallInteger(), nullable=True),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["gtfs_routes.route_id"],
        ),
        sa.PrimaryKeyConstraint("trip_id"),
    )
    op.create_index(
        op.f("ix_gtfs_trips_service_id"), "gtfs_trips", ["service_id"], unique=False
    )

    # Create gtfs_stop_times table
    op.create_table(
        "gtfs_stop_times",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.String(length=64), nullable=False),
        sa.Column("stop_id", sa.String(length=64), nullable=False),
        sa.Column("arrival_time", sa.Interval(), nullable=True),
        sa.Column("departure_time", sa.Interval(), nullable=True),
        sa.Column("stop_sequence", sa.SmallInteger(), nullable=False),
        sa.Column("pickup_type", sa.SmallInteger(), nullable=True),
        sa.Column("drop_off_type", sa.SmallInteger(), nullable=True),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["stop_id"],
            ["gtfs_stops.stop_id"],
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["gtfs_trips.trip_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_gtfs_stop_times_stop", "gtfs_stop_times", ["stop_id"], unique=False
    )
    op.create_index(
        "idx_gtfs_stop_times_trip", "gtfs_stop_times", ["trip_id"], unique=False
    )

    # Create gtfs_calendar table
    op.create_table(
        "gtfs_calendar",
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("monday", sa.Boolean(), nullable=False),
        sa.Column("tuesday", sa.Boolean(), nullable=False),
        sa.Column("wednesday", sa.Boolean(), nullable=False),
        sa.Column("thursday", sa.Boolean(), nullable=False),
        sa.Column("friday", sa.Boolean(), nullable=False),
        sa.Column("saturday", sa.Boolean(), nullable=False),
        sa.Column("sunday", sa.Boolean(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("service_id"),
    )
    op.create_index(
        "idx_gtfs_calendar_active",
        "gtfs_calendar",
        ["start_date", "end_date"],
        unique=False,
    )

    # Create gtfs_calendar_dates table
    op.create_table(
        "gtfs_calendar_dates",
        sa.Column("service_id", sa.String(length=64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.SmallInteger(), nullable=False),
        sa.Column("feed_id", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("service_id", "date"),
    )
    op.create_index(
        "idx_gtfs_calendar_dates_lookup",
        "gtfs_calendar_dates",
        ["date", "service_id"],
        unique=False,
    )

    # Create gtfs_feed_info table
    op.create_table(
        "gtfs_feed_info",
        sa.Column("feed_id", sa.String(length=32), nullable=False),
        sa.Column("feed_url", sa.String(length=512), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
        sa.Column("feed_start_date", sa.Date(), nullable=True),
        sa.Column("feed_end_date", sa.Date(), nullable=True),
        sa.Column("stop_count", sa.Integer(), nullable=True),
        sa.Column("route_count", sa.Integer(), nullable=True),
        sa.Column("trip_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("feed_id"),
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
