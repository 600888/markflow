"""抽象接口定义"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.models.models import ConversionResult, OutputFormat

# 进度回调类型：接收进度值(0~1)和消息
ProgressCallback = Callable[[float, str], Awaitable[None]]


class ConversionEngine(ABC):
    """转换引擎接口"""

    @abstractmethod
    async def convert(
        self,
        input_path: Path,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ConversionResult:
        """
        执行格式转换。

        Args:
            input_path: 输入文件路径
            output_format: 目标输出格式
            extra_args: 额外的 Pandoc 参数
            template_slug: 模版标识，用于 --reference-doc
            on_progress: 进度回调

        """
        ...

    @abstractmethod
    async def validate_format(self, output_format: OutputFormat) -> bool:
        """检查是否支持目标格式"""
        ...


class FileManager(ABC):
    """文件管理接口"""

    @abstractmethod
    async def save_upload(self, content: bytes, filename: str) -> Path:
        """保存上传文件，返回本地路径"""
        ...

    @abstractmethod
    async def cleanup(self, path: Path) -> None:
        """删除临时文件"""
        ...

    @abstractmethod
    def get_output_path(self, base_name: str, fmt: OutputFormat) -> Path:
        """生成输出文件路径"""
        ...
