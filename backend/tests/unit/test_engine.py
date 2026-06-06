"""Pandoc 引擎单元测试"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.engine import PandocEngine
from app.models import OutputFormat
from app.utils.exceptions import ConversionError


class TestPandocEngine:
    @patch("pypandoc.get_pandoc_path", return_value="/usr/bin/pandoc")
    async def test_all_formats_supported(self, mock_pandoc) -> None:
        """所有 OutputFormat 枚举值都应该被支持"""
        engine = PandocEngine()
        for fmt in OutputFormat:
            assert await engine.validate_format(fmt), f"{fmt} 应该被支持"

    @patch("pypandoc.get_pandoc_path", return_value="/usr/bin/pandoc")
    async def test_convert_success(self, mock_pandoc_path, tmp_path: Path) -> None:
        """正常转换应返回 ConversionResult"""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Hello")
        output_file = input_file.with_suffix(".docx")
        output_file.write_text("mock output")

        engine = PandocEngine()
        with patch("pypandoc.convert_file", return_value=str(output_file)):
            result = await engine.convert(input_file, OutputFormat.DOCX)

        assert result.output_format == OutputFormat.DOCX
        assert result.duration_ms >= 0
        assert result.file_size >= 0

    @patch("pypandoc.get_pandoc_path", return_value="/usr/bin/pandoc")
    @patch("pypandoc.convert_file", side_effect=RuntimeError("Pandoc crashed"))
    async def test_convert_failure(self, mock_convert, mock_pandoc_path, tmp_path: Path) -> None:
        """Pandoc 异常应转为 ConversionError"""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Hello")

        engine = PandocEngine()
        with pytest.raises(ConversionError) as exc_info:
            await engine.convert(input_file, OutputFormat.DOCX)

        assert "Pandoc" in exc_info.value.message

    @patch("pypandoc.get_pandoc_path", return_value="/usr/bin/pandoc")
    async def test_convert_with_progress(self, mock_pandoc_path, tmp_path: Path) -> None:
        """应调用进度回调"""
        input_file = tmp_path / "test.md"
        input_file.write_text("# Hello")
        output_file = input_file.with_suffix(".docx")
        output_file.write_text("mock output")

        on_progress = AsyncMock()

        engine = PandocEngine()
        with patch("pypandoc.convert_file", return_value=str(output_file)):
            await engine.convert(input_file, OutputFormat.DOCX, on_progress=on_progress)

        assert on_progress.await_count >= 1
