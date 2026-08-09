"""为转换任务增加处理管线。"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_conversion_pipeline"
down_revision: str | None = "0003_template_history_and_snapshots"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """增加管线字段并把已有任务回填为 Markdown 转换。"""
    with op.batch_alter_table("conversion_jobs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "pipeline",
                sa.String(length=32),
                nullable=False,
                server_default="markdown",
            )
        )


def downgrade() -> None:
    """移除转换管线字段。"""
    with op.batch_alter_table("conversion_jobs") as batch_op:
        batch_op.drop_column("pipeline")
