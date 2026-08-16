"""图片 OCR 引擎与 API 单元测试。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import get_svc, router
from app.core import image_ocr
from app.core.image_ocr import (
    OcrLineResult,
    _build_text,
    _group_paragraphs,
    _merge_text,
    recognize_image,
)
from app.services.artifact_storage import ArtifactStorage
from app.utils.exceptions import OcrUnavailableError


def _png_bytes() -> bytes:
    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGB", (60, 40), (255, 255, 255)).save(stream, format="PNG")
    return stream.getvalue()


def _make_image(tmp_path: Path, name: str = "test.png") -> Path:
    path = tmp_path / name
    path.write_bytes(_png_bytes())
    return path


class TestBuildText:
    def _line(
        self,
        text: str,
        y: int,
        height: int = 20,
        x: int = 0,
    ) -> OcrLineResult:
        return OcrLineResult(text, 0.99, x, y, 200, height)

    def test_keep_layout_preserves_newlines(self) -> None:
        lines = [
            self._line("第一行", y=100),
            self._line("第二行", y=130),
            self._line("下一段", y=300),
        ]
        text = _build_text(lines, keep_layout=True)
        assert "第一行\n第二行" in text
        assert "第二行\n\n下一段" in text

    def test_merge_paragraph_when_not_keep_layout(self) -> None:
        lines = [
            self._line("第一行", y=100),
            self._line("第二行", y=130),
        ]
        text = _build_text(lines, keep_layout=False)
        assert "第一行第二行" in text

    def test_empty_lines(self) -> None:
        assert _build_text([], keep_layout=True) == ""
        assert _build_text([], keep_layout=False) == ""

    def test_same_row_merged_by_x(self) -> None:
        lines = [
            self._line("列A", y=100, x=50),
            self._line("列B", y=100, x=300),
        ]
        text = _build_text(lines, keep_layout=False)
        assert "列A列B" in text


class TestGroupParagraphs:
    def test_groups_by_gap(self) -> None:
        lines = [
            OcrLineResult("a", 0.9, 0, 100, 100, 20),
            OcrLineResult("b", 0.9, 0, 130, 100, 20),
            OcrLineResult("c", 0.9, 0, 400, 100, 20),
        ]
        groups = _group_paragraphs(lines)
        assert len(groups) == 2
        assert [line.text for line in groups[0]] == ["a", "b"]
        assert [line.text for line in groups[1]] == ["c"]


class TestMergeText:
    def test_cjk_no_space(self) -> None:
        assert _merge_text("你好", "世界") == "你好世界"

    def test_english_space(self) -> None:
        assert _merge_text("hello", "world") == "hello world"


class TestRecognizeImage:
    def test_supported_extensions(self) -> None:
        assert image_ocr.supported_extension(".png") is True
        assert image_ocr.supported_extension(".JPG") is True
        assert image_ocr.supported_extension(".gif") is False

    def test_recognize_requires_engine(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: False)
        with pytest.raises(OcrUnavailableError):
            recognize_image(_make_image(tmp_path), keep_layout=True)

    def test_recognize_flow(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: True)

        def fake_recognize(image_path):
            return (
                [
                    OcrLineResult("识别结果第一行", 0.98, 10, 20, 300, 30),
                    OcrLineResult("识别结果第二行", 0.95, 10, 60, 300, 30),
                ],
                60,
                40,
            )

        monkeypatch.setattr("app.core.image_ocr._recognize", fake_recognize)
        result = recognize_image(_make_image(tmp_path), keep_layout=True)
        assert result.line_count == 2
        assert "识别结果第一行\n识别结果第二行" in result.text
        assert result.confidence == pytest.approx(0.965, abs=0.001)
        assert result.duration_ms >= 0
        assert result.width == 60
        assert result.height == 40

    def test_recognize_unreadable_image(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: True)
        path = tmp_path / "broken.png"
        path.write_bytes(b"not an image")
        with pytest.raises(Exception):  # noqa: B017 - ConversionError
            recognize_image(path, keep_layout=True)


class TestOcrApi:
    def _build_app(self, tmp_path):
        from app.api.errors import register_error_handlers
        from app.db import ConversionRepository, Database
        from app.services.converter import ConversionService

        database = Database(tmp_path)
        database.initialize()
        repository = ConversionRepository(database.session_factory)
        service = ConversionService(
            object(),  # type: ignore[arg-type] - 仅用于 max_file_size
            repository,
            ArtifactStorage(tmp_path),
        )
        app = FastAPI()
        app.include_router(router)
        register_error_handlers(app)
        app.dependency_overrides[get_svc] = lambda: service
        return app

    def test_ocr_status(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: True)
        app = self._build_app(tmp_path)
        with TestClient(app) as client:
            response = client.get("/ocr/status")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["engine"] == "rapidocr"

    def test_ocr_recognize_success(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: True)
        monkeypatch.setattr(
            "app.core.image_ocr.recognize_image",
            lambda image_path, keep_layout=True: image_ocr.OcrResult(
                text="发票识别结果",
                lines=[OcrLineResult("发票识别结果", 0.99, 0, 0, 200, 30)],
                confidence=0.99,
                duration_ms=800,
                width=60,
                height=40,
                line_count=1,
            ),
        )
        app = self._build_app(tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/ocr/recognize",
                files={"file": ("发票.png", _png_bytes(), "image/png")},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["text"] == "发票识别结果"
        assert body["line_count"] == 1
        assert body["confidence"] == pytest.approx(0.99)
        assert body["duration_ms"] == 800

    def test_ocr_recognize_bad_extension(self, tmp_path) -> None:
        app = self._build_app(tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/ocr/recognize",
                files={"file": ("note.txt", b"hello", "text/plain")},
            )
        assert response.status_code == 400
        assert "不支持的图片格式" in response.json()["detail"]

    def test_ocr_recognize_engine_unavailable(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr("app.core.image_ocr.ocr_available", lambda: False)
        app = self._build_app(tmp_path)
        with TestClient(app) as client:
            response = client.post(
                "/ocr/recognize",
                files={"file": ("a.png", _png_bytes(), "image/png")},
            )
        assert response.status_code == 503
        assert "OCR 引擎" in response.json()["detail"]
