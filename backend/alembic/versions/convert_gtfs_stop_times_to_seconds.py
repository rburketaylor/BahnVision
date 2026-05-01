"""Convert GTFS stop times from intervals to integer seconds.

Revision ID: convert_gtfs_stop_times_seconds
Revises: remove_rt_stats_stop_fk_cascade
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "convert_gtfs_stop_times_seconds"
down_revision: Union[str, None] = "remove_rt_stats_stop_fk_cascade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEPARTURE_LOOKUP_INDEX = "idx_gtfs_stop_times_departure_lookup"


def upgrade() -> None:
    op.add_column("gtfs_stop_times", sa.Column("arrival_seconds", sa.Integer()))
    op.add_column("gtfs_stop_times", sa.Column("departure_seconds", sa.Integer()))

    op.execute(
        """
        UPDATE gtfs_stop_times
        SET arrival_seconds = CASE
                WHEN arrival_time IS NULL THEN NULL
                ELSE floor(extract(epoch FROM arrival_time))::integer
            END,
            departure_seconds = CASE
                WHEN departure_time IS NULL THEN NULL
                ELSE floor(extract(epoch FROM departure_time))::integer
            END
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_gtfs_stop_times_departure_lookup")
    op.create_index(
        _DEPARTURE_LOOKUP_INDEX,
        "gtfs_stop_times",
        ["stop_id", "departure_seconds"],
    )

    op.drop_column("gtfs_stop_times", "arrival_time")
    op.drop_column("gtfs_stop_times", "departure_time")


def downgrade() -> None:
    op.add_column("gtfs_stop_times", sa.Column("arrival_time", sa.Interval()))
    op.add_column("gtfs_stop_times", sa.Column("departure_time", sa.Interval()))

    op.execute(
        """
        UPDATE gtfs_stop_times
        SET arrival_time = CASE
                WHEN arrival_seconds IS NULL THEN NULL
                ELSE arrival_seconds * INTERVAL '1 second'
            END,
            departure_time = CASE
                WHEN departure_seconds IS NULL THEN NULL
                ELSE departure_seconds * INTERVAL '1 second'
            END
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_gtfs_stop_times_departure_lookup")
    op.create_index(
        _DEPARTURE_LOOKUP_INDEX,
        "gtfs_stop_times",
        ["stop_id", "departure_time"],
    )

    op.drop_column("gtfs_stop_times", "arrival_seconds")
    op.drop_column("gtfs_stop_times", "departure_seconds")
