from uuid import uuid4

import pytest

from app.core.interfaces import ConversionEngine
from app.db import ConversionRepository, Database
from app.models import ConversionPipeline, ConversionResult, OutputFormat
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService


class FakeMarkdownEngine(ConversionEngine):
    async def convert(self, input_path, output_format, *args, on_progress=None, **kwargs):
        output = input_path.with_suffix(f".{output_format.value}")
        output.write_bytes(b"markdown")
        return ConversionResult(
            task_id=uuid4(),
            output_path=output,
            output_format=output_format,
            duration_ms=1,
            file_size=8,
        )

    async def validate_format(self, output_format):
        return True


class FakeWordEngine(ConversionEngine):
    def __init__(self) -> None:
        self.options = None

    async def convert(self, input_path, output_format, *args, options=None, **kwargs):
        self.options = options
        output_dir = input_path.parent / "lo-output"
        output_dir.mkdir()
        output = output_dir / f"{input_path.stem}.pdf"
        output.write_bytes(b"%PDF-mock")
        return ConversionResult(
            task_id=uuid4(),
            output_path=output,
            output_format=output_format,
            duration_ms=2,
            file_size=9,
        )

    async def validate_format(self, output_format):
        return output_format == OutputFormat.PDF


@pytest.mark.asyncio
async def test_word_pipeline_uses_registered_engine_and_persists_history(tmp_path) -> None:
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    word_engine = FakeWordEngine()
    service = ConversionService(
        FakeMarkdownEngine(),
        repository,
        ArtifactStorage(tmp_path),
        word_engine=word_engine,
    )
    options = {"quality": "standard", "export_bookmarks": True}

    task = await service.submit(
        b"word",
        "report.docx",
        OutputFormat.PDF,
        pipeline=ConversionPipeline.WORD_TO_PDF,
        options=options,
    )
    result = await service.execute(task.task_id)

    assert result.output_path.read_bytes() == b"%PDF-mock"
    assert word_engine.options == options
    persisted = repository.get_job(task.task_id)
    assert persisted is not None
    assert persisted.pipeline == ConversionPipeline.WORD_TO_PDF.value
    assert persisted.options_json == options
    restored = service.get_task(task.task_id)
    assert restored is not None
    assert restored.pipeline == ConversionPipeline.WORD_TO_PDF
    database.close()
