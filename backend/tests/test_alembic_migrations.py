from __future__ import annotations

from pathlib import Path
import re


def test_alembic_revision_ids_fit_version_column() -> None:
    """Alembic's default version_num column is varchar(32)."""

    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    migration_files = versions_dir.glob("*.py")
    revision_pattern = re.compile(r'^(?:revision|down_revision):.*=\s*"([^"]+)"', re.M)

    oversized_revisions: list[str] = []
    for migration_file in migration_files:
        for revision_id in revision_pattern.findall(migration_file.read_text()):
            if len(revision_id) > 32:
                oversized_revisions.append(f"{migration_file.name}: {revision_id}")

    assert oversized_revisions == []
