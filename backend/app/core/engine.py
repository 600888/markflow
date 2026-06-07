"""Pandoc 转换引擎实现"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from uuid import UUID

import pypandoc

from app.core.interfaces import ConversionEngine, ProgressCallback
from app.core.log import log
from app.core.template_manager import TemplateManager
from app.models import ConversionResult, OutputFormat
from app.models.templates import ConversionOptions
from app.utils.config import AppSettings
from app.utils.exceptions import ConversionError, PandocNotFoundError, UnsupportedFormatError


class PandocEngine(ConversionEngine):
    """基于 Pandoc 的转换引擎（适配器模式）"""

    # OutputFormat → Pandoc -t 格式名
    FORMAT_MAP: dict[OutputFormat, str] = {
        OutputFormat.DOCX: "docx",
        OutputFormat.PDF: "pdf",
        OutputFormat.HTML: "html",
        OutputFormat.EPUB: "epub",
        OutputFormat.LATEX: "latex",
        OutputFormat.MARKDOWN: "gfm",
        OutputFormat.ODT: "odt",
        OutputFormat.RTF: "rtf",
    }

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self._template_mgr = TemplateManager()
        self._validate_pandoc()

    def _validate_pandoc(self) -> None:
        """启动时验证 Pandoc 是否可用"""
        try:
            path = pypandoc.get_pandoc_path()
            log.info(f"Pandoc 路径: {path}")
        except OSError as e:
            raise PandocNotFoundError(
                "Pandoc 未安装或不在 PATH 中，请先安装 Pandoc",
                detail={"error": str(e)},
            ) from e

    async def convert(
        self,
        input_path: Path,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ConversionResult:
        """执行 Pandoc 转换"""
        pandoc_target = self.FORMAT_MAP.get(output_format)
        if pandoc_target is None:
            raise UnsupportedFormatError(f"不支持的格式: {output_format.value}")

        if on_progress:
            await on_progress(0.05, "准备转换...")

        output_path = input_path.with_suffix(f".{output_format.value}")
        args = extra_args or []

        # 组装模版参数
        if template_slug:
            template_args = self._template_mgr.build_extra_args(
                ConversionOptions(template_slug=template_slug),
            )
            args = template_args + args
            log.info(f"使用模版: {template_slug}, 参数: {template_args}")

        start = time.monotonic()

        if on_progress:
            await on_progress(0.1, "正在转换...")

        try:
            loop = asyncio.get_running_loop()

            def _convert() -> str:
                return pypandoc.convert_file(
                    source_file=str(input_path),
                    to=pandoc_target,
                    format="markdown",
                    outputfile=str(output_path),
                    extra_args=args,
                )

            if self.settings.pandoc_timeout > 0:
                # 带超时的异步执行
                await asyncio.wait_for(
                    loop.run_in_executor(None, _convert),
                    timeout=self.settings.pandoc_timeout,
                )
            else:
                await loop.run_in_executor(None, _convert)

            if on_progress:
                await on_progress(1.0, "转换完成")

            duration = int((time.monotonic() - start) * 1000)
            file_size = output_path.stat().st_size

            log.info(
                f"转换完成: {input_path.name} → {output_format.value}, "
                f"耗时 {duration}ms, 大小 {file_size} bytes"
            )

            return ConversionResult(
                task_id=UUID("00000000-0000-0000-0000-000000000000"),
                output_path=output_path,
                output_format=output_format,
                duration_ms=duration,
                file_size=file_size,
            )

        except TimeoutError:
            raise ConversionError(
                f"转换超时（{self.settings.pandoc_timeout}s）",
                detail={"input": str(input_path), "format": output_format.value},
            ) from None
        except Exception as e:
            raise ConversionError(
                "Pandoc 转换失败",
                detail={
                    "input": str(input_path),
                    "format": output_format.value,
                    "error": str(e),
                },
            ) from e

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """校验格式是否支持"""
        return output_format in self.FORMAT_MAP
