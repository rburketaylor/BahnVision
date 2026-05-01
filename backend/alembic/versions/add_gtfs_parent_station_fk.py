"""Add self-referential FK for gtfs_stops.parent_station

Revision ID: add_gtfs_parent_station_fk
Revises: add_trip_route_idx_rt_stop_fk
Create Date: 2026-02-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_gtfs_parent_station_fk"
down_revision: Union[str, None] = "add_trip_route_idx_rt_stop_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PARENT_STATION_FK = "fk_gtfs_stops_parent_station_gtfs_stops"


def upgrade() -> None:
    op.execute(
        """
        UPDATE gtfs_stops child
        SET parent_station = NULL
        WHERE child.parent_station IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM gtfs_stops parent
              WHERE parent.stop_id = child.parent_station
          )
        """
    )
    op.create_foreign_key(
        _PARENT_STATION_FK,
        "gtfs_stops",
        "gtfs_stops",
        ["parent_station"],
        ["stop_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        _PARENT_STATION_FK,
        "gtfs_stops",
        type_="foreignkey",
    )
