"""转 Markdown 引擎单元测试。"""

from __future__ import annotations

import base64
import io
import zipfile

import pytest

from app.core.to_markdown_engine import (
    MarkItDownEngine,
    ToMarkdownEngineRegistry,
)
from app.models import OutputFormat
from app.utils.config import AppSettings
from app.utils.exceptions import (
    ConversionError,
    ToMarkdownUnavailableError,
    UnsupportedFormatError,
)

_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _png_bytes() -> bytes:
    return base64.b64decode(_PNG)


def _docx_bytes(*, omml: bool = False) -> bytes:
    stream = io.BytesIO()
    if omml:
        body = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
            "<m:oMath><m:r><m:t>x</m:t></m:r></m:oMath></w:document>"
        )
    else:
        body = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
        )
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", body.encode("utf-8"))
    return stream.getvalue()


def _docx_bytes_with_image(*names: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", b"<w:document />")
        for index, name in enumerate(names or ("image1.png",), start=1):
            archive.writestr(f"word/media/{name}", _png_bytes() + bytes([index]))
    return stream.getvalue()


def _install_markitdown(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.to_markdown_engine._markitdown_version",
        lambda: "0.1.7",
    )


class TestDocxImageExtraction:
    def test_extract_docx_images(self, tmp_path) -> None:
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes_with_image())
        assets = tmp_path / "assets" / "media"
        text = "# 标题\n\n![示意](data:image/png;base64...)\n"
        result = MarkItDownEngine._extract_docx_images(text, source, assets)
        assert "![示意](assets/media/image1.png)" in result
        assert "data:image" not in result
        assert (assets / "image1.png").read_bytes() == _png_bytes() + b"\x01"

    def test_extract_docx_images_multiple(self, tmp_path) -> None:
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes_with_image("image1.png", "image2.png"))
        assets = tmp_path / "assets" / "media"
        text = "![a](data:image/png;base64...) ![b](data:image/png;base64...)"
        result = MarkItDownEngine._extract_docx_images(text, source, assets)
        assert "assets/media/image1.png" in result
        assert "assets/media/image2.png" in result
        assert len(list(assets.glob("*"))) == 2

    def test_extract_docx_images_no_media(self, tmp_path) -> None:
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes())
        assets = tmp_path / "assets" / "media"
        text = "# 标题\n\n![x](data:image/png;base64...)\n"
        result = MarkItDownEngine._extract_docx_images(text, source, assets)
        assert "data:image/png;base64..." in result
        assert not assets.exists()

    def test_extract_docx_images_plain_text_unchanged(self, tmp_path) -> None:
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes_with_image())
        text = "# 标题\n\n无图片内容\n"
        result = MarkItDownEngine._extract_docx_images(text, source, tmp_path / "assets")
        assert result == text


class TestPdfImageExtraction:
    def test_extract_pdf_images(self, tmp_path) -> None:
        import fitz

        pdf_path = tmp_path / "sample.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_image(fitz.Rect(72, 72, 200, 180), stream=_png_bytes())
        doc.save(pdf_path)
        doc.close()

        assets = tmp_path / "assets" / "media"
        text = "# 标题\n\n正文内容"
        result = MarkItDownEngine._extract_pdf_images(text, pdf_path, assets)
        assert "## 图片资源" in result
        assert "assets/media/pdf_image_p001_" in result
        assert len(list(assets.glob("*.png"))) == 1

    def test_extract_pdf_images_none(self, tmp_path) -> None:
        import fitz

        pdf_path = tmp_path / "plain.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "plain text")
        doc.save(pdf_path)
        doc.close()

        text = "# 标题"
        result = MarkItDownEngine._extract_pdf_images(text, pdf_path, tmp_path / "assets")
        assert result == text


class TestDocxOmmlDetection:
    def test_docx_has_omml_true(self, tmp_path) -> None:
        path = tmp_path / "math.docx"
        path.write_bytes(_docx_bytes(omml=True))
        assert MarkItDownEngine._docx_has_omml(path) is True

    def test_docx_has_omml_false(self, tmp_path) -> None:
        path = tmp_path / "plain.docx"
        path.write_bytes(_docx_bytes())
        assert MarkItDownEngine._docx_has_omml(path) is False

    def test_docx_has_omml_invalid(self, tmp_path) -> None:
        path = tmp_path / "broken.docx"
        path.write_bytes(b"not a zip")
        assert MarkItDownEngine._docx_has_omml(path) is False


class TestMarkItDownEngineConvert:
    async def test_convert_docx_writes_md(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: "# 标题\n\n正文"),
        )
        result = await engine.convert(source, OutputFormat.MARKDOWN)
        assert result.output_format == OutputFormat.MARKDOWN
        assert result.output_path.name == "doc.md"
        assert result.output_path.read_text(encoding="utf-8") == "# 标题\n\n正文"

    async def test_convert_extracts_docx_images(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes_with_image())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: "![x](data:image/png;base64...)"),
        )
        result = await engine.convert(
            source,
            OutputFormat.MARKDOWN,
            options={"extract_images": True},
        )
        text = result.output_path.read_text(encoding="utf-8")
        assert "assets/media/image1.png" in text
        assert (tmp_path / "assets" / "media" / "image1.png").is_file()

    async def test_convert_skips_images_when_disabled(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes_with_image())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: "![x](data:image/png;base64...)"),
        )
        result = await engine.convert(
            source,
            OutputFormat.MARKDOWN,
            options={"extract_images": False},
        )
        text = result.output_path.read_text(encoding="utf-8")
        assert "data:image/png;base64..." in text
        assert not (tmp_path / "assets").exists()

    async def test_convert_rejects_wrong_format(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "a.docx"
        source.write_bytes(_docx_bytes())
        with pytest.raises(UnsupportedFormatError):
            await engine.convert(source, OutputFormat.PDF)

    async def test_convert_rejects_unsupported_suffix(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "a.txt"
        source.write_bytes(b"hello")
        with pytest.raises(UnsupportedFormatError):
            await engine.convert(source, OutputFormat.MARKDOWN)

    async def test_convert_unavailable_engine(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.core.to_markdown_engine._markitdown_version",
            lambda: "",
        )
        engine = MarkItDownEngine(AppSettings())
        source = tmp_path / "a.docx"
        source.write_bytes(_docx_bytes())
        with pytest.raises(ToMarkdownUnavailableError):
            await engine.convert(source, OutputFormat.MARKDOWN)

    async def test_convert_empty_pdf_without_ocr(self, tmp_path, monkeypatch) -> None:
        import fitz

        _install_markitdown(monkeypatch)
        monkeypatch.setattr(
            "app.core.to_markdown_engine.pdf_ocr.ocr_available",
            lambda: False,
        )
        pdf_path = tmp_path / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()
        engine = MarkItDownEngine(AppSettings())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: ""),
        )
        with pytest.raises(ConversionError, match="扫描件"):
            await engine.convert(pdf_path, OutputFormat.MARKDOWN)

    async def test_convert_scanned_pdf_uses_ocr(self, tmp_path, monkeypatch) -> None:
        import fitz

        _install_markitdown(monkeypatch)
        monkeypatch.setattr(
            "app.core.to_markdown_engine.pdf_ocr.ocr_available",
            lambda: True,
        )

        async def fake_ocr_pdf(input_path, assets_dir, *, extract_images, on_progress):
            if extract_images:
                assets_dir.mkdir(parents=True, exist_ok=True)
                (assets_dir / "page_001.png").write_bytes(b"png")
            return "# 扫描件标题\n\nOCR 识别正文。\n"

        monkeypatch.setattr(
            "app.core.to_markdown_engine.pdf_ocr.ocr_pdf",
            fake_ocr_pdf,
        )
        pdf_path = tmp_path / "scan.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()
        engine = MarkItDownEngine(AppSettings())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: ""),
        )
        result = await engine.convert(pdf_path, OutputFormat.MARKDOWN)
        assert result.output_format == OutputFormat.MARKDOWN
        text = result.output_path.read_text(encoding="utf-8")
        assert "# 扫描件标题" in text
        assert (tmp_path / "assets" / "media" / "page_001.png").is_file()

    async def test_convert_force_ocr_skips_markitdown(self, tmp_path, monkeypatch) -> None:
        import fitz

        _install_markitdown(monkeypatch)
        monkeypatch.setattr(
            "app.core.to_markdown_engine.pdf_ocr.ocr_available",
            lambda: True,
        )
        called: list[str] = []

        async def fake_ocr_pdf(input_path, assets_dir, *, extract_images, on_progress):
            called.append("ocr")
            return "强制 OCR 结果\n"

        monkeypatch.setattr(
            "app.core.to_markdown_engine.pdf_ocr.ocr_pdf",
            fake_ocr_pdf,
        )
        pdf_path = tmp_path / "text.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "text layer")
        doc.save(pdf_path)
        doc.close()
        engine = MarkItDownEngine(AppSettings())

        def unexpected(_path):  # pragma: no cover - 不应被调用
            called.append("markitdown")
            return "markitdown 结果"

        monkeypatch.setattr(MarkItDownEngine, "_convert_text", staticmethod(unexpected))
        result = await engine.convert(
            pdf_path,
            OutputFormat.MARKDOWN,
            options={"force_ocr": True},
        )
        assert called == ["ocr"]
        assert result.output_path.read_text(encoding="utf-8") == "强制 OCR 结果\n"

    async def test_validate_format(self, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        engine = MarkItDownEngine(AppSettings())
        assert await engine.validate_format(OutputFormat.MARKDOWN) is True
        assert await engine.validate_format(OutputFormat.DOCX) is False


class TestToMarkdownEngineRegistry:
    def test_get_info(self) -> None:
        registry = ToMarkdownEngineRegistry(AppSettings())
        info = registry.get_info()
        assert info["default_engine"] == "markitdown"
        assert [item["id"] for item in info["engines"]] == [
            "markitdown",
            "word-com",
            "pdf-ocr",
        ]
        assert info["engines"][0]["supported_inputs"] == ["docx", "pdf"]

    def test_resolve_engine_id(self) -> None:
        registry = ToMarkdownEngineRegistry(AppSettings())
        assert registry.resolve_engine_id("") == "markitdown"
        assert registry.resolve_engine_id("markitdown") == "markitdown"

    async def test_convert_dispatch(self, tmp_path, monkeypatch) -> None:
        _install_markitdown(monkeypatch)
        registry = ToMarkdownEngineRegistry(AppSettings())
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes())
        monkeypatch.setattr(
            MarkItDownEngine,
            "_convert_text",
            staticmethod(lambda path: "# ok"),
        )
        result = await registry.convert(
            source,
            OutputFormat.MARKDOWN,
            options={"engine": "markitdown"},
        )
        assert result.output_format == OutputFormat.MARKDOWN

    async def test_convert_unknown_engine(self, tmp_path) -> None:
        registry = ToMarkdownEngineRegistry(AppSettings())
        source = tmp_path / "doc.docx"
        source.write_bytes(_docx_bytes())
        with pytest.raises(ToMarkdownUnavailableError):
            await registry.convert(
                source,
                OutputFormat.MARKDOWN,
                options={"engine": "unknown"},
            )

    async def test_validate_format(self) -> None:
        registry = ToMarkdownEngineRegistry(AppSettings())
        assert await registry.validate_format(OutputFormat.MARKDOWN) is True
        assert await registry.validate_format(OutputFormat.PDF) is False
