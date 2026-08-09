"""基于 LibreOffice Writer 的 Word 转 PDF 引擎。"""

from __future__ import annotations

import asyncio
import base64
import json
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
from app.core.libreoffice_check import LibreOfficeManager
from app.core.office_suite_check import NativeOfficeManager, word_manager, wps_manager
from app.core.pandoc_check import pandoc_manager
from app.models import ConversionResult, OutputFormat
from app.utils.config import AppSettings
from app.utils.exceptions import (
    ConversionError,
    UnsupportedFormatError,
    WordEngineUnavailableError,
)

QUALITY_PRESETS: dict[str, dict[str, int | bool]] = {
    "screen": {
        "Quality": 75,
        "ReduceImageResolution": True,
        "MaxImageResolution": 150,
    },
    "standard": {
        "Quality": 90,
        "ReduceImageResolution": True,
        "MaxImageResolution": 300,
    },
    "print": {
        "Quality": 100,
        "ReduceImageResolution": False,
    },
}


class LibreOfficeWordToPdfEngine(ConversionEngine):
    """在独立用户 profile 中调用 soffice 完成转换。"""

    def __init__(
        self,
        settings: AppSettings | None = None,
        manager: LibreOfficeManager | None = None,
    ) -> None:
        self.settings = settings or AppSettings()
        self.manager = manager or LibreOfficeManager(self.settings)

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
        """把一个工作目录中的 Word 文件转换成已校验的 PDF。"""
        del extra_args, template_slug, convert_images, convert_mermaid
        if output_format != OutputFormat.PDF:
            raise UnsupportedFormatError("Word 转换管线仅支持 PDF 输出")
        executable = self.manager.find_executable()
        if executable is None or not self.manager.get_version():
            raise WordEngineUnavailableError(
                "未检测到 LibreOffice，请安装 LibreOffice 后重试。"
            )
        if input_path.suffix.lower() not in {".docx", ".doc"}:
            raise UnsupportedFormatError("仅支持 .docx 和 .doc 文件")

        if on_progress:
            await on_progress(0.15, "正在准备转换环境")
        work_dir = input_path.parent
        output_dir = work_dir / "lo-output"
        profile_dir = work_dir / "lo-profile"
        output_dir.mkdir(parents=True, exist_ok=True)
        profile_dir.mkdir(parents=True, exist_ok=True)
        expected_output = output_dir / f"{input_path.stem}.pdf"
        expected_output.unlink(missing_ok=True)

        filter_spec = self._build_filter_spec(options or {})
        command = [
            str(executable),
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            "--norestore",
            "--convert-to",
            filter_spec,
            "--outdir",
            str(output_dir.resolve()),
            str(input_path.resolve()),  # noqa: ASYNC240
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        if on_progress:
            await on_progress(0.25, "正在启动 PDF 转换引擎")
        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.word_conversion_timeout,
            )
        except TimeoutError as exc:
            await self._terminate_process(process)
            raise ConversionError("Word 转 PDF 超时，请简化文档或稍后重试") from exc
        except asyncio.CancelledError:
            await self._terminate_process(process)
            raise

        diagnostic = (stdout + stderr)[-65_536:].decode(errors="replace").strip()
        if process.returncode != 0:
            raise ConversionError(
                f"Word 转 PDF 失败（LibreOffice 返回 {process.returncode}）",
                detail={"diagnostic": diagnostic},
            )
        if on_progress:
            await on_progress(0.8, "正在校验 PDF 输出")
        if not expected_output.is_file() or expected_output.stat().st_size == 0:
            raise ConversionError(
                "LibreOffice 未生成 PDF，文档可能已损坏或受密码保护",
                detail={"diagnostic": diagnostic},
            )
        with expected_output.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ConversionError("生成的 PDF 文件无效")

        duration_ms = round((time.monotonic() - started) * 1000)
        return ConversionResult(
            task_id=uuid4(),
            output_path=expected_output,
            output_format=OutputFormat.PDF,
            duration_ms=duration_ms,
            file_size=expected_output.stat().st_size,
        )

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """仅在 LibreOffice 可用时接受 PDF 输出。"""
        return output_format == OutputFormat.PDF and self.manager.is_available()

    @staticmethod
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
            )
            try:
                await asyncio.wait_for(killer.wait(), timeout=10)
            except TimeoutError:
                killer.kill()
                await killer.wait()
        if process.returncode is None:
            process.kill()
        await process.wait()

    @staticmethod
    def _build_filter_spec(options: dict) -> str:
        quality = str(options.get("quality", "standard"))
        preset = QUALITY_PRESETS.get(quality)
        if preset is None:
            raise ConversionError(f"不支持的 PDF 质量选项: {quality}")

        properties: dict[str, dict[str, str]] = {}
        for name, value in preset.items():
            value_type = "boolean" if isinstance(value, bool) else "long"
            serialized = str(value).lower() if isinstance(value, bool) else str(value)
            properties[name] = {"type": value_type, "value": serialized}
        properties["ExportBookmarks"] = {
            "type": "boolean",
            "value": str(bool(options.get("export_bookmarks", True))).lower(),
        }
        properties["EmbedStandardFonts"] = {
            "type": "boolean",
            "value": str(bool(options.get("embed_standard_fonts", True))).lower(),
        }
        properties["UseTaggedPDF"] = {"type": "boolean", "value": "true"}
        payload = json.dumps(properties, ensure_ascii=False, separators=(",", ":"))
        return f"pdf:writer_pdf_Export:{payload}"


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
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = await asyncio.create_subprocess_exec(
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=creationflags,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.settings.word_conversion_timeout,
            )
        except TimeoutError as exc:
            await LibreOfficeWordToPdfEngine._terminate_process(process)  # noqa: SLF001
            raise ConversionError(f"{self.manager.name} 导出 PDF 超时") from exc
        except asyncio.CancelledError:
            await LibreOfficeWordToPdfEngine._terminate_process(process)  # noqa: SLF001
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
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    pypandoc.convert_file,
                    str(input_path),
                    "html5",
                    format="docx",
                    outputfile=str(html_path),
                    extra_args=["--standalone", "--embed-resources", "--mathml"],
                ),
                timeout=self.settings.word_conversion_timeout,
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

    ENGINE_ORDER = ("pandoc", "wps", "microsoft-word", "libreoffice")
    PREFERRED_ENGINE = "microsoft-word"

    def __init__(
        self,
        settings: AppSettings,
        libreoffice_manager: LibreOfficeManager,
        pandoc_engine: PandocEngine,
    ) -> None:
        self.settings = settings
        self.libreoffice_manager = libreoffice_manager
        self.engines: dict[str, ConversionEngine] = {
            "pandoc": PandocWordToPdfEngine(settings, pandoc_engine),
            "wps": NativeOfficeWordToPdfEngine(settings, wps_manager),
            "microsoft-word": NativeOfficeWordToPdfEngine(settings, word_manager),
            "libreoffice": LibreOfficeWordToPdfEngine(settings, libreoffice_manager),
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
            "managed": bool(default.get("managed", False)),
            "installer_found": bool(default.get("installer_found", False)),
            "can_install": bool(default.get("can_install", False)),
            "default_engine": default["id"],
            "engines": engines,
        }

    def get_engine_info(self, engine_id: str, *, refresh: bool = False) -> dict[str, Any]:
        """返回指定引擎状态。"""
        if engine_id == "libreoffice":
            info = self.libreoffice_manager.get_info(refresh=refresh)
            return {"id": "libreoffice", "name": "LibreOffice", "fidelity": "compatible", **info}
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
