"""转换历史仓储。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.db.models import ConversionArtifactEntity, ConversionJobEntity
from app.models import ConversionPipeline, ConversionStatus, ConversionTask, OutputFormat


class ConversionRepository:
    """封装转换任务和产物的数据库操作。"""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def create_job(
        self,
        task: ConversionTask,
        source_file_name: str,
        options: dict,
        source_artifact: dict,
        *,
        template_snapshot: dict | None = None,
    ) -> None:
        """创建任务及其源文件索引。"""
        now = datetime.now(UTC)
        entity = ConversionJobEntity(
            id=str(task.task_id),
            pipeline=task.pipeline.value,
            status=task.status.value,
            source_file_name=source_file_name,
            output_format=task.output_format.value,
            template_slug=task.template_slug,
            template_revision=(template_snapshot or {}).get("revision"),
            template_snapshot_json=template_snapshot,
            options_json=options,
            progress=task.progress,
            created_at=task.created_at,
            updated_at=now,
            artifacts=[ConversionArtifactEntity(job_id=str(task.task_id), **source_artifact)],
        )
        with self._session_factory.begin() as session:
            session.add(entity)

    def mark_running(self, task_id: UUID) -> None:
        """将任务标记为运行中。"""
        now = datetime.now(UTC)
        self._update(task_id, status=ConversionStatus.RUNNING.value, started_at=now, updated_at=now)

    def update_progress(self, task_id: UUID, progress: float) -> None:
        """持久化任务进度。"""
        self._update(task_id, progress=progress, updated_at=datetime.now(UTC))

    def mark_completed(
        self,
        task_id: UUID,
        *,
        duration_ms: int,
        output_artifact: dict,
    ) -> None:
        """完成任务并原子写入输出文件索引。"""
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            session.add(ConversionArtifactEntity(job_id=str(task_id), **output_artifact))
            session.execute(
                update(ConversionJobEntity)
                .where(ConversionJobEntity.id == str(task_id))
                .values(
                    status=ConversionStatus.COMPLETED.value,
                    progress=1.0,
                    duration_ms=duration_ms,
                    completed_at=now,
                    updated_at=now,
                )
            )

    def mark_failed(self, task_id: UUID, error_message: str) -> None:
        """记录任务失败状态。"""
        now = datetime.now(UTC)
        self._update(
            task_id,
            status=ConversionStatus.FAILED.value,
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )

    def mark_interrupted(self) -> int:
        """将上次异常退出遗留的任务标记为中断。"""
        now = datetime.now(UTC)
        with self._session_factory.begin() as session:
            result = session.execute(
                update(ConversionJobEntity)
                .where(
                    ConversionJobEntity.status.in_(
                        [ConversionStatus.PENDING.value, ConversionStatus.RUNNING.value]
                    )
                )
                .values(
                    status="interrupted",
                    error_message="应用退出导致转换中断",
                    completed_at=now,
                    updated_at=now,
                )
            )
            return result.rowcount

    def get_job(self, task_id: UUID | str) -> ConversionJobEntity | None:
        """按任务 ID 查询完整任务。"""
        with self._session_factory() as session:
            return session.scalar(
                select(ConversionJobEntity)
                .options(selectinload(ConversionJobEntity.artifacts))
                .where(ConversionJobEntity.id == str(task_id))
            )

    def get_task(self, task_id: UUID) -> ConversionTask | None:
        """将持久化任务转换为领域模型。"""
        job = self.get_job(task_id)
        if job is None:
            return None
        artifacts = {artifact.kind: artifact for artifact in job.artifacts}
        source = artifacts.get("source")
        output = artifacts.get("output")
        return ConversionTask(
            task_id=UUID(job.id),
            input_path=Path(source.relative_path) if source else Path(),
            pipeline=ConversionPipeline(job.pipeline),
            output_format=OutputFormat(job.output_format),
            template_slug=job.template_slug,
            status=ConversionStatus(job.status)
            if job.status != "interrupted"
            else ConversionStatus.FAILED,
            progress=job.progress,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error=job.error_message,
            options=job.options_json,
            output_path=Path(output.relative_path) if output else None,
        )

    def list_history(
        self,
        *,
        search: str = "",
        days: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ConversionJobEntity], int, int]:
        """分页查询成功历史及总输出大小。"""
        filters = [ConversionJobEntity.status == ConversionStatus.COMPLETED.value]
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    ConversionJobEntity.source_file_name.ilike(pattern),
                    ConversionArtifactEntity.file_name.ilike(pattern),
                )
            )
        if days is not None:
            filters.append(
                ConversionJobEntity.created_at >= datetime.now(UTC) - timedelta(days=days)
            )

        stmt = (
            select(ConversionJobEntity)
            .outerjoin(ConversionArtifactEntity)
            .options(selectinload(ConversionJobEntity.artifacts))
            .where(*filters)
            .distinct()
        )
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
            jobs = list(
                session.scalars(
                    stmt.order_by(ConversionJobEntity.created_at.desc()).limit(limit).offset(offset)
                ).unique()
            )
            output_bytes = (
                session.scalar(
                    select(func.coalesce(func.sum(ConversionArtifactEntity.size_bytes), 0))
                    .join(ConversionJobEntity)
                    .where(
                        ConversionArtifactEntity.kind == "output",
                        ConversionJobEntity.status == ConversionStatus.COMPLETED.value,
                    )
                )
                or 0
            )
        return jobs, total, int(output_bytes)

    def delete_job(self, task_id: UUID | str) -> bool:
        """删除一个任务及其文件索引。"""
        with self._session_factory.begin() as session:
            result = session.execute(
                delete(ConversionJobEntity).where(ConversionJobEntity.id == str(task_id))
            )
            return result.rowcount > 0

    def clear_history(self) -> list[str]:
        """删除全部成功历史并返回任务 ID。"""
        with self._session_factory.begin() as session:
            ids = list(
                session.scalars(
                    select(ConversionJobEntity.id).where(
                        ConversionJobEntity.status == ConversionStatus.COMPLETED.value
                    )
                )
            )
            session.execute(
                delete(ConversionJobEntity).where(
                    ConversionJobEntity.status == ConversionStatus.COMPLETED.value
                )
            )
            return ids

    def _update(self, task_id: UUID, **values: object) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(ConversionJobEntity)
                .where(ConversionJobEntity.id == str(task_id))
                .values(**values)
            )
