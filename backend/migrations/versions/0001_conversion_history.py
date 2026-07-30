"""创建转换历史和产物表。"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_conversion_history"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """创建初始历史结构。"""
    op.create_table(
        "conversion_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("output_format", sa.String(length=16), nullable=False),
        sa.Column("template_slug", sa.String(length=128), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversion_jobs_created_at", "conversion_jobs", ["created_at"])
    op.create_index(
        "ix_conversion_jobs_source_file_name",
        "conversion_jobs",
        ["source_file_name"],
    )
    op.create_index(
        "ix_conversion_jobs_status_created_at",
        "conversion_jobs",
        ["status", "created_at"],
    )
    op.create_table(
        "conversion_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["conversion_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "kind", name="uq_artifact_job_kind"),
    )
    op.create_index(
        "ix_conversion_artifacts_job_id",
        "conversion_artifacts",
        ["job_id"],
    )


def downgrade() -> None:
    """移除历史结构。"""
    op.drop_index("ix_conversion_artifacts_job_id", table_name="conversion_artifacts")
    op.drop_table("conversion_artifacts")
    op.drop_index("ix_conversion_jobs_status_created_at", table_name="conversion_jobs")
    op.drop_index("ix_conversion_jobs_source_file_name", table_name="conversion_jobs")
    op.drop_index("ix_conversion_jobs_created_at", table_name="conversion_jobs")
    op.drop_table("conversion_jobs")
