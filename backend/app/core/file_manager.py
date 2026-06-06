"""临时文件管理"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import aiofiles

from app.core.interfaces import FileManager
from app.models import OutputFormat
from app.utils.config import AppSettings

logger = logging.getLogger(__name__)


class TempFileManager(FileManager):
    """本地临时文件管理"""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.settings.temp_dir.mkdir(parents=True, exist_ok=True)
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, content: bytes, filename: str) -> Path:
        """保存上传文件到临时目录"""
        safe_name = _safe_filename(filename)
        file_path = (self.settings.temp_dir / safe_name).resolve()

        # 防止路径遍历：确保文件仍在 temp_dir 下
        if not str(file_path).startswith(str(self.settings.temp_dir.resolve())):
            raise ValueError(f"非法文件名: {filename}")

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        logger.debug("文件已保存: %s (%d bytes)", file_path, len(content))
        return file_path

    async def cleanup(self, path: Path) -> None:
        """删除临时文件"""
        try:
            if path.exists():
                path.unlink()
                logger.debug("文件已清理: %s", path)
        except OSError as e:
            logger.warning("清理文件失败: %s - %s", path, e)

    def get_output_path(self, base_name: str, fmt: OutputFormat) -> Path:
        """生成输出路径"""
        safe = Path(base_name).stem
        return (self.settings.output_dir / f"{safe}.{fmt.value}").resolve()


def _safe_filename(filename: str) -> str:
    """过滤不可用于文件名的字符"""
    name = Path(filename).name  # 去除路径部分
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    return name or "untitled"
