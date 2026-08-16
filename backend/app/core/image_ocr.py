"""
图片 OCR 提取（RapidOCR，本地离线）。

识别上传/粘贴的图片中的文字，支持保留版面（段落换行）输出，
并返回逐行置信度、行数与耗时等信息。
"""

from __future__ import annotations

import re
import statistics
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.utils.exceptions import ConversionError, OcrUnavailableError

_OCR_LOCK = threading.Lock()
_OCR_ENGINE: Any | None = None
_SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_MAX_IMAGE_PIXELS = 40_000_000  # 约 6300×6300，防止超大图片拖垮内存


def ocr_available() -> bool:
    """RapidOCR 是否可导入。"""
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except ImportError:
        return False


def supported_extension(suffix: str) -> bool:
    """扩展名是否为支持的图片格式。"""
    return suffix.lower() in _SUPPORTED_EXTENSIONS


def _get_engine() -> Any:  # noqa: ANN401
    """延迟初始化的 RapidOCR 单例（模型加载较慢，复用实例）。"""
    global _OCR_ENGINE  # noqa: PLW0603
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


@dataclass
class OcrLineResult:
    """单条识别结果。"""

    text: str
    score: float
    x: int
    y: int
    width: int
    height: int


@dataclass
class OcrResult:
    """图片 OCR 整体结果。"""

    text: str
    lines: list[OcrLineResult]
    confidence: float
    duration_ms: int
    width: int
    height: int
    line_count: int


def _load_rgb_array(image_path: Path) -> Any:  # noqa: ANN401
    """用 Pillow 打开图片，修正 EXIF 方向并转为 RGB numpy 数组。"""
    from PIL import Image, ImageOps

    try:
        with Image.open(image_path) as opened:
            width, height = opened.size
            data = ImageOps.exif_transpose(opened).convert("RGB")
    except Exception as exc:
        raise ConversionError(f"无法读取图片文件: {exc}") from exc
    if width * height > _MAX_IMAGE_PIXELS:
        raise ConversionError("图片尺寸过大，无法识别")
    return data


def _recognize(image_path: Path) -> tuple[list[OcrLineResult], int, int]:
    """同步执行 OCR，返回 (行结果, 图片宽, 图片高)。"""
    from PIL import Image

    array = _load_rgb_array(image_path)
    engine = _get_engine()
    with _OCR_LOCK:
        results, _ = engine(array)  # type: ignore[operator]

    lines: list[OcrLineResult] = []
    for item in results or []:
        box, text, score = item[0], item[1], float(item[2])
        clean = str(text).strip()
        if not clean:
            continue
        x0, y0 = float(box[0][0]), float(box[0][1])
        width = abs(float(box[1][0]) - float(box[0][0]))
        height = abs(float(box[2][1]) - float(box[0][1]))
        lines.append(
            OcrLineResult(
                text=clean,
                score=score,
                x=round(x0),
                y=round(y0),
                width=round(width),
                height=round(height),
            )
        )
    lines.sort(key=lambda line: (line.y, line.x))
    with Image.open(image_path) as image:
        width, height = image.size
    return lines, width, height


def _group_paragraphs(lines: list[OcrLineResult]) -> list[list[OcrLineResult]]:
    """按 y 间距把行分组为段落（段间空行）。"""
    if not lines:
        return []
    heights = [line.height for line in lines if line.height > 0]
    median_height = statistics.median(heights) if heights else 20.0
    paragraphs: list[list[OcrLineResult]] = [[lines[0]]]
    for line in lines[1:]:
        previous = paragraphs[-1][-1]
        gap = line.y - (previous.y + previous.height)
        if gap > max(median_height * 1.6, 8.0):
            paragraphs.append([])
        paragraphs[-1].append(line)
    return paragraphs


def _merge_text(left: str, right: str) -> str:
    """合并同行/段内文本：CJK 字符间不加空格。"""
    if not left:
        return right
    if _CJK_RE.search(left[-1]) or _CJK_RE.search(right[0]):
        return f"{left}{right}"
    return f"{left} {right}"


def _build_text(lines: list[OcrLineResult], *, keep_layout: bool) -> str:
    """按是否保留版面生成输出文本。"""
    paragraphs = _group_paragraphs(lines)
    rendered: list[str] = []
    for paragraph in paragraphs:
        if keep_layout:
            rendered.append("\n".join(line.text for line in paragraph))
        else:
            text = ""
            for line in paragraph:
                text = _merge_text(text, line.text)
            rendered.append(text)
    return "\n\n".join(rendered)


def recognize_image(image_path: Path, *, keep_layout: bool = True) -> OcrResult:
    """识别图片并返回结构化结果。"""
    if not ocr_available():
        raise OcrUnavailableError("OCR 引擎（RapidOCR）未安装，无法识别图片")
    started = time.monotonic()
    lines, width, height = _recognize(image_path)
    text = _build_text(lines, keep_layout=keep_layout)
    confidence = (
        round(sum(line.score for line in lines) / len(lines), 4) if lines else 0.0
    )
    return OcrResult(
        text=text,
        lines=lines,
        confidence=confidence,
        duration_ms=round((time.monotonic() - started) * 1000),
        width=width,
        height=height,
        line_count=len(lines),
    )
