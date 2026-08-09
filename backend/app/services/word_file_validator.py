"""Word 上传文件的轻量结构与资源消耗校验。"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.utils.exceptions import InvalidWordFileError

OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
DOCX_REQUIRED_ENTRIES = {"[Content_Types].xml", "word/document.xml"}


class WordFileValidator:
    """拒绝伪装文件、损坏 OOXML 和明显的 ZIP bomb。"""

    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        max_uncompressed_size: int = 500 * 1024 * 1024,
        max_compression_ratio: float = 100.0,
    ) -> None:
        self.max_entries = max_entries
        self.max_uncompressed_size = max_uncompressed_size
        self.max_compression_ratio = max_compression_ratio

    def validate(self, content: bytes, filename: str) -> str:
        """校验并返回标准化的小写扩展名。"""
        suffix = Path(filename).suffix.lower()
        if suffix not in {".docx", ".doc"}:
            raise InvalidWordFileError("仅支持 .docx 和 .doc 文件")
        if not content:
            raise InvalidWordFileError("Word 文件为空")

        if suffix == ".docx":
            self._validate_docx(content)
        elif not content.startswith(OLE_SIGNATURE):
            raise InvalidWordFileError(".doc 文件结构无效或文件已损坏")
        return suffix

    def _validate_docx(self, content: bytes) -> None:
        if not content.startswith(b"PK"):
            raise InvalidWordFileError(".docx 文件结构无效或文件已损坏")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > self.max_entries:
                    raise InvalidWordFileError(".docx 文件包含过多内部条目")
                names = {entry.filename.replace("\\", "/") for entry in entries}
                if not DOCX_REQUIRED_ENTRIES.issubset(names):
                    raise InvalidWordFileError(".docx 文件缺少必要的文档结构")

                total_size = 0
                for entry in entries:
                    total_size += entry.file_size
                    if total_size > self.max_uncompressed_size:
                        raise InvalidWordFileError(".docx 解压后内容超过安全限制")
                    if entry.file_size == 0:
                        continue
                    if entry.compress_size == 0:
                        raise InvalidWordFileError(".docx 包含异常压缩条目")
                    if entry.file_size / entry.compress_size > self.max_compression_ratio:
                        raise InvalidWordFileError(".docx 包含异常高压缩比条目")
        except zipfile.BadZipFile as exc:
            raise InvalidWordFileError(".docx 文件结构无效或文件已损坏") from exc
