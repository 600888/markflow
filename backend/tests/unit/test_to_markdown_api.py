"""转 Markdown API 单元测试。"""

from __future__ import annotations

import io
import threading
import time
import zipfile
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import (
    get_artifact_storage,
    get_svc,
    get_to_markdown_registry,
    router,
)
from app.core.interfaces import ConversionEngine
from app.db import ConversionRepository, Database
from app.models import ConversionPipeline, ConversionResult, OutputFormat
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService


def _docx_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", b"<w:document />")
    return stream.getvalue()


class FakeEngine(ConversionEngine):
    """模拟 to_markdown 引擎：产出 md 文件与图片资源目录。"""

    async def convert(self, input_path, output_format, *args, **kwargs):
        md_path = input_path.with_suffix(".md")
        md_path.write_text("# 转换结果\n\n![图片](assets/media/image_0001.png)\n", encoding="utf-8")
        assets = input_path.parent / "assets" / "media"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "image_0001.png").write_bytes(b"png-data")
        return ConversionResult(
            task_id=uuid4(),
            output_path=md_path,
            output_format=output_format,
            duration_ms=1,
            file_size=md_path.stat().st_size,
        )

    async def validate_format(self, output_format):
        return output_format == OutputFormat.MARKDOWN


class FakeRegistry:
    """模拟 ToMarkdownEngineRegistry 状态。"""

    def get_info(self, *, refresh=False):
        return {
            "available": True,
            "engine": "markitdown",
            "default_engine": "markitdown",
            "version": "0.1.7",
            "supported_inputs": ["docx", "doc", "pdf"],
            "diagnostic": "ready",
            "engines": [
                self.get_engine_info("markitdown", refresh=refresh),
                self.get_engine_info("word-com", refresh=refresh),
            ],
        }

    def get_engine_info(self, engine_id, *, refresh=False):
        assert engine_id in {"markitdown", "word-com"}
        if engine_id == "word-com":
            return {
                "id": "word-com",
                "name": "Word 兼容（COM）",
                "available": False,
                "version": "",
                "supported_inputs": ["doc"],
                "diagnostic": "未检测到 Word 或 WPS",
            }
        return {
            "id": "markitdown",
            "name": "MarkItDown",
            "available": True,
            "version": "0.1.7",
            "supported_inputs": ["docx", "pdf"],
            "diagnostic": "ready",
        }

    def resolve_engine_id(self, engine_id="", *, refresh=False):
        return engine_id or "markitdown"


class ThreadRecordingRegistry(FakeRegistry):
    """记录状态检测实际运行的线程。"""

    def __init__(self) -> None:
        self.thread_id: int | None = None

    def get_info(self, *, refresh=False):
        self.thread_id = threading.get_ident()
        return super().get_info(refresh=refresh)


def _build_app(tmp_path) -> tuple[FastAPI, ConversionService, ConversionRepository]:
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    engine = FakeEngine()
    service = ConversionService(
        engine,
        repository,
        ArtifactStorage(tmp_path),
        to_markdown_engine=engine,
    )
    registry = FakeRegistry()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_svc] = lambda: service
    app.dependency_overrides[get_to_markdown_registry] = lambda: registry
    app.dependency_overrides[get_artifact_storage] = lambda: ArtifactStorage(tmp_path)
    return app, service, repository


def test_to_markdown_status(tmp_path) -> None:
    app, _, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/to-markdown/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["default_engine"] == "markitdown"
    assert [item["id"] for item in body["engines"]] == ["markitdown", "word-com"]


def test_to_markdown_status_runs_detection_in_worker_thread(tmp_path) -> None:
    app, _, _ = _build_app(tmp_path)
    registry = ThreadRecordingRegistry()
    app.dependency_overrides[get_to_markdown_registry] = lambda: registry

    with TestClient(app) as client:
        request_thread_id = client.portal.call(threading.get_ident)
        response = client.get("/to-markdown/status")

    assert response.status_code == 200
    assert registry.thread_id is not None
    assert registry.thread_id != request_thread_id


def test_to_markdown_convert_submit(tmp_path) -> None:
    app, _, repository = _build_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/to-markdown/convert",
            files={
                "file": (
                    "产品说明.docx",
                    _docx_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={
                "output_file_name": "说明.md",
                "extract_tables": "true",
                "extract_images": "false",
                "extract_formulas": "true",
            },
        )
    assert response.status_code == 200
    task_id = response.json()["task_id"]
    job = repository.get_job(task_id)
    assert job is not None
    assert job.pipeline == ConversionPipeline.TO_MARKDOWN.value
    assert job.output_format == OutputFormat.MARKDOWN.value
    assert job.source_file_name == "产品说明.docx"
    assert job.options_json["engine"] == "markitdown"
    assert job.options_json["extract_images"] is False
    assert job.options_json["extract_tables"] is True


def test_to_markdown_convert_rejects_bad_extension(tmp_path) -> None:
    app, _, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/to-markdown/convert",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
    assert response.status_code == 400
    assert "不支持的源文件格式" in response.json()["detail"]


def test_to_markdown_convert_executes_and_previews(tmp_path) -> None:
    app, _, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        submitted = client.post(
            "/to-markdown/convert",
            files={"file": ("产品说明.docx", _docx_bytes(), "application/octet-stream")},
            data={"output_file_name": "产品说明.md"},
        )
        assert submitted.status_code == 200
        task_id = submitted.json()["task_id"]

        # 后台任务由端点调度，轮询等待其完成
        for _ in range(200):
            task = client.get(f"/tasks/{task_id}").json()
            if task["status"] in ("completed", "failed"):
                break
            time.sleep(0.02)
        assert task["status"] == "completed"

        preview = client.get(f"/tasks/{task_id}/markdown")
        download = client.get(f"/tasks/{task_id}/download")
    assert preview.status_code == 200
    assert "# 转换结果" in preview.text
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = archive.namelist()
        assert "产品说明.md" in names
        assert any(name.startswith("assets/media/") for name in names)


def test_to_markdown_preview_missing_task(tmp_path) -> None:
    app, _, _ = _build_app(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"/tasks/{uuid4()}/markdown")
    assert response.status_code == 404
