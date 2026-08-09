"""转换源文件和产物的持久化文件存储。"""

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import aiofiles


class ArtifactStorage:
    """管理 data/artifacts 下的任务文件。"""

    def __init__(self, data_dir: Path) -> None:
        self.root = (data_dir / "artifacts").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_source(self, task_id: UUID, content: bytes, filename: str) -> tuple[Path, dict]:
        """保存任务源文件并返回文件索引数据。"""
        task_dir = self._task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=False)
        source_dir = task_dir / "source"
        source_dir.mkdir()
        safe_name = _safe_filename(filename)
        path = (source_dir / safe_name).resolve()
        self._ensure_contained(path)
        async with aiofiles.open(path, "wb") as stream:
            await stream.write(content)
        return path, self.describe(path, "source")

    def prepare_working_copy(self, task_id: UUID, source_path: Path) -> Path:
        """创建转换工作副本，避免转换覆盖持久化源文件。"""
        work_dir = self._task_dir(task_id) / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        working_path = (work_dir / source_path.name).resolve()
        self._ensure_contained(working_path)
        shutil.copy2(source_path, working_path)
        return working_path

    def persist_output(
        self,
        task_id: UUID,
        generated_path: Path,
        output_file_name: str | None = None,
    ) -> Path:
        """把转换结果复制到稳定的输出目录。"""
        output_dir = self._task_dir(task_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        target_name = generated_path.name
        if output_file_name and output_file_name.strip():
            safe_name = _safe_filename(output_file_name.strip())
            known_suffixes = {".docx", ".pdf", ".html", ".epub", ".tex", ".md", ".odt", ".rtf"}
            safe_path = Path(safe_name)
            base_name = safe_path.stem if safe_path.suffix.lower() in known_suffixes else safe_name
            target_name = f"{base_name}{generated_path.suffix}"
        output_path = (output_dir / target_name).resolve()
        self._ensure_contained(output_path)
        shutil.copy2(generated_path, output_path)
        return output_path

    def cleanup_work(self, task_id: UUID) -> None:
        """清理不需要持久化的转换工作目录。"""
        work_dir = self._task_dir(task_id) / "work"
        if work_dir.exists():
            shutil.rmtree(work_dir)

    def describe(self, path: Path, kind: str) -> dict:
        """生成可写入数据库的文件索引。"""
        resolved = path.resolve()
        self._ensure_contained(resolved)
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        return {
            "kind": kind,
            "file_name": resolved.name,
            "content_type": content_type,
            "size_bytes": resolved.stat().st_size,
            "sha256": digest.hexdigest(),
            "relative_path": resolved.relative_to(self.root).as_posix(),
            "created_at": datetime.now(UTC),
        }

    def resolve(self, relative_path: str) -> Path:
        """安全解析数据库中的相对文件路径。"""
        path = (self.root / relative_path).resolve()
        self._ensure_contained(path)
        return path

    def delete_task(self, task_id: UUID | str) -> None:
        """删除任务的全部持久化文件。"""
        task_dir = self._task_dir(task_id)
        if task_dir.exists():
            shutil.rmtree(task_dir)

    def _task_dir(self, task_id: UUID | str) -> Path:
        path = (self.root / str(task_id)).resolve()
        self._ensure_contained(path)
        return path

    def _ensure_contained(self, path: Path) -> None:
        if path != self.root and self.root not in path.parents:
            raise ValueError("历史文件路径越界")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name or "document.md"
