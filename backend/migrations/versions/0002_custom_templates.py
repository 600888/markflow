"""创建自定义模板表。"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_custom_templates"
down_revision: str | None = "0001_conversion_history"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "custom_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("target_formats_json", sa.JSON(), nullable=False),
        sa.Column("styles_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("artifact_relative_path", sa.Text(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_generator_version", sa.String(length=32), nullable=True),
        sa.Column("artifact_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_custom_templates_slug"),
    )
    op.create_index("ix_custom_templates_updated_at", "custom_templates", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_custom_templates_updated_at", table_name="custom_templates")
    op.drop_table("custom_templates")
