"""Add daily station stats aggregation

Creates the realtime_station_stats_daily table for pre-aggregated daily statistics.
This improves query performance for large time range heatmap requests (7d, 30d).

Revision ID: add_daily_station_stats
Revises: redesign_gtfs_rt_storage
Create Date: 2025-01-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_daily_station_stats"
down_revision: Union[str, None] = "redesign_gtfs_rt_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create daily stats table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS realtime_station_stats_daily (
            id BIGSERIAL PRIMARY KEY,
            stop_id VARCHAR(64) NOT NULL,
            date DATE NOT NULL,
            trip_count INTEGER NOT NULL DEFAULT 0,
            delayed_count INTEGER NOT NULL DEFAULT 0,
            cancelled_count INTEGER NOT NULL DEFAULT 0,
            on_time_count INTEGER NOT NULL DEFAULT 0,
            total_delay_seconds BIGINT NOT NULL DEFAULT 0,
            observation_count INTEGER NOT NULL DEFAULT 0,
            by_route_type JSONB NOT NULL DEFAULT '{}',
            first_observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_daily_stats_stop_date_unique UNIQUE (stop_id, date)
        )
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_daily_stats_stop_date ON realtime_station_stats_daily (stop_id, date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_daily_stats_date ON realtime_station_stats_daily (date)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS realtime_station_stats_daily CASCADE")
