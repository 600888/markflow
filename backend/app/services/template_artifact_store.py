"""自定义模板 reference.docx 派生文件存储。"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from uuid import UUID, uuid4


class TemplateArtifactStore:
    """在用户数据目录中按内容哈希原子发布模板文件。"""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir.resolve()
        self.root = (self.data_dir / "template-artifacts").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, template_id: str, content: bytes) -> tuple[str, str]:
        """保存 DOCX 内容，返回相对 DATA_DIR 的路径和 SHA-256。"""
        safe_id = str(UUID(template_id))
        digest = hashlib.sha256(content).hexdigest()
        template_dir = (self.root / safe_id).resolve()
        self._ensure_contained(template_dir)
        template_dir.mkdir(parents=True, exist_ok=True)

        destination = (template_dir / f"{digest}.docx").resolve()
        self._ensure_contained(destination)
        if not destination.exists():
            temporary = (template_dir / f".{digest}.{uuid4().hex}.tmp").resolve()
            self._ensure_contained(temporary)
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)

        relative_path = destination.relative_to(self.data_dir).as_posix()
        return relative_path, digest

    def resolve(self, relative_path: str) -> Path:
        """安全解析数据库保存的相对路径。"""
        path = (self.data_dir / relative_path).resolve()
        self._ensure_contained(path)
        return path

    def is_valid(self, relative_path: str | None, expected_sha256: str | None) -> bool:
        """校验派生文件是否存在且内容哈希匹配。"""
        if not relative_path or not expected_sha256:
            return False
        try:
            path = self.resolve(relative_path)
        except ValueError:
            return False
        if not path.is_file():
            return False
        return self.sha256(path) == expected_sha256

    def cleanup(
        self,
        referenced_paths: set[str],
        *,
        temporary_max_age_seconds: int = 24 * 60 * 60,
        orphan_max_age_seconds: int = 7 * 24 * 60 * 60,
        now: float | None = None,
    ) -> dict[str, int]:
        """延迟删除临时文件和不再被数据库引用的 DOCX。"""
        current_time = time.time() if now is None else now
        normalized_references = {Path(item).as_posix() for item in referenced_paths}
        removed_temporary = 0
        removed_orphans = 0

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            age = max(0, current_time - path.stat().st_mtime)
            if path.name.endswith(".tmp"):
                if age >= temporary_max_age_seconds:
                    path.unlink(missing_ok=True)
                    removed_temporary += 1
                continue
            if path.suffix.lower() != ".docx" or age < orphan_max_age_seconds:
                continue
            relative_path = path.resolve().relative_to(self.data_dir).as_posix()
            if relative_path not in normalized_references:
                path.unlink(missing_ok=True)
                removed_orphans += 1

        removed_directories = 0
        directories = sorted(
            (path for path in self.root.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
                removed_directories += 1
            except OSError:
                continue
        return {
            "temporary_files": removed_temporary,
            "orphan_files": removed_orphans,
            "directories": removed_directories,
        }

    @staticmethod
    def sha256(path: Path) -> str:
        """计算文件 SHA-256。"""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _ensure_contained(self, path: Path) -> None:
        if path != self.root and self.root not in path.parents:
            raise ValueError("模板派生文件路径越界")
