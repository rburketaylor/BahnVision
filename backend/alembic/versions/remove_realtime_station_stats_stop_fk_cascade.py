"""Remove realtime station stats stop FK cascade.

Revision ID: remove_rt_stats_stop_fk_cascade
Revises: add_gtfs_parent_station_fk
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "remove_rt_stats_stop_fk_cascade"
down_revision: Union[str, None] = "add_gtfs_parent_station_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REALTIME_STOP_FK = "fk_realtime_station_stats_stop_id_gtfs_stops"


def upgrade() -> None:
    # Preserve realtime history across static GTFS refreshes. A non-cascading FK
    # would still block truncating and replacing gtfs_stops while historical rows
    # reference old stop IDs, so the FK is removed for now.
    op.execute(
        "ALTER TABLE realtime_station_stats "
        "DROP CONSTRAINT IF EXISTS fk_realtime_station_stats_stop_id_gtfs_stops"
    )


def downgrade() -> None:
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
    op.execute("ALTER TABLE realtime_station_stats SET UNLOGGED")
    op.create_foreign_key(
        _REALTIME_STOP_FK,
        "realtime_station_stats",
        "gtfs_stops",
        ["stop_id"],
        ["stop_id"],
        ondelete="CASCADE",
    )
