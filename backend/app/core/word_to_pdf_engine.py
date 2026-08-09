"""Word 转 PDF 多引擎实现。"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pypandoc

from app.core.browser_check import edge_manager
from app.core.engine import PandocEngine
from app.core.interfaces import ConversionEngine, ProgressCallback
from app.core.office_suite_check import (
    NativeOfficeManager,
    word_manager,
    wps_manager,
)
from app.core.pandoc_check import pandoc_manager
from app.models import ConversionResult, OutputFormat
from app.utils.config import AppSettings
from app.utils.exceptions import (
    ConversionError,
    UnsupportedFormatError,
    WordEngineUnavailableError,
)


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    """终止转换进程；Windows 下优先回收完整子进程树。"""
    if process.returncode is not None:
        return
    taskkill = shutil.which("taskkill") if os.name == "nt" else None
    if taskkill:
        killer = await asyncio.create_subprocess_exec(
            taskkill,
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=_windows_creation_flags(),
        )
        try:
            await asyncio.wait_for(killer.wait(), timeout=10)
        except TimeoutError:
            killer.kill()
            await killer.wait()
    if process.returncode is None:
        process.kill()
    await process.wait()


def _windows_creation_flags(*, new_process_group: bool = False) -> int:
    """返回不会创建控制台窗口的 Windows 子进程标志。"""
    if os.name != "nt":
        return 0
    flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    return flags


class NativeOfficeWordToPdfEngine(ConversionEngine):
    """通过 Word/WPS 的 COM 接口调用原生固定版式导出。"""

    def __init__(self, settings: AppSettings, manager: NativeOfficeManager) -> None:
        self.settings = settings
        self.manager = manager

    async def convert(  # noqa: PLR0913
        self,
        input_path: Path,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        *,
        convert_images: bool = True,
        convert_mermaid: bool = True,
        options: dict | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ConversionResult:
        """调用本机 Office 应用导出 PDF。"""
        del extra_args, template_slug, convert_images, convert_mermaid
        if output_format != OutputFormat.PDF:
            raise UnsupportedFormatError("Word 转换管线仅支持 PDF 输出")
        if input_path.suffix.lower() not in {".docx", ".doc"}:
            raise UnsupportedFormatError("仅支持 .docx 和 .doc 文件")
        prog_id = self.manager.find_prog_id()
        if not prog_id:
            raise WordEngineUnavailableError(
                f"未检测到可用的 {self.manager.name} 原生导出接口。"
            )

        output_dir = input_path.parent / f"{self.manager.engine_id}-output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{input_path.stem}.pdf"
        output_path.unlink(missing_ok=True)
        opts = options or {}
        optimize_for = 1 if opts.get("quality") == "screen" else 0
        bookmarks = 1 if opts.get("export_bookmarks", True) else 0
        script = self._build_script(
            prog_id,
            input_path.resolve(),  # noqa: ASYNC240
            output_path.resolve(),
            optimize_for,
            bookmarks,
        )
        shell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not shell:
            raise WordEngineUnavailableError("未找到 PowerShell，无法调用 Office 导出接口")

        if on_progress:
            await on_progress(0.2, f"正在启动 {self.manager.name}")
        started = time.monotonic()
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        process = await asyncio.create_subprocess_exec(
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=_windows_creation_flags(new_process_group=True),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.word_conversion_timeout,
            )
        except TimeoutError as exc:
            await _terminate_process(process)
            raise ConversionError(f"{self.manager.name} 导出 PDF 超时") from exc
        except asyncio.CancelledError:
            await _terminate_process(process)
            raise

        diagnostic = (stdout + stderr)[-65_536:].decode(errors="replace").strip()
        if process.returncode != 0:
            raise ConversionError(
                f"{self.manager.name} 导出 PDF 失败",
                detail={"diagnostic": diagnostic},
            )
        if on_progress:
            await on_progress(0.85, "正在校验 PDF 输出")
        _validate_pdf(output_path, f"{self.manager.name} 未生成有效的 PDF")
        return _conversion_result(output_path, started)

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """仅当原生 COM 接口可用时支持 PDF。"""
        return output_format == OutputFormat.PDF and self.manager.find_prog_id() is not None

    @staticmethod
    def _build_script(
        prog_id: str,
        input_path: Path,
        output_path: Path,
        optimize_for: int,
        bookmarks: int,
    ) -> str:
        def quote(value: object) -> str:
            return "'" + str(value).replace("'", "''") + "'"

        return "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$inputPath = {quote(input_path)}",
                f"$outputPath = {quote(output_path)}",
                "$app = $null",
                "$doc = $null",
                "try {",
                f"  $app = New-Object -ComObject {quote(prog_id)}",
                "  try { $app.Visible = $false } catch {}",
                "  try { $app.DisplayAlerts = 0 } catch {}",
                "  try { $app.AutomationSecurity = 3 } catch {}",
                "  $doc = $app.Documents.Open($inputPath, $false, $true)",
                "  try {",
                "    $doc.ExportAsFixedFormat($outputPath, 17, $false, "
                f"{optimize_for}, 0, 1, 1, 0, $true, $true, {bookmarks}, "
                "$true, $true, $false)",
                "  } catch {",
                "    $doc.SaveAs($outputPath, 17)",
                "  }",
                "} finally {",
                "  if ($null -ne $doc) { try { $doc.Close($false) } catch {} }",
                "  if ($null -ne $app) { try { $app.Quit() } catch {} }",
                "  if ($null -ne $doc) {",
                "    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)",
                "  }",
                "  if ($null -ne $app) {",
                "    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)",
                "  }",
                "  [GC]::Collect(); [GC]::WaitForPendingFinalizers()",
                "}",
            ]
        )


class PandocWordToPdfEngine(ConversionEngine):
    """使用 Pandoc 提取 DOCX 内容，再由 Edge 打印为 PDF。"""

    def __init__(self, settings: AppSettings, pandoc_engine: PandocEngine) -> None:
        self.settings = settings
        self.pandoc_engine = pandoc_engine

    async def convert(  # noqa: PLR0913
        self,
        input_path: Path,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        *,
        convert_images: bool = True,
        convert_mermaid: bool = True,
        options: dict | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ConversionResult:
        """把 DOCX 内容重排为 HTML 后打印成 PDF。"""
        del extra_args, template_slug, convert_images, convert_mermaid, options
        if output_format != OutputFormat.PDF:
            raise UnsupportedFormatError("Word 转换管线仅支持 PDF 输出")
        if input_path.suffix.lower() != ".docx":
            raise UnsupportedFormatError("Pandoc 导出仅支持 .docx 文件")
        if not pandoc_manager.is_installed() or not edge_manager.is_ready():
            raise WordEngineUnavailableError("Pandoc 与 Microsoft Edge 未同时就绪")

        html_path = input_path.with_name(f"{input_path.stem}.pandoc.html")
        output_dir = input_path.parent / "pandoc-output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{input_path.stem}.pdf"
        output_path.unlink(missing_ok=True)
        started = time.monotonic()
        if on_progress:
            await on_progress(0.2, "正在用 Pandoc 提取文档内容")
        pandoc = pypandoc.get_pandoc_path()
        command = [
            pandoc,
            str(input_path.resolve()),  # noqa: ASYNC240
            "--from=docx",
            "--to=html5",
            "--output",
            str(html_path.resolve()),
            "--standalone",
            "--embed-resources",
            "--mathml",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=_windows_creation_flags(new_process_group=True),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.settings.word_conversion_timeout,
                )
            except TimeoutError as exc:
                await _terminate_process(process)
                raise ConversionError("Pandoc 提取 Word 内容超时") from exc
            except asyncio.CancelledError:
                await _terminate_process(process)
                raise
            if process.returncode != 0:
                diagnostic = (stdout + stderr)[-65_536:].decode(errors="replace").strip()
                raise ConversionError(
                    f"Pandoc 提取 Word 内容失败（返回 {process.returncode}）",
                    detail={"diagnostic": diagnostic},
                )
            if on_progress:
                await on_progress(0.7, "正在用 Edge 生成 PDF")
            await self.pandoc_engine._render_html_to_pdf(html_path, output_path)  # noqa: SLF001
        finally:
            html_path.unlink(missing_ok=True)
        _validate_pdf(output_path, "Pandoc 未生成有效的 PDF")
        return _conversion_result(output_path, started)

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """Pandoc 和 Edge 均可用时支持 PDF。"""
        return (
            output_format == OutputFormat.PDF
            and pandoc_manager.is_installed()
            and edge_manager.is_ready()
        )


class WordToPdfEngineRegistry(ConversionEngine):
    """集中提供引擎状态，并按任务选项把转换分派给具体实现。"""

    ENGINE_ORDER = ("pandoc", "wps", "microsoft-word")
    PREFERRED_ENGINE = "microsoft-word"

    def __init__(
        self,
        settings: AppSettings,
        pandoc_engine: PandocEngine,
    ) -> None:
        self.settings = settings
        self.engines: dict[str, ConversionEngine] = {
            "pandoc": PandocWordToPdfEngine(settings, pandoc_engine),
            "wps": NativeOfficeWordToPdfEngine(settings, wps_manager),
            "microsoft-word": NativeOfficeWordToPdfEngine(settings, word_manager),
        }

    def get_info(self, *, refresh: bool = False) -> dict[str, Any]:
        """返回全部引擎状态及默认选择。"""
        engines = [
            self.get_engine_info(engine_id, refresh=refresh)
            for engine_id in self.ENGINE_ORDER
        ]
        default = next(item for item in engines if item["id"] == self.PREFERRED_ENGINE)
        return {
            "available": any(item["available"] for item in engines),
            "engine": default["id"],
            "version": default["version"],
            "executable": default["executable"],
            "supported_inputs": default["supported_inputs"],
            "diagnostic": default["diagnostic"],
            "default_engine": default["id"],
            "engines": engines,
        }

    def get_engine_info(self, engine_id: str, *, refresh: bool = False) -> dict[str, Any]:
        """返回指定引擎状态。"""
        if engine_id == "wps":
            return wps_manager.get_info(refresh=refresh)
        if engine_id == "microsoft-word":
            return word_manager.get_info(refresh=refresh)
        if engine_id == "pandoc":
            available = pandoc_manager.is_installed(force=refresh) and edge_manager.is_ready()
            try:
                executable = pypandoc.get_pandoc_path() if available else ""
            except OSError:
                executable = ""
                available = False
            return {
                "id": "pandoc",
                "name": "Pandoc",
                "available": available,
                "version": str(pandoc_manager.get_info().get("version", "")),
                "executable": executable,
                "supported_inputs": ["docx"],
                "diagnostic": (
                    "Pandoc 内容重排导出已就绪（版式可能变化）"
                    if available
                    else "需要同时安装 Pandoc 并提供 Microsoft Edge"
                ),
                "fidelity": "reflow",
            }
        raise WordEngineUnavailableError(f"未知的 Word 转 PDF 引擎: {engine_id}")

    def resolve_engine_id(self, engine_id: str = "", *, refresh: bool = False) -> str:
        """解析显式选择；未指定时使用当前可用的默认引擎。"""
        if engine_id:
            return engine_id
        return str(self.get_info(refresh=refresh)["default_engine"])

    async def convert(  # noqa: PLR0913
        self,
        input_path: Path,
        output_format: OutputFormat,
        extra_args: list[str] | None = None,
        template_slug: str | None = None,
        *,
        convert_images: bool = True,
        convert_mermaid: bool = True,
        options: dict | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ConversionResult:
        """按 options.engine 分派到具体导出实现。"""
        selected = self.resolve_engine_id(str((options or {}).get("engine", "")))
        engine = self.engines.get(selected)
        if engine is None:
            raise WordEngineUnavailableError(f"不支持的 Word 转 PDF 引擎: {selected}")
        info = self.get_engine_info(selected, refresh=True)
        if not info["available"]:
            raise WordEngineUnavailableError(str(info["diagnostic"]))
        suffix = input_path.suffix.lower().lstrip(".")
        if suffix not in info["supported_inputs"]:
            raise UnsupportedFormatError(f"{info['name']} 不支持 .{suffix} 文件")
        return await engine.convert(
            input_path,
            output_format,
            extra_args,
            template_slug,
            convert_images=convert_images,
            convert_mermaid=convert_mermaid,
            options=options,
            on_progress=on_progress,
        )

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """任一引擎可用时支持 PDF。"""
        return output_format == OutputFormat.PDF and bool(self.get_info()["available"])


def _validate_pdf(path: Path, message: str) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise ConversionError(message)
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ConversionError(message)


def _conversion_result(path: Path, started: float) -> ConversionResult:
    return ConversionResult(
        task_id=uuid4(),
        output_path=path,
        output_format=OutputFormat.PDF,
        duration_ms=round((time.monotonic() - started) * 1000),
        file_size=path.stat().st_size,
    )
