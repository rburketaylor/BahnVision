"""Fix heatmap duplication: deduplicate stats and add NULLS NOT DISTINCT constraint

This migration addresses the ~12x data inflation caused by PostgreSQL's handling
of NULL values in unique constraints. Since PostgreSQL treats NULL != NULL,
multiple rows with route_type=NULL were being created instead of updated.

This migration:
1. Aggregates duplicate rows into a temporary table
2. Clears the original table
3. Restores aggregated data
4. Updates the unique constraint to use NULLS NOT DISTINCT (PostgreSQL 15+)

Revision ID: fix_heatmap_duplication
Revises: add_daily_station_stats
Create Date: 2025-01-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fix_heatmap_duplication"
down_revision: Union[str, None] = "add_daily_station_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNKNOWN_ROUTE_TYPE = -1


def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    if dialect_name != "postgresql":
        raise NotImplementedError(
            "This migration only supports PostgreSQL due to NULLS NOT DISTINCT requirement"
        )
    server_version = getattr(conn.dialect, "server_version_info", None)
    if not server_version or tuple(server_version) < (15, 0):
        raise NotImplementedError(
            "PostgreSQL 15+ is required for this migration "
            "(UNIQUE NULLS NOT DISTINCT constraint)."
        )

    op.execute(
        """
        CREATE TABLE realtime_station_stats_dedup AS
        SELECT
            MIN(id) as id,
            stop_id,
            bucket_start,
            bucket_width_minutes,
            route_type,
            SUM(observation_count) as observation_count,
            SUM(trip_count) as trip_count,
            SUM(total_delay_seconds) as total_delay_seconds,
            SUM(delayed_count) as delayed_count,
            SUM(on_time_count) as on_time_count,
            SUM(cancelled_count) as cancelled_count,
            MIN(first_observed_at) as first_observed_at,
            MAX(last_updated_at) as last_updated_at
        FROM realtime_station_stats
        GROUP BY stop_id, bucket_start, bucket_width_minutes, route_type
        """
    )

    op.execute("TRUNCATE TABLE realtime_station_stats")

    op.execute(
        """
        INSERT INTO realtime_station_stats (
            id, stop_id, bucket_start, bucket_width_minutes, route_type,
            observation_count, trip_count, total_delay_seconds,
            delayed_count, on_time_count, cancelled_count,
            first_observed_at, last_updated_at
        )
        SELECT
            id, stop_id, bucket_start, bucket_width_minutes, route_type,
            observation_count, trip_count, total_delay_seconds,
            delayed_count, on_time_count, cancelled_count,
            first_observed_at, last_updated_at
        FROM realtime_station_stats_dedup
        """
    )

    op.execute("DROP TABLE realtime_station_stats_dedup")

    op.execute(
        """
        ALTER TABLE realtime_station_stats
        DROP CONSTRAINT IF EXISTS uq_realtime_stats_unique
        """
    )

    op.execute(
        """
        ALTER TABLE realtime_station_stats
        ADD CONSTRAINT uq_realtime_stats_unique
        UNIQUE NULLS NOT DISTINCT (stop_id, bucket_start, bucket_width_minutes, route_type)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE realtime_station_stats
        DROP CONSTRAINT IF EXISTS uq_realtime_stats_unique
        """
    )

    op.execute(
        """
        ALTER TABLE realtime_station_stats
        ADD CONSTRAINT uq_realtime_stats_unique
        UNIQUE (stop_id, bucket_start, bucket_width_minutes, route_type)
        """
    )
