"""SQLAlchemy 持久化模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式模型基类。"""


class ConversionJobEntity(Base):
    """转换任务记录。"""

    __tablename__ = "conversion_jobs"
    __table_args__ = (
        Index("ix_conversion_jobs_created_at", "created_at"),
        Index("ix_conversion_jobs_status_created_at", "status", "created_at"),
        Index("ix_conversion_jobs_source_file_name", "source_file_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), nullable=False)
    template_slug: Mapped[str | None] = mapped_column(String(128))
    template_revision: Mapped[int | None] = mapped_column(Integer)
    template_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    options_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    artifacts: Mapped[list[ConversionArtifactEntity]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ConversionArtifactEntity(Base):
    """源文件或转换产物。"""

    __tablename__ = "conversion_artifacts"
    __table_args__ = (UniqueConstraint("job_id", "kind", name="uq_artifact_job_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversion_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[ConversionJobEntity] = relationship(back_populates="artifacts")


class CustomTemplateEntity(Base):
    """数据库中的自定义模板定义与派生文件索引。"""

    __tablename__ = "custom_templates"
    __table_args__ = (
        Index("ix_custom_templates_updated_at", "updated_at"),
        UniqueConstraint("slug", name="uq_custom_templates_slug"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="MarkFlow")
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    target_formats_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    styles_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    artifact_relative_path: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_generator_version: Mapped[str | None] = mapped_column(String(32))
    artifact_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CustomTemplateRevisionEntity(Base):
    """不可变的自定义模板修订和删除事件。"""

    __tablename__ = "custom_template_revisions"
    __table_args__ = (
        Index("ix_custom_template_revisions_template_id", "template_id"),
        Index("ix_custom_template_revisions_slug", "slug"),
        UniqueConstraint(
            "template_id",
            "revision",
            name="uq_custom_template_revisions_template_revision",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_relative_path: Mapped[str | None] = mapped_column(Text)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_generator_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
