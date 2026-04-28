"""Add heatmap indexes.

Revision ID: add_heatmap_indexes
Revises: compact_static_gtfs_schema
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_heatmap_indexes"
down_revision: Union[str, None] = "compact_static_gtfs_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_realtime_stats_bucket_width_route",
        "realtime_station_stats",
        ["bucket_start", "bucket_width_minutes", "route_type"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_realtime_stats_bucket_width_route")
