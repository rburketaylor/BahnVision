"""Compact static GTFS schema metadata.

Revision ID: compact_static_gtfs_schema
Revises: convert_gtfs_stop_times_seconds
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "compact_static_gtfs_schema"
down_revision: Union[str, None] = "convert_gtfs_stop_times_seconds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("gtfs_stop_times", "feed_id")

    op.drop_column("gtfs_stops", "feed_id")
    op.drop_column("gtfs_routes", "feed_id")
    op.drop_column("gtfs_trips", "feed_id")
    op.drop_column("gtfs_calendar", "feed_id")
    op.drop_column("gtfs_calendar_dates", "feed_id")

    op.drop_column("gtfs_stops", "created_at")
    op.drop_column("gtfs_stops", "updated_at")
    op.drop_column("gtfs_routes", "created_at")
    op.drop_column("gtfs_trips", "created_at")

    op.alter_column(
        "gtfs_stops",
        "stop_lat",
        existing_type=sa.Numeric(9, 6),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="stop_lat::double precision",
    )
    op.alter_column(
        "gtfs_stops",
        "stop_lon",
        existing_type=sa.Numeric(9, 6),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="stop_lon::double precision",
    )

    op.drop_constraint("gtfs_stop_times_pkey", "gtfs_stop_times", type_="primary")
    op.drop_column("gtfs_stop_times", "id")
    op.create_primary_key(
        "gtfs_stop_times_pkey",
        "gtfs_stop_times",
        ["trip_id", "stop_sequence"],
    )


def downgrade() -> None:
    op.drop_constraint("gtfs_stop_times_pkey", "gtfs_stop_times", type_="primary")
    op.add_column(
        "gtfs_stop_times",
        sa.Column("id", sa.Integer(), nullable=True),
    )
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS gtfs_stop_times_id_seq "
        "OWNED BY gtfs_stop_times.id"
    )
    op.execute(
        """
        WITH numbered AS (
            SELECT trip_id, stop_sequence,
                   row_number() OVER (ORDER BY trip_id, stop_sequence) AS new_id
            FROM gtfs_stop_times
        )
        UPDATE gtfs_stop_times stop_times
        SET id = numbered.new_id
        FROM numbered
        WHERE stop_times.trip_id = numbered.trip_id
          AND stop_times.stop_sequence = numbered.stop_sequence
        """
    )
    op.execute(
        """
        SELECT setval(
            'gtfs_stop_times_id_seq',
            COALESCE((SELECT max(id) FROM gtfs_stop_times), 1),
            (SELECT count(*) > 0 FROM gtfs_stop_times)
        )
        """
    )
    op.execute(
        "ALTER TABLE gtfs_stop_times ALTER COLUMN id "
        "SET DEFAULT nextval('gtfs_stop_times_id_seq')"
    )
    op.alter_column(
        "gtfs_stop_times",
        "id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_primary_key("gtfs_stop_times_pkey", "gtfs_stop_times", ["id"])

    op.alter_column(
        "gtfs_stops",
        "stop_lon",
        existing_type=sa.Float(),
        type_=sa.Numeric(9, 6),
        existing_nullable=True,
    )
    op.alter_column(
        "gtfs_stops",
        "stop_lat",
        existing_type=sa.Float(),
        type_=sa.Numeric(9, 6),
        existing_nullable=True,
    )

    op.add_column(
        "gtfs_trips",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gtfs_routes",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gtfs_stops",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "gtfs_stops",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    for table_name in (
        "gtfs_calendar_dates",
        "gtfs_calendar",
        "gtfs_trips",
        "gtfs_routes",
        "gtfs_stops",
        "gtfs_stop_times",
    ):
        op.add_column(table_name, sa.Column("feed_id", sa.String(length=32)))
