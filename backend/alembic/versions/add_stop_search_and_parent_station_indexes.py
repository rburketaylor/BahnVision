"""Add stop search and parent station indexes.

Revision ID: add_stop_parent_search_idx
Revises: add_heatmap_indexes
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_stop_parent_search_idx"
down_revision: Union[str, None] = "add_heatmap_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "idx_gtfs_stops_name_trgm",
        "gtfs_stops",
        ["stop_name"],
        postgresql_using="gin",
        postgresql_ops={"stop_name": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_gtfs_stops_parent_station",
        "gtfs_stops",
        ["parent_station"],
    )


def downgrade() -> None:
    op.drop_index("idx_gtfs_stops_parent_station", table_name="gtfs_stops")
    op.drop_index("idx_gtfs_stops_name_trgm", table_name="gtfs_stops")
