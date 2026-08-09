"""转换服务 — 编排上传、转换、进度、下载全流程"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.interfaces import ConversionEngine
from app.db.repository import ConversionRepository
from app.models import (
    ConversionPipeline,
    ConversionResult,
    ConversionStatus,
    ConversionTask,
    OutputFormat,
)
from app.services.artifact_storage import ArtifactStorage
from app.services.log import log
from app.utils.exceptions import FileTooLargeError

PROGRESS_PERSIST_STEP = 0.05


class ConversionService:
    """转换用例编排"""

    def __init__(  # noqa: PLR0913
        self,
        engine: ConversionEngine,
        repository: ConversionRepository,
        artifact_storage: ArtifactStorage,
        max_file_size: int = 50 * 1024 * 1024,
        max_concurrent: int = 4,
        word_engine: ConversionEngine | None = None,
        max_concurrent_word: int = 2,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._artifact_storage = artifact_storage
        self._max_file_size = max_file_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._word_semaphore = asyncio.Semaphore(max_concurrent_word)
        self._engines: dict[ConversionPipeline, ConversionEngine] = {
            ConversionPipeline.MARKDOWN: engine,
        }
        if word_engine is not None:
            self._engines[ConversionPipeline.WORD_TO_PDF] = word_engine
        self._tasks: dict[UUID, ConversionTask] = {}

    @property
    def max_file_size(self) -> int:
        """单个源文件允许的最大字节数。"""
        return self._max_file_size

    async def submit(  # noqa: PLR0913
        self,
        content: bytes,
        filename: str,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        options: dict | None = None,
        template_snapshot: dict | None = None,
        pipeline: ConversionPipeline = ConversionPipeline.MARKDOWN,
        *,
        output_file_name: str | None = None,
        convert_images: bool = True,
        convert_mermaid: bool = True,
    ) -> ConversionTask:
        """提交转换任务，返回任务对象"""
        if len(content) > self._max_file_size:
            raise FileTooLargeError(
                f"文件大小 {len(content)} 超过上限 {self._max_file_size} bytes",
            )

        task_id = uuid4()
        input_path, source_artifact = await self._artifact_storage.save_source(
            task_id,
            content,
            filename,
        )
        task = ConversionTask(
            task_id=task_id,
            input_path=input_path,
            pipeline=pipeline,
            output_format=output_format,
            output_file_name=output_file_name,
            template_slug=template_slug,
            convert_images=convert_images,
            convert_mermaid=convert_mermaid,
            extra_args=extra_args or [],
            options=options or {},
        )
        try:
            self._repository.create_job(
                task,
                filename,
                options or {},
                source_artifact,
                template_snapshot=template_snapshot,
            )
        except Exception:
            self._artifact_storage.delete_task(task_id)
            raise
        self._tasks[task.task_id] = task
        return task

    async def execute(self, task_id: UUID) -> ConversionResult:
        """后台执行转换"""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"任务不存在: {task_id}")
        assert task is not None  # type narrowing for pyrefly

        task.status = ConversionStatus.RUNNING
        task.progress = 0.0
        self._repository.mark_running(task_id)
        last_persisted_progress = 0.0
        working_path = self._artifact_storage.prepare_working_copy(
            task_id,
            task.input_path,
        )

        async def _on_progress(pct: float, msg: str = "") -> None:
            nonlocal last_persisted_progress
            task.progress = pct
            if pct >= 1.0 or pct - last_persisted_progress >= PROGRESS_PERSIST_STEP:
                self._repository.update_progress(task_id, pct)
                last_persisted_progress = pct
            log.debug(f"任务 {task_id}: {pct * 100:.0f}% - {msg}")

        try:
            engine = self._engines.get(task.pipeline)
            if engine is None:
                raise RuntimeError(f"转换引擎不可用: {task.pipeline.value}")  # noqa: TRY301
            semaphore = (
                self._word_semaphore
                if task.pipeline == ConversionPipeline.WORD_TO_PDF
                else self._semaphore
            )
            async with semaphore:
                pipeline_options = (
                    {"options": task.options}
                    if task.pipeline == ConversionPipeline.WORD_TO_PDF
                    else {}
                )
                result = await engine.convert(
                    input_path=working_path,
                    output_format=task.output_format,
                    extra_args=task.extra_args,
                    template_slug=task.template_slug,
                    convert_images=task.convert_images,
                    convert_mermaid=task.convert_mermaid,
                    on_progress=_on_progress,
                    **pipeline_options,
                )

            result.task_id = task_id
            result.output_path = self._artifact_storage.persist_output(
                task_id,
                result.output_path,
                task.output_file_name,
            )
            task.status = ConversionStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = datetime.now(UTC)
            task.output_path = result.output_path
            output_artifact = self._artifact_storage.describe(
                result.output_path,
                "output",
            )
            self._repository.mark_completed(
                task_id,
                duration_ms=result.duration_ms,
                output_artifact=output_artifact,
            )

            return result

        except Exception as e:
            task.status = ConversionStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(UTC)
            self._repository.mark_failed(task_id, str(e))
            log.error(f"任务 {task_id} 失败: {e}")
            raise
        finally:
            self._artifact_storage.cleanup_work(task_id)

    def get_task(self, task_id: UUID) -> ConversionTask | None:
        """查询任务"""
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        task = self._repository.get_task(task_id)
        if task is None:
            return None
        job = self._repository.get_job(task_id)
        if job is not None:
            artifacts = {artifact.kind: artifact for artifact in job.artifacts}
            if source := artifacts.get("source"):
                task.input_path = self._artifact_storage.resolve(source.relative_path)
            if output := artifacts.get("output"):
                task.output_path = self._artifact_storage.resolve(output.relative_path)
        return task

    def forget_task(self, task_id: UUID | str) -> None:
        """删除历史后同步清理运行时任务缓存。"""
        self._tasks.pop(UUID(str(task_id)), None)
