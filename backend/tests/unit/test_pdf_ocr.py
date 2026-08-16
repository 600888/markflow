"""扫描件 PDF OCR 提取单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import pdf_ocr
from app.core.pdf_ocr import OcrLine, _build_markdown, _merge_line_text, _PageResult
from app.utils.exceptions import ConversionError


class TestBuildMarkdown:
    def _line(self, text: str, y0: float, height: float, x0: float = 0.0) -> OcrLine:
        return OcrLine(text, 0.99, page=1, x0=x0, y0=y0, height=height)

    def test_title_heuristic_and_paragraphs(self) -> None:
        lines = [
            self._line("项目技术报告", y0=100, height=40),  # 大字号 → 标题
            self._line("这是第一段的第一行", y0=200, height=20),
            self._line("这是第一段的第二行", y0=235, height=20),
            self._line("这是第二段内容", y0=400, height=20),
        ]
        markdown = _build_markdown([_PageResult(1, lines, None)], include_images=False)
        assert "# 项目技术报告" in markdown
        assert "这是第一段的第一行" in markdown
        assert "这是第一段的第二行" in markdown
        # 相邻段落以空行分隔
        assert "这是第一段的第二行\n\n这是第二段内容" in markdown

    def test_same_row_merge_without_space_for_cjk(self) -> None:
        lines = [
            OcrLine("列A", 0.9, page=1, x0=50, y0=300, height=20),
            OcrLine("列B", 0.9, page=1, x0=200, y0=300, height=20),
        ]
        markdown = _build_markdown([_PageResult(1, lines, None)], include_images=False)
        assert "列A列B" in markdown

    def test_page_number_filtered(self) -> None:
        lines = [
            self._line("正文内容", y0=200, height=20),
            self._line("12", y0=800, height=16),  # 页码应被过滤
        ]
        markdown = _build_markdown([_PageResult(1, lines, None)], include_images=False)
        assert "正文内容" in markdown
        assert "\n12" not in markdown

    def test_page_images_section(self) -> None:
        lines = [self._line("正文", y0=200, height=20)]
        page = _PageResult(1, lines, Path("assets/media/page_001.png"))
        markdown = _build_markdown([page], include_images=True)
        assert "## 页面图像" in markdown
        assert "![第 1 页](assets/media/page_001.png)" in markdown

    def test_empty_pages_produce_empty(self) -> None:
        assert _build_markdown([], include_images=True) == ""
        assert _build_markdown([_PageResult(1, [], None)], include_images=True) == ""


class TestMergeLineText:
    def test_cjk_no_space(self) -> None:
        assert _merge_line_text("你好", "世界") == "你好世界"

    def test_english_space(self) -> None:
        assert _merge_line_text("hello", "world") == "hello world"

    def test_mixed(self) -> None:
        assert _merge_line_text("版本", "2.0") == "版本2.0"
        assert _merge_line_text("v", "1.0") == "v 1.0"


class TestOcrPdf:
    async def test_ocr_pdf_requires_engine(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.pdf_ocr.ocr_available", lambda: False)
        pdf_path = tmp_path / "scan.pdf"
        pdf_path.write_bytes(b"not a real pdf")
        with pytest.raises(ConversionError, match="OCR 引擎"):
            await pdf_ocr.ocr_pdf(pdf_path, tmp_path / "assets", extract_images=True)

    async def test_ocr_pdf_flow(self, tmp_path, monkeypatch) -> None:
        import fitz

        monkeypatch.setattr("app.core.pdf_ocr.ocr_available", lambda: True)
        pdf_path = tmp_path / "scan.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "hello")
        doc.save(pdf_path)
        doc.close()

        def fake_ocr_image(image_path: Path, page: int) -> list[OcrLine]:
            return [OcrLine("扫描件第 N 页内容", 0.99, page, 10, 100, 30)]

        monkeypatch.setattr("app.core.pdf_ocr._ocr_image", fake_ocr_image)
        assets = tmp_path / "assets" / "media"
        markdown = await pdf_ocr.ocr_pdf(pdf_path, assets, extract_images=True)
        assert "扫描件第 N 页内容" in markdown
        assert (assets / "page_001.png").is_file()
        assert "## 页面图像" in markdown

    async def test_ocr_pdf_no_images(self, tmp_path, monkeypatch) -> None:
        import fitz

        monkeypatch.setattr("app.core.pdf_ocr.ocr_available", lambda: True)
        pdf_path = tmp_path / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()

        def fake_ocr_image(image_path: Path, page: int) -> list[OcrLine]:
            return [OcrLine("正文", 0.99, page, 10, 100, 30)]

        monkeypatch.setattr("app.core.pdf_ocr._ocr_image", fake_ocr_image)
        assets = tmp_path / "assets" / "media"
        markdown = await pdf_ocr.ocr_pdf(pdf_path, assets, extract_images=False)
        assert "正文" in markdown
        assert "## 页面图像" not in markdown
        assert not assets.exists()

    async def test_ocr_pdf_empty_result_raises(self, tmp_path, monkeypatch) -> None:
        import fitz

        monkeypatch.setattr("app.core.pdf_ocr.ocr_available", lambda: True)
        pdf_path = tmp_path / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()

        monkeypatch.setattr("app.core.pdf_ocr._ocr_image", lambda image_path, page: [])
        with pytest.raises(ConversionError, match="未能"):
            await pdf_ocr.ocr_pdf(pdf_path, tmp_path / "assets", extract_images=True)
