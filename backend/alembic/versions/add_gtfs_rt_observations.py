"""Add GTFS-RT observation tables

Revision ID: add_gtfs_rt_observations
Revises: 80a6a8257627
Create Date: 2025-12-13 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_gtfs_rt_observations"
down_revision: Union[str, None] = "80a6a8257627"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create schedule_relationship enum if it doesn't exist
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE schedule_relationship AS ENUM (
                'SCHEDULED', 'SKIPPED', 'NO_DATA', 'UNSCHEDULED', 'CANCELED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """
    )

    # Create trip_update_observations table for raw GTFS-RT data
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trip_update_observations (
            id BIGSERIAL PRIMARY KEY,
            trip_id VARCHAR(128) NOT NULL,
            route_id VARCHAR(64) NOT NULL,
            stop_id VARCHAR(64) NOT NULL,
            stop_sequence INTEGER NOT NULL,
            arrival_delay_seconds INTEGER,
            departure_delay_seconds INTEGER,
            schedule_relationship schedule_relationship NOT NULL DEFAULT 'SCHEDULED',
            feed_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            observed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            route_type INTEGER,
            CONSTRAINT uq_trip_update_unique UNIQUE (trip_id, stop_id, feed_timestamp)
        )
    """
    )

    # Create indexes (using IF NOT EXISTS via raw SQL)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trip_obs_stop_observed ON trip_update_observations (stop_id, observed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trip_obs_route_observed ON trip_update_observations (route_id, observed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trip_obs_feed_ts ON trip_update_observations (feed_timestamp)"
    )

    # Create station_aggregations table for pre-computed heatmap data
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS station_aggregations (
            id BIGSERIAL PRIMARY KEY,
            stop_id VARCHAR(64) NOT NULL,
            bucket_start TIMESTAMP WITH TIME ZONE NOT NULL,
            bucket_width_minutes INTEGER NOT NULL DEFAULT 60,
            total_departures INTEGER NOT NULL DEFAULT 0,
            cancelled_count INTEGER NOT NULL DEFAULT 0,
            delayed_count INTEGER NOT NULL DEFAULT 0,
            avg_delay_seconds FLOAT NOT NULL DEFAULT 0.0,
            route_type INTEGER,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_station_agg_unique UNIQUE (stop_id, bucket_start, bucket_width_minutes, route_type)
        )
    """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_station_agg_stop_bucket ON station_aggregations (stop_id, bucket_start)"
    )


def downgrade() -> None:
    # Drop station_aggregations table
    op.execute("DROP INDEX IF EXISTS ix_station_agg_stop_bucket")
    op.execute("DROP TABLE IF EXISTS station_aggregations")

    # Drop trip_update_observations table
    op.execute("DROP INDEX IF EXISTS ix_trip_obs_feed_ts")
    op.execute("DROP INDEX IF EXISTS ix_trip_obs_route_observed")
    op.execute("DROP INDEX IF EXISTS ix_trip_obs_stop_observed")
    op.execute("DROP TABLE IF EXISTS trip_update_observations")

    # Drop schedule_relationship enum
    op.execute("DROP TYPE IF EXISTS schedule_relationship")
