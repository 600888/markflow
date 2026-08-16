"""编码修复工具单元测试。"""

from __future__ import annotations

from app.utils.encoding import recover_filename


class TestRecoverFilename:
    def test_gbk_bytes_decoded_as_latin1(self) -> None:
        # 模拟：客户端发送 GBK 字节，starlette fallback latin-1
        mangled = "季度报告.pdf".encode("gbk").decode("latin-1")
        assert mangled != "季度报告.pdf"
        assert recover_filename(mangled) == "季度报告.pdf"

    def test_utf8_bytes_decoded_as_latin1(self) -> None:
        mangled = "测试报告.pdf".encode().decode("latin-1")
        assert recover_filename(mangled) == "测试报告.pdf"

    def test_normal_utf8_unchanged(self) -> None:
        assert recover_filename("季度报告.pdf") == "季度报告.pdf"

    def test_ascii_unchanged(self) -> None:
        assert recover_filename("report.pdf") == "report.pdf"

    def test_latin1_non_cjk_unchanged(self) -> None:
        # 无法恢复且不含 CJK 时保持原样
        assert recover_filename("café.pdf") == "café.pdf"

    def test_empty_and_none_safe(self) -> None:
        assert recover_filename("") == ""
