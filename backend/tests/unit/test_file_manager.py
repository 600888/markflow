"""文件管理器单元测试"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.file_manager import TempFileManager, _safe_filename
from app.models import OutputFormat


class TestSafeFilename:
    def test_simple_name(self) -> None:
        assert _safe_filename("test.md") == "test.md"

    def test_path_traversal(self) -> None:
        assert _safe_filename("../evil.md") == "evil.md"

    def test_windows_invalid_chars(self) -> None:
        result = _safe_filename('a<b>c:d"e|f*g?hello.md')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result

    def test_empty_result(self) -> None:
        result = _safe_filename("")
        assert result == "untitled"

    def test_absolute_on_windows(self) -> None:
        result = _safe_filename("C:\\Windows\\evil.exe")
        assert result == "evil.exe"


class TestTempFileManager:
    @pytest.fixture
    def manager(self, tmp_path: Path) -> TempFileManager:
        from app.utils.config import AppSettings

        settings = AppSettings(
            temp_dir=tmp_path / "temp",
            output_dir=tmp_path / "output",
        )
        return TempFileManager(settings)

    async def test_save_and_read(self, manager: TempFileManager) -> None:
        path = await manager.save_upload(b"hello world", "test.md")
        assert path.exists()
        assert path.read_text() == "hello world"

    async def test_cleanup(self, manager: TempFileManager) -> None:
        path = await manager.save_upload(b"data", "clean.md")
        assert path.exists()
        await manager.cleanup(path)
        assert not path.exists()

    async def test_cleanup_nonexistent(self, manager: TempFileManager) -> None:
        """清理不存在的文件不应报错"""
        await manager.cleanup(Path("/nonexistent/file.md"))

    async def test_path_traversal_prevention(self, manager: TempFileManager) -> None:
        """_safe_filename 应该过滤掉路径遍历，保存到 temp_dir 下"""
        path = await manager.save_upload(b"evil", "../evil.md")
        # 文件名应该被过滤为 evil.md，保存在 temp_dir 下
        assert path.name == "evil.md"
        assert str(path.parent).endswith("temp")

    async def test_get_output_path(self, manager: TempFileManager) -> None:
        path = manager.get_output_path("input.md", OutputFormat.PDF)
        assert path.name == "input.pdf"
        assert str(path.parent).endswith("output")
