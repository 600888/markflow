"""增加模板修订历史与转换模板快照。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0003_template_history_and_snapshots"
down_revision: str | None = "0002_custom_templates"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """创建修订表、转换快照字段并回填已有模板基线。"""
    op.add_column("conversion_jobs", sa.Column("template_revision", sa.Integer(), nullable=True))
    op.add_column("conversion_jobs", sa.Column("template_snapshot_json", sa.JSON(), nullable=True))
    op.create_table(
        "custom_template_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("artifact_relative_path", sa.Text(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_generator_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "revision",
            name="uq_custom_template_revisions_template_revision",
        ),
    )
    op.create_index(
        "ix_custom_template_revisions_template_id",
        "custom_template_revisions",
        ["template_id"],
    )
    op.create_index(
        "ix_custom_template_revisions_slug",
        "custom_template_revisions",
        ["slug"],
    )

    # 已存在的数据库模板补记为首个可恢复修订，升级后不会丢失历史基线。
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT * FROM custom_templates")).mappings()
    revision_table = sa.table(
        "custom_template_revisions",
        sa.column("template_id", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("revision", sa.Integer()),
        sa.column("operation", sa.String()),
        sa.column("definition_json", sa.JSON()),
        sa.column("artifact_relative_path", sa.Text()),
        sa.column("artifact_sha256", sa.String()),
        sa.column("artifact_generator_version", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    revisions = []
    for row in rows:
        formats = row["target_formats_json"]
        styles = row["styles_json"]
        if isinstance(formats, str):
            formats = json.loads(formats)
        if isinstance(styles, str):
            styles = json.loads(styles)
        created_at = row["updated_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        revisions.append(
            {
                "template_id": row["id"],
                "slug": row["slug"],
                "revision": row["revision"],
                "operation": "migrated",
                "definition_json": {
                    "name": row["name"],
                    "slug": row["slug"],
                    "description": row["description"],
                    "author": row["author"],
                    "version": row["version"],
                    "target_formats": formats,
                    "styles": styles,
                },
                "artifact_relative_path": row["artifact_relative_path"],
                "artifact_sha256": row["artifact_sha256"],
                "artifact_generator_version": row["artifact_generator_version"],
                "created_at": created_at,
            }
        )
    if revisions:
        connection.execute(revision_table.insert(), revisions)


def downgrade() -> None:
    """移除模板历史和转换快照结构。"""
    op.drop_index(
        "ix_custom_template_revisions_slug",
        table_name="custom_template_revisions",
    )
    op.drop_index(
        "ix_custom_template_revisions_template_id",
        table_name="custom_template_revisions",
    )
    op.drop_table("custom_template_revisions")
    op.drop_column("conversion_jobs", "template_snapshot_json")
    op.drop_column("conversion_jobs", "template_revision")
