"""
扫描件 PDF 的 OCR 提取（RapidOCR，本地离线）。

把无文本层的 PDF 逐页渲染为图像后识别，按版面坐标重建标题/段落结构，
并在启用 `extract_images` 时把每页渲染图落盘 `assets/media/` 供 Markdown 引用。
"""

from __future__ import annotations

import asyncio
import re
import statistics
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.interfaces import ProgressCallback
from app.services.log import log
from app.utils.exceptions import ConversionError

_OCR_LOCK = threading.Lock()
_OCR_ENGINE: Any | None = None
_RENDER_DPI = 200
_PAGE_NUMBER_RE = re.compile(r"^[\d\s\-—.·]{1,6}$")


def ocr_available() -> bool:
    """RapidOCR 是否可导入。"""
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except ImportError:
        return False


def _get_engine() -> Any:  # noqa: ANN401
    """延迟初始化的 RapidOCR 单例（模型加载较慢，复用实例）。"""
    global _OCR_ENGINE  # noqa: PLW0603
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


@dataclass
class OcrLine:
    """单条 OCR 识别结果（含版面坐标）。"""

    text: str
    score: float
    page: int
    x0: float
    y0: float
    height: float


@dataclass
class _PageResult:
    page: int
    lines: list[OcrLine]
    image_path: Path | None


def _ocr_image(image_path: Path, page: int) -> list[OcrLine]:
    """识别单页图像，返回按 y/x 排序的行。"""
    engine = _get_engine()
    with _OCR_LOCK:
        results, _ = engine(str(image_path))  # type: ignore[operator]
    lines: list[OcrLine] = []
    for item in results or []:
        box, text, score = item[0], item[1], float(item[2])
        clean = str(text).strip()
        if not clean:
            continue
        if _PAGE_NUMBER_RE.match(clean):
            continue
        x0, y0 = float(box[0][0]), float(box[0][1])
        height = abs(float(box[2][1]) - float(box[0][1]))
        lines.append(OcrLine(clean, score, page, x0, y0, height))
    lines.sort(key=lambda line: (line.y0, line.x0))
    return lines


def _render_page(page: Any, output_path: Path) -> None:  # noqa: ANN401
    """把 PDF 页渲染为 PNG。"""
    pix = page.get_pixmap(dpi=_RENDER_DPI)
    pix.save(str(output_path))


def _merge_line_text(left: str, right: str) -> str:
    """合并同行文本：中文字符间不加空格，其余情况补一个空格。"""
    if not left:
        return right
    if re.search(r"[\u4e00-\u9fff]$", left) or re.match(r"^[\u4e00-\u9fff]", right):
        return f"{left}{right}"
    return f"{left} {right}"


def _build_markdown(pages: list[_PageResult], *, include_images: bool) -> str:
    """把各页 OCR 行重建为 Markdown：标题启发式 + 段落合并 + 页面图像小节。"""
    blocks: list[str] = []
    for page_result in pages:
        lines = [
            line for line in page_result.lines if not _PAGE_NUMBER_RE.match(line.text)
        ]
        if not lines:
            continue
        heights = [line.height for line in lines if line.height > 0]
        median_height = statistics.median(heights) if heights else 0.0
        title_threshold = median_height * 1.35 if median_height > 0 else 0.0

        # 同行合并：y 接近的行按 x 排序拼接
        merged: list[list[OcrLine]] = []
        for line in lines:
            tolerance = max(line.height * 0.5, 6.0)
            if merged and abs(line.y0 - merged[-1][-1].y0) <= tolerance:
                merged[-1].append(line)
            else:
                merged.append([line])

        # 段落合并 + 标题
        paragraph_lines: list[str] = []
        for group in merged:
            group.sort(key=lambda line: line.x0)
            text = ""
            for line in group:
                text = _merge_line_text(text, line.text)
            if not text:
                continue
            height = max(line.height for line in group)
            if title_threshold and height >= title_threshold:
                text = f"# {text}"
            paragraph_lines.append(text)

        if not paragraph_lines:
            continue
        if blocks:
            blocks.append("")
        blocks.append("\n\n".join(paragraph_lines))

    if include_images:
        image_lines = [
            f"![第 {result.page} 页](assets/media/{result.image_path.name})"
            for result in pages
            if result.image_path is not None
        ]
        if image_lines:
            blocks.append("")
            blocks.append("## 页面图像")
            blocks.append("")
            blocks.append("\n\n".join(image_lines))

    return "\n".join(blocks)


async def ocr_pdf(
    input_path: Path,
    assets_dir: Path,
    *,
    extract_images: bool,
    on_progress: ProgressCallback | None = None,
) -> str:
    """OCR 整个 PDF，返回 Markdown 文本；页图按需落盘 assets_dir。"""
    if not ocr_available():
        raise ConversionError("OCR 引擎（RapidOCR）未安装，无法转换扫描件")
    import shutil
    import tempfile

    import fitz

    loop = asyncio.get_running_loop()
    doc = fitz.open(input_path)
    total = doc.page_count
    pages: list[_PageResult] = []
    temp_dir: Path | None = None
    try:
        for index in range(total):
            if on_progress:
                await on_progress(
                    0.25 + 0.6 * index / max(total, 1),
                    f"正在 OCR 第 {index + 1}/{total} 页",
                )
            page = doc[index]
            if extract_images:
                assets_dir.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
                image_path = assets_dir / f"page_{index + 1:03d}.png"
                await loop.run_in_executor(None, _render_page, page, image_path)
            else:
                if temp_dir is None:
                    temp_dir = Path(tempfile.mkdtemp(prefix="markflow-ocr-"))
                image_path = temp_dir / f"page_{index + 1:03d}.png"
                await loop.run_in_executor(None, _render_page, page, image_path)
            lines = await loop.run_in_executor(None, _ocr_image, image_path, index + 1)
            pages.append(_PageResult(index + 1, lines, image_path if extract_images else None))
            log.debug(f"OCR 第 {index + 1} 页完成，识别 {len(lines)} 行")
    finally:
        doc.close()
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    markdown = _build_markdown(pages, include_images=extract_images)
    if sum(len(result.lines) for result in pages) == 0:
        raise ConversionError("OCR 未能从扫描件中识别出任何内容")
    if on_progress:
        await on_progress(0.95, "OCR 完成，正在生成 Markdown")
    return markdown
