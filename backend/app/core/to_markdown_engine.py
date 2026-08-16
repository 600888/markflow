"""
Word/PDF 转 Markdown 多引擎实现。

核心引擎为 Microsoft MarkItDown（本地离线 Python 库），在其之上提供
`.doc` COM 预处理、图片资源提取与扫描件检测等增强能力。
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core import pdf_ocr
from app.core.interfaces import ConversionEngine, ProgressCallback
from app.core.office_suite_check import NativeOfficeManager, word_manager, wps_manager
from app.models import ConversionResult, OutputFormat
from app.services.log import log
from app.utils.config import AppSettings
from app.utils.exceptions import (
    ConversionError,
    ToMarkdownUnavailableError,
    UnsupportedFormatError,
)

_SUPPORTED_SUFFIXES = {".docx", ".doc", ".pdf"}
_RGB_CHANNELS = 3
# MarkItDown 对 DOCX 内嵌图片输出字面量占位符（不含真实数据）
_MD_IMAGE_PLACEHOLDER = re.compile(
    r"!\[([^\]]*)\]\(data:image/([a-zA-Z0-9.+-]+);base64\.\.\.\)"
)


def _markitdown_version() -> str:
    """返回 MarkItDown 版本号；未安装时返回空字符串。"""
    try:
        import markitdown

        return str(getattr(markitdown, "__version__", ""))
    except ImportError:
        return ""


def _windows_creation_flags(*, new_process_group: bool = False) -> int:
    """返回不会创建控制台窗口的 Windows 子进程标志。"""
    if os.name != "nt":
        return 0
    flags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    if new_process_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    return flags


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    """终止子进程；Windows 下优先回收完整进程树。"""
    if process.returncode is not None:
        return
    taskkill = shutil.which("taskkill")
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


class DocToDocxConverter:
    """通过 Word/WPS COM 将 `.doc` 只读转存为 `.docx`。"""

    def __init__(self, settings: AppSettings, manager: NativeOfficeManager) -> None:
        self.settings = settings
        self.manager = manager

    async def convert_to_docx(self, input_path: Path, output_path: Path) -> Path:
        """调用本机 Office 应用，把 .doc 转存为 .docx。"""
        prog_id = self.manager.find_prog_id()
        if not prog_id:
            raise ToMarkdownUnavailableError(
                f"未检测到可用的 {self.manager.name}，无法处理 .doc 旧格式文件。"
            )
        output_path.unlink(missing_ok=True)  # noqa: ASYNC240
        script = self._build_script(
            prog_id,
            input_path.resolve(),  # noqa: ASYNC240
            output_path.resolve(),  # noqa: ASYNC240
        )
        shell = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not shell:
            raise ToMarkdownUnavailableError("未找到 PowerShell，无法调用 Office 转换接口")
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
            raise ConversionError(f"{self.manager.name} 转换 .doc 超时") from exc
        except asyncio.CancelledError:
            await _terminate_process(process)
            raise
        diagnostic = (stdout + stderr)[-65_536:].decode(errors="replace").strip()
        if process.returncode != 0:
            raise ConversionError(
                f"{self.manager.name} 转换 .doc 失败",
                detail={"diagnostic": diagnostic},
            )
        if not output_path.is_file() or output_path.stat().st_size == 0:  # noqa: ASYNC240
            raise ConversionError(f"{self.manager.name} 未生成有效的 .docx 文件")
        return output_path

    @staticmethod
    def _build_script(prog_id: str, input_path: Path, output_path: Path) -> str:
        """构造只读打开 .doc 并另存为 .docx 的 PowerShell 脚本。"""

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
                "  $doc.SaveAs($outputPath, 12)",
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


class MarkItDownEngine(ConversionEngine):
    """封装 MarkItDown 的 Word/PDF 转 Markdown 引擎。"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

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
        """把 .docx / .doc / .pdf 提取为 Markdown，并落盘图片资源。"""
        del extra_args, template_slug, convert_images, convert_mermaid
        if output_format != OutputFormat.MARKDOWN:
            raise UnsupportedFormatError("转 Markdown 管线仅支持 Markdown 输出")
        suffix = input_path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise UnsupportedFormatError(f"不支持 .{suffix.lstrip('.')} 文件")
        if not _markitdown_version():
            raise ToMarkdownUnavailableError("MarkItDown 引擎未安装，无法转换文档")

        opts = options or {}
        extract_images = bool(opts.get("extract_images", True))
        extract_formulas = bool(opts.get("extract_formulas", True))

        started = time.monotonic()
        work_dir = input_path.parent
        source = input_path
        if suffix == ".doc":
            if on_progress:
                await on_progress(0.1, "正在转换 .doc 为 .docx")
            manager = word_manager if word_manager.find_prog_id() else wps_manager
            converter = DocToDocxConverter(self.settings, manager)
            source = await converter.convert_to_docx(
                input_path,
                work_dir / f"{input_path.stem}.converted.docx",
            )
            suffix = ".docx"

        force_ocr = bool(opts.get("force_ocr", False)) and suffix == ".pdf"

        if on_progress:
            await on_progress(0.25, "正在提取文档内容")
        loop = asyncio.get_running_loop()
        text = ""
        if not force_ocr:
            text = await loop.run_in_executor(None, self._convert_text, source)

        if not text.strip() or force_ocr:
            if suffix == ".pdf":
                return await self._convert_scanned_pdf(
                    input_path,
                    work_dir,
                    opts,
                    on_progress,
                    started,
                )
            raise ConversionError("未能从文档中提取到任何内容")

        if extract_formulas and suffix == ".docx" and self._docx_has_omml(source):
            log.warning("文档包含 OMML 公式，MarkItDown 无法保留公式，转换结果可能不完整")

        if extract_images:
            if on_progress:
                await on_progress(0.6, "正在提取图片资源")
            text = self._extract_images(text, source, work_dir, suffix)

        if on_progress:
            await on_progress(0.9, "正在生成 Markdown 文件")
        md_path = work_dir / f"{input_path.stem}.md"
        md_path.write_text(text, encoding="utf-8")
        return _conversion_result(md_path, started)

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """仅当 MarkItDown 已安装时支持 Markdown 输出。"""
        return output_format == OutputFormat.MARKDOWN and bool(_markitdown_version())

    async def _convert_scanned_pdf(
        self,
        input_path: Path,
        work_dir: Path,
        opts: dict,
        on_progress: ProgressCallback | None,
        started: float,
    ) -> ConversionResult:
        """扫描件 PDF：走本地 OCR 管线（RapidOCR）。"""
        if not pdf_ocr.ocr_available():
            raise ConversionError(
                "该 PDF 无文本层（扫描件），且 OCR 引擎（RapidOCR）未安装，无法提取内容"
            )
        if on_progress:
            await on_progress(0.15, "检测到扫描件，正在启动 OCR")
        extract_images = bool(opts.get("extract_images", True))
        assets_dir = work_dir / "assets" / "media"
        markdown_text = await pdf_ocr.ocr_pdf(
            input_path,
            assets_dir,
            extract_images=extract_images,
            on_progress=on_progress,
        )
        md_path = work_dir / f"{input_path.stem}.md"
        md_path.write_text(markdown_text, encoding="utf-8")
        return _conversion_result(md_path, started)

    @staticmethod
    def _convert_text(path: Path) -> str:
        """同步调用 MarkItDown 转换（在 executor 中执行）。"""
        from markitdown import MarkItDown

        return MarkItDown().convert(str(path)).text_content

    def _extract_images(self, text: str, source: Path, work_dir: Path, suffix: str) -> str:
        """按源类型提取图片资源并回填 Markdown 引用。"""
        assets_dir = work_dir / "assets" / "media"
        if suffix == ".docx":
            return self._extract_docx_images(text, source, assets_dir)
        return self._extract_pdf_images(text, source, assets_dir)

    @staticmethod
    def _extract_docx_images(text: str, source: Path, assets_dir: Path) -> str:
        """从 docx 的 word/media 提取图片，替换 MarkItDown 输出的占位符。"""
        placeholders = list(_MD_IMAGE_PLACEHOLDER.finditer(text))
        if not placeholders:
            return text
        images = _docx_media_files(source)
        if not images:
            return text
        assets_dir.mkdir(parents=True, exist_ok=True)

        def replace(match: re.Match[str], index: int) -> str:
            alt = match.group(1)
            name, data = images[index]
            (assets_dir / name).write_bytes(data)
            return f"![{alt or '图片'}](assets/media/{name})"

        return _replace_placeholders(text, placeholders, replace, len(images))

    @staticmethod
    def _extract_pdf_images(text: str, source: Path, assets_dir: Path) -> str:
        """用 PyMuPDF 提取 PDF 内嵌图片，并在文档末尾追加图片资源小节。"""
        import fitz

        doc = fitz.open(source)
        refs: list[tuple[int, str]] = []
        seen: set[int] = set()
        try:
            for page_index, page in enumerate(doc, start=1):
                for image in page.get_images(full=True):
                    xref = int(image[0])
                    if xref in seen:
                        continue
                    seen.add(xref)
                    pix = fitz.Pixmap(doc, xref)
                    try:
                        if pix.n - pix.alpha > _RGB_CHANNELS:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        assets_dir.mkdir(parents=True, exist_ok=True)
                        name = f"pdf_image_p{page_index:03d}_{xref}.png"
                        pix.save(assets_dir / name)
                        refs.append((page_index, f"assets/media/{name}"))
                    finally:
                        pix = None
        finally:
            doc.close()
        if not refs:
            return text
        lines = ["", "## 图片资源", ""]
        for index, (page, relative) in enumerate(refs, start=1):
            lines.append(f"![图片 {index}（第 {page} 页）]({relative})")
        return text.rstrip() + "\n" + "\n".join(lines) + "\n"

    @staticmethod
    def _docx_has_omml(path: Path) -> bool:
        """检测 docx 正文中是否包含 OMML 公式。"""
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
            return "<m:oMath" in xml
        except (KeyError, zipfile.BadZipFile):
            return False


class ToMarkdownEngineRegistry(ConversionEngine):
    """集中提供引擎状态，并把转换分派给 MarkItDown 实现。"""

    ENGINE_ORDER = ("markitdown", "word-com", "pdf-ocr")
    PREFERRED_ENGINE = "markitdown"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.engines: dict[str, ConversionEngine] = {
            "markitdown": MarkItDownEngine(settings),
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
            "supported_inputs": default["supported_inputs"],
            "diagnostic": default["diagnostic"],
            "default_engine": default["id"],
            "engines": engines,
        }

    def get_engine_info(self, engine_id: str, *, refresh: bool = False) -> dict[str, Any]:
        """返回指定引擎状态。"""
        if engine_id == "markitdown":
            version = _markitdown_version()
            available = bool(version)
            return {
                "id": "markitdown",
                "name": "MarkItDown",
                "available": available,
                "version": version,
                "supported_inputs": ["docx", "pdf"],
                "diagnostic": "MarkItDown 引擎已就绪" if available else "MarkItDown 库未安装",
            }
        if engine_id == "word-com":
            prog_id = word_manager.find_prog_id() or wps_manager.find_prog_id()
            return {
                "id": "word-com",
                "name": "Word 兼容（COM）",
                "available": bool(prog_id),
                "version": "",
                "supported_inputs": ["doc"],
                "diagnostic": (
                    "可用于 .doc 旧格式预处理" if prog_id else "未检测到 Word 或 WPS"
                ),
            }
        if engine_id == "pdf-ocr":
            available = pdf_ocr.ocr_available()
            return {
                "id": "pdf-ocr",
                "name": "扫描件 OCR",
                "available": available,
                "version": "",
                "supported_inputs": ["pdf"],
                "diagnostic": (
                    "扫描件 PDF 将自动走 OCR 识别" if available else "OCR 引擎（RapidOCR）未安装"
                ),
            }
        raise ToMarkdownUnavailableError(f"未知的转 Markdown 引擎: {engine_id}")

    def resolve_engine_id(self, engine_id: str = "", *, refresh: bool = False) -> str:
        """解析显式选择；未指定时使用默认引擎。"""
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
        """校验引擎可用性后分派到 MarkItDown 实现。"""
        opts = options or {}
        selected = self.resolve_engine_id(str(opts.get("engine", "")))
        if selected not in {"markitdown", "word-com", "pdf-ocr"}:
            raise ToMarkdownUnavailableError(f"不支持的转 Markdown 引擎: {selected}")
        info = self.get_engine_info(selected, refresh=True)
        if not info["available"]:
            raise ToMarkdownUnavailableError(str(info["diagnostic"]))
        suffix = input_path.suffix.lower().lstrip(".")
        if suffix not in info["supported_inputs"] and suffix != "doc":
            raise UnsupportedFormatError(f"{info['name']} 不支持 .{suffix} 文件")
        engine = self.engines["markitdown"]
        convert_options = dict(opts)
        if selected == "pdf-ocr":
            convert_options["force_ocr"] = True
        return await engine.convert(
            input_path,
            output_format,
            extra_args,
            template_slug,
            convert_images=convert_images,
            convert_mermaid=convert_mermaid,
            options=convert_options,
            on_progress=on_progress,
        )

    async def validate_format(self, output_format: OutputFormat) -> bool:
        """任一引擎可用时支持 Markdown 输出。"""
        return output_format == OutputFormat.MARKDOWN and bool(self.get_info()["available"])


def _docx_media_files(path: Path) -> list[tuple[str, bytes]]:
    """读取 docx 内 word/media 下的图片，按出现顺序返回 (文件名, 数据)。"""
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.startswith("word/media/") and not name.endswith("/")
            ]
            names.sort(key=_media_sort_key)
            return [(Path(name).name, archive.read(name)) for name in names]
    except (zipfile.BadZipFile, KeyError):
        return []


def _media_sort_key(name: str) -> tuple[int, str]:
    """按 media 文件名的数字编号排序（image2 排在 image10 之前）。"""
    match = re.search(r"(\d+)", Path(name).stem)
    return (int(match.group(1)) if match else 0, name)


def _replace_placeholders(
    text: str,
    placeholders: list[re.Match[str]],
    replace: Callable[[re.Match[str], int], str],
    limit: int,
) -> str:
    """按顺序替换占位符；超出图片数量的占位符保持原样。"""
    parts: list[str] = []
    cursor = 0
    for index, match in enumerate(placeholders):
        parts.append(text[cursor : match.start()])
        if index < limit:
            parts.append(replace(match, index))
        else:
            parts.append(match.group(0))
        cursor = match.end()
    parts.append(text[cursor:])
    return "".join(parts)


def _conversion_result(path: Path, started: float) -> ConversionResult:
    return ConversionResult(
        task_id=uuid4(),
        output_path=path,
        output_format=OutputFormat.MARKDOWN,
        duration_ms=round((time.monotonic() - started) * 1000),
        file_size=path.stat().st_size,
    )
