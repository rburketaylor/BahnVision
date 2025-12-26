"""Redesign GTFS-RT storage to streaming aggregation

Drops the raw observation tables and creates a new streaming stats table.
This is a breaking change that removes all existing GTFS-RT data.

Revision ID: redesign_gtfs_rt_storage
Revises: add_gtfs_rt_observations
Create Date: 2025-12-14 11:40:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "redesign_gtfs_rt_storage"
down_revision: Union[str, None] = "add_gtfs_rt_observations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old tables (in order due to no FK dependencies)
    op.execute("DROP TABLE IF EXISTS station_aggregations CASCADE")
    op.execute("DROP TABLE IF EXISTS trip_update_observations CASCADE")

    # Create new streaming stats table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS realtime_station_stats (
            id BIGSERIAL PRIMARY KEY,
            stop_id VARCHAR(64) NOT NULL,
            bucket_start TIMESTAMP WITH TIME ZONE NOT NULL,
            bucket_width_minutes INTEGER NOT NULL DEFAULT 60,
            observation_count INTEGER NOT NULL DEFAULT 0,
            trip_count INTEGER NOT NULL DEFAULT 0,
            total_delay_seconds BIGINT NOT NULL DEFAULT 0,
            delayed_count INTEGER NOT NULL DEFAULT 0,
            on_time_count INTEGER NOT NULL DEFAULT 0,
            cancelled_count INTEGER NOT NULL DEFAULT 0,
            route_type INTEGER,
            first_observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_realtime_stats_unique UNIQUE (stop_id, bucket_start, bucket_width_minutes, route_type)
        )
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_realtime_stats_stop_bucket ON realtime_station_stats (stop_id, bucket_start)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_realtime_stats_bucket ON realtime_station_stats (bucket_start)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS realtime_station_stats CASCADE")
    # Note: Does not restore old tables - use backup if needed
