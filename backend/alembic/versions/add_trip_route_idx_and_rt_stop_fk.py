"""Add gtfs_trips route index and realtime stop FK integrity.

Revision ID: add_trip_route_idx_rt_stop_fk
Revises: fix_heatmap_duplication
Create Date: 2026-02-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_trip_route_idx_rt_stop_fk"
down_revision: Union[str, None] = "fix_heatmap_duplication"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRIP_ROUTE_INDEX = "ix_gtfs_trips_route_id"
_REALTIME_STOP_FK = "fk_realtime_station_stats_stop_id_gtfs_stops"


def upgrade() -> None:
    op.create_index(_TRIP_ROUTE_INDEX, "gtfs_trips", ["route_id"], unique=False)

    # Strategy for enforcing FK integrity on existing data:
    # remove orphan rows first, then add a validated FK constraint.
    op.execute(
        """
        DELETE FROM realtime_station_stats rss
        WHERE NOT EXISTS (
            SELECT 1
            FROM gtfs_stops gs
            WHERE gs.stop_id = rss.stop_id
        )
        """
    )

    # gtfs_stops is UNLOGGED in earlier migrations. PostgreSQL does not allow a
    # permanent (logged) table to reference an UNLOGGED table via FK, so align
    # realtime_station_stats before creating the constraint.
    op.execute("ALTER TABLE realtime_station_stats SET UNLOGGED")

    op.create_foreign_key(
        _REALTIME_STOP_FK,
        "realtime_station_stats",
        "gtfs_stops",
        ["stop_id"],
        ["stop_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        _REALTIME_STOP_FK,
        "realtime_station_stats",
        type_="foreignkey",
    )
    op.execute("ALTER TABLE realtime_station_stats SET LOGGED")
    op.drop_index(_TRIP_ROUTE_INDEX, table_name="gtfs_trips")
