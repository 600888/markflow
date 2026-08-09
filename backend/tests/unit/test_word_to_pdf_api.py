import io
import zipfile
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import get_svc, get_word_to_pdf_registry, router
from app.core.interfaces import ConversionEngine
from app.db import ConversionRepository, Database
from app.models import ConversionPipeline, ConversionResult
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService


def _docx_bytes() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types />")
        archive.writestr("word/document.xml", b"<w:document />")
    return stream.getvalue()


class FakeEngine(ConversionEngine):
    async def convert(self, input_path, output_format, *args, **kwargs):
        output = input_path.with_suffix(f".{output_format.value}")
        output.write_bytes(b"%PDF-mock")
        return ConversionResult(
            task_id=uuid4(),
            output_path=output,
            output_format=output_format,
            duration_ms=1,
            file_size=9,
        )

    async def validate_format(self, output_format):
        return True


class FakeRegistry:
    engines = {"libreoffice": object()}

    def get_info(self, *, refresh=False):
        return {
            "available": True,
            "engine": "libreoffice",
            "default_engine": "libreoffice",
            "version": "26.2.0",
            "executable": "soffice.com",
            "supported_inputs": ["docx", "doc"],
            "diagnostic": "ready",
            "engines": [self.get_engine_info("libreoffice", refresh=refresh)],
        }

    def get_engine_info(self, engine_id, *, refresh=False):
        assert engine_id == "libreoffice"
        return {
            "id": "libreoffice",
            "name": "LibreOffice",
            "available": True,
            "version": "26.2.0",
            "executable": "soffice.com",
            "supported_inputs": ["docx", "doc"],
            "diagnostic": "ready",
            "fidelity": "compatible",
        }

    def resolve_engine_id(self, engine_id="", *, refresh=False):
        return engine_id or "libreoffice"


def test_word_to_pdf_status_and_submit(tmp_path) -> None:
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    engine = FakeEngine()
    service = ConversionService(
        engine,
        repository,
        ArtifactStorage(tmp_path),
        word_engine=engine,
    )
    registry = FakeRegistry()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_svc] = lambda: service
    app.dependency_overrides[get_word_to_pdf_registry] = lambda: registry

    with TestClient(app) as client:
        status = client.get("/word-to-pdf/status")
        response = client.post(
            "/word-to-pdf/convert",
            files={
                "file": (
                    "产品说明.docx",
                    _docx_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"quality": "standard", "export_bookmarks": "true"},
        )

    assert status.status_code == 200
    assert status.json()["available"] is True
    assert response.status_code == 200
    task_id = response.json()["task_id"]
    job = repository.get_job(task_id)
    assert job is not None
    assert job.pipeline == ConversionPipeline.WORD_TO_PDF.value
    assert job.source_file_name == "产品说明.docx"
    assert job.options_json["engine_version"] == "26.2.0"
    database.close()
