from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.interfaces import ConversionEngine
from app.db import ConversionRepository, Database
from app.models import ConversionResult, ConversionStatus, ConversionTask, OutputFormat
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService


class FakeEngine(ConversionEngine):
    async def convert(  # noqa: PLR0913
        self,
        input_path,
        output_format,
        extra_args=None,
        template_slug=None,
        *,
        convert_images=True,
        convert_mermaid=True,
        on_progress=None,
    ):
        if on_progress:
            await on_progress(0.5, "half")
        output_path = input_path.with_suffix(f".{output_format.value}")
        output_path.write_bytes(b"generated")
        return ConversionResult(
            task_id=uuid4(),
            output_path=output_path,
            output_format=output_format,
            duration_ms=20,
            file_size=len(b"generated"),
        )

    async def validate_format(self, output_format):
        return True


@pytest.mark.asyncio
async def test_conversion_history_lifecycle(tmp_path):
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    storage = ArtifactStorage(tmp_path)
    task_id = uuid4()

    source_path, source_artifact = await storage.save_source(
        task_id,
        b"# persisted",
        "../report.md",
    )
    task = ConversionTask(
        task_id=task_id,
        input_path=source_path,
        output_format=OutputFormat.DOCX,
        template_slug="academic",
    )
    repository.create_job(task, "report.md", {"toc": True}, source_artifact)

    repository.mark_running(task_id)
    repository.update_progress(task_id, 0.5)
    output_path = source_path.with_suffix(".docx")
    output_path.write_bytes(b"docx-content")
    repository.mark_completed(
        task_id,
        duration_ms=125,
        output_artifact=storage.describe(output_path, "output"),
    )

    persisted = repository.get_job(task_id)
    assert persisted is not None
    assert persisted.status == ConversionStatus.COMPLETED.value
    assert persisted.options_json == {"toc": True}
    assert {artifact.kind for artifact in persisted.artifacts} == {"source", "output"}

    jobs, total, output_bytes = repository.list_history(search="report")
    assert total == 1
    assert len(jobs) == 1
    assert output_bytes == len(b"docx-content")

    ids = repository.clear_history()
    assert ids == [str(task_id)]
    storage.delete_task(task_id)
    assert repository.get_job(task_id) is None
    assert not source_path.parent.exists()
    database.close()


def test_running_jobs_are_marked_interrupted(tmp_path):
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    task_id = uuid4()
    task = ConversionTask(
        task_id=task_id,
        input_path=tmp_path / "source.md",
        output_format=OutputFormat.PDF,
        created_at=datetime.now(UTC),
    )
    source_artifact = {
        "kind": "source",
        "file_name": "source.md",
        "content_type": "text/markdown",
        "size_bytes": 1,
        "sha256": "0" * 64,
        "relative_path": f"{task_id}/source.md",
        "created_at": datetime.now(UTC),
    }
    repository.create_job(task, "source.md", {}, source_artifact)

    assert repository.mark_interrupted() == 1
    persisted = repository.get_job(task_id)
    assert persisted is not None
    assert persisted.status == "interrupted"
    assert persisted.error_message
    database.close()


@pytest.mark.asyncio
async def test_conversion_service_survives_service_restart(tmp_path):
    database = Database(tmp_path)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    storage = ArtifactStorage(tmp_path)
    service = ConversionService(FakeEngine(), repository, storage)

    task = await service.submit(
        b"# hello",
        "hello.md",
        OutputFormat.MARKDOWN,
        options={"toc": False},
    )
    result = await service.execute(task.task_id)
    assert result.output_path.read_bytes() == b"generated"

    restarted_service = ConversionService(FakeEngine(), repository, storage)
    restored = restarted_service.get_task(task.task_id)
    assert restored is not None
    assert restored.status == ConversionStatus.COMPLETED
    assert restored.input_path.read_bytes() == b"# hello"
    assert restored.output_path is not None
    assert restored.output_path.read_bytes() == b"generated"
    database.close()
