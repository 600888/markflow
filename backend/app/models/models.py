"""数据模型定义"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OutputFormat(StrEnum):
    """支持的输出格式"""

    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    EPUB = "epub"
    LATEX = "latex"
    MARKDOWN = "md"
    ODT = "odt"
    RTF = "rtf"


class ConversionStatus(StrEnum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversionTask(BaseModel):
    """转换任务"""

    task_id: UUID = Field(default_factory=uuid4)
    input_path: Path
    output_format: OutputFormat
    template_slug: str | None = None
    convert_images: bool = True
    convert_mermaid: bool = True
    status: ConversionStatus = ConversionStatus.PENDING
    progress: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None
    extra_args: list[str] = Field(default_factory=list)
    output_path: Path | None = None


class ConversionResult(BaseModel):
    """转换结果"""

    task_id: UUID
    output_path: Path
    output_format: OutputFormat
    duration_ms: int
    file_size: int
