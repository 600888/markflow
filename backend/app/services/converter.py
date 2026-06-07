"""转换服务 — 编排上传、转换、进度、下载全流程"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.interfaces import ConversionEngine, FileManager
from app.models import ConversionResult, ConversionStatus, ConversionTask, OutputFormat
from app.services.log import log
from app.utils.exceptions import FileTooLargeError


class ConversionService:
    """转换用例编排"""

    def __init__(
        self,
        engine: ConversionEngine,
        file_manager: FileManager,
        max_file_size: int = 50 * 1024 * 1024,
        max_concurrent: int = 4,
    ) -> None:
        self._engine = engine
        self._file_manager = file_manager
        self._max_file_size = max_file_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[UUID, ConversionTask] = {}

    async def submit(
        self,
        content: bytes,
        filename: str,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
    ) -> ConversionTask:
        """提交转换任务，返回任务对象"""
        if len(content) > self._max_file_size:
            raise FileTooLargeError(
                f"文件大小 {len(content)} 超过上限 {self._max_file_size} bytes",
            )

        input_path = await self._file_manager.save_upload(content, filename)
        task = ConversionTask(
            task_id=uuid4(),
            input_path=input_path,
            output_format=output_format,
            template_slug=template_slug,
            extra_args=extra_args or [],
        )
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

        async def _on_progress(pct: float, msg: str = "") -> None:
            task.progress = pct
            log.debug(f"任务 {task_id}: {pct * 100:.0f}% - {msg}")

        try:
            async with self._semaphore:
                result = await self._engine.convert(
                    input_path=task.input_path,
                    output_format=task.output_format,
                    extra_args=task.extra_args,
                    template_slug=task.template_slug,
                    on_progress=_on_progress,
                )

            result.task_id = task_id
            task.status = ConversionStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = datetime.now(UTC)
            task.output_path = result.output_path

            return result

        except Exception as e:
            task.status = ConversionStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(UTC)
            log.error(f"任务 {task_id} 失败: {e}")
            raise
        finally:
            await self._file_manager.cleanup(task.input_path)

    def get_task(self, task_id: UUID) -> ConversionTask | None:
        """查询任务"""
        return self._tasks.get(task_id)
