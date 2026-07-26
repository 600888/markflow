"""数据模型单元测试"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from app.models import ConversionResult, ConversionStatus, ConversionTask, OutputFormat


class TestOutputFormat:
    def test_all_values(self) -> None:
        assert OutputFormat.DOCX.value == "docx"
        assert OutputFormat.PDF.value == "pdf"
        assert OutputFormat.HTML.value == "html"
        assert OutputFormat.EPUB.value == "epub"
        assert OutputFormat.LATEX.value == "latex"
        assert OutputFormat.MARKDOWN.value == "md"
        assert OutputFormat.ODT.value == "odt"
        assert OutputFormat.RTF.value == "rtf"

    def test_from_string(self) -> None:
        assert OutputFormat("docx") == OutputFormat.DOCX
        assert OutputFormat("pdf") == OutputFormat.PDF

    def test_invalid_string(self) -> None:
        with pytest.raises(ValueError):
            OutputFormat("invalid")  # type: ignore[call-arg]


class TestConversionStatus:
    def test_transitions(self) -> None:
        assert ConversionStatus.PENDING.value == "pending"
        assert ConversionStatus.RUNNING.value == "running"
        assert ConversionStatus.COMPLETED.value == "completed"
        assert ConversionStatus.FAILED.value == "failed"
        assert ConversionStatus.CANCELLED.value == "cancelled"


class TestConversionTask:
    def test_default_values(self) -> None:
        task = ConversionTask(input_path="test.md", output_format=OutputFormat.DOCX)  # type: ignore[arg-type]
        assert isinstance(task.task_id, UUID)
        assert task.status == ConversionStatus.PENDING
        assert task.progress == 0.0
        assert isinstance(task.created_at, datetime)
        assert task.completed_at is None
        assert task.error is None
        assert task.extra_args == []
        assert task.convert_images is True
        assert task.convert_mermaid is True
        assert task.output_path is None

    def test_serialization(self) -> None:
        task = ConversionTask(input_path="test.md", output_format=OutputFormat.PDF)  # type: ignore[arg-type]
        data = task.model_dump()
        assert data["output_format"] == "pdf"
        assert data["status"] == "pending"

    def test_deserialization(self) -> None:
        raw = {
            "input_path": "test.md",
            "output_format": "html",
            "status": "running",
            "progress": 0.5,
        }
        task = ConversionTask.model_validate(raw)
        assert task.output_format == OutputFormat.HTML
        assert task.status == ConversionStatus.RUNNING
        assert task.progress == 0.5


class TestConversionResult:
    def test_create(self) -> None:
        from uuid import UUID

        result = ConversionResult(
            task_id=UUID("00000000-0000-0000-0000-000000000001"),
            output_path="out.docx",
            output_format=OutputFormat.DOCX,
            duration_ms=1500,
            file_size=10240,
        )
        assert result.duration_ms == 1500
        assert result.file_size == 10240
