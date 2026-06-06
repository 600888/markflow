"""自定义异常"""

from __future__ import annotations

from typing import Any


class MarkflowError(Exception):
    """基础异常"""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        self.message = message
        self.detail = detail or {}
        super().__init__(self.message)


class ConversionError(MarkflowError):
    """转换过程失败"""


class UnsupportedFormatError(MarkflowError):
    """不支持的输出格式"""


class FileTooLargeError(MarkflowError):
    """文件超出大小限制"""


class PandocNotFoundError(MarkflowError):
    """Pandoc 未安装或不可用"""
