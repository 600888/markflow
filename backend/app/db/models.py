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
