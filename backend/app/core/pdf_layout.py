"""文本型 PDF 的版面感知 Markdown 重建。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any, Protocol

import pdfplumber

_TABLE_LINE_HEIGHT = 2.0
_TABLE_ROW_MAX_HEIGHT = 72.0
_COORD_TOLERANCE = 1.5
_MIN_TABLE_WIDTH_RATIO = 0.45
_MAX_TABLE_COLUMNS = 12
_MIN_TABLE_COLUMNS = 2
_MIN_TABLE_ROWS = 2
_MIN_HEADER_HEIGHT = 8.0
_HEADING_LEVEL_ONE_SIZE = 15.0
_HEADING_LEVEL_TWO_SIZE = 13.0
_HEADING_LEVEL_THREE_SIZE = 11.5
_PARAGRAPH_MAX_GAP = 9.0
_BULLET_MAX_SIZE = 8.0
_BULLET_MAX_GAP = 24.0
_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?(?:\s+|$)")
_MERMAID_START = re.compile(
    r"^(?:flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt)\b"
)


@dataclass(slots=True)
class _TableRegion:
    """一页中的表格范围与单元格内容。"""

    bbox: tuple[float, float, float, float]
    rows: list[list[str]]


@dataclass(slots=True)
class _PageElement:
    """按页面纵坐标排序的 Markdown 元素。"""

    page: int
    top: float
    kind: str
    markdown: str = ""
    rows: list[list[str]] | None = None


class _PdfPlumberPage(Protocol):
    """本模块使用到的 pdfplumber 页面接口。"""

    rects: list[dict[str, Any]]
    curves: list[dict[str, Any]]
    width: float
    height: float

    def crop(self, bbox: tuple[float, float, float, float], *, strict: bool) -> _PdfPlumberPage: ...

    def extract_text(self, **kwargs: object) -> str | None: ...

    def extract_text_lines(self, **kwargs: object) -> list[dict[str, Any]]: ...


class _FitzPage(Protocol):
    """本模块使用到的 PyMuPDF 页面接口。"""

    def get_text(self, option: str) -> dict[str, Any]: ...


def convert_pdf_layout(
    source: Path,
    assets_dir: Path,
    *,
    extract_tables: bool,
    extract_images: bool,
) -> str:
    """按坐标重建文本型 PDF，避免跨栏、表格和图片打乱阅读顺序。"""
    import pymupdf

    elements: list[_PageElement] = []
    seen_images: set[str] = set()
    image_index = 0
    fitz_document = pymupdf.open(source)
    try:
        with pdfplumber.open(source) as plumber_document:
            for page_index, plumber_page in enumerate(plumber_document.pages):
                page_number = page_index + 1
                tables = _find_tables(plumber_page) if extract_tables else []
                elements.extend(_extract_text_elements(plumber_page, tables, page_number))
                elements.extend(
                    _PageElement(
                        page=page_number,
                        top=table.bbox[1],
                        kind="table",
                        rows=table.rows,
                    )
                    for table in tables
                )
                if extract_images:
                    image_elements, image_index = _extract_image_elements(
                        fitz_document[page_index],
                        assets_dir,
                        page_number,
                        seen_images,
                        image_index,
                    )
                    elements.extend(image_elements)
    finally:
        fitz_document.close()

    elements.sort(key=lambda item: (item.page, item.top, _element_priority(item.kind)))
    elements = _merge_adjacent_tables(elements)
    rendered = [_render_element(item) for item in elements]
    markdown = "\n\n".join(item for item in rendered if item)
    return markdown.strip() + ("\n" if markdown.strip() else "")


def _find_tables(page: _PdfPlumberPage) -> list[_TableRegion]:
    """识别 Chromium/Word PDF 中由表头底色和横向分隔线构成的表格。"""
    rects = [_normalise_rect(rect) for rect in [*page.rects, *page.curves]]
    header_groups = _header_groups(rects, float(page.width))
    regions: list[_TableRegion] = []
    for index, header in enumerate(header_groups):
        next_header_top = (
            header_groups[index + 1][0]["top"]
            if index + 1 < len(header_groups)
            else float(page.height)
        )
        columns = [(rect["x0"], rect["x1"]) for rect in header]
        header_top = min(rect["top"] for rect in header)
        header_bottom = max(rect["bottom"] for rect in header)
        separators = _matching_separators(
            rects,
            columns,
            header_bottom,
            next_header_top,
        )
        if len(separators) < _MIN_TABLE_ROWS:
            continue
        row_boundaries = [header_top, *separators]
        rows = [
            _extract_table_row(page, columns, row_top, row_bottom)
            for row_top, row_bottom in pairwise(row_boundaries)
        ]
        rows = [row for row in rows if any(cell for cell in row)]
        if len(rows) < _MIN_TABLE_ROWS:
            continue
        regions.append(
            _TableRegion(
                bbox=(columns[0][0], header_top, columns[-1][1], separators[-1]),
                rows=rows,
            )
        )
    return regions


def _normalise_rect(rect: dict[str, Any]) -> dict[str, float]:
    return {
        "x0": float(rect["x0"]),
        "x1": float(rect["x1"]),
        "top": float(rect["top"]),
        "bottom": float(rect["bottom"]),
    }


def _header_groups(
    rects: list[dict[str, float]],
    page_width: float,
) -> list[list[dict[str, float]]]:
    grouped: dict[tuple[float, float], list[dict[str, float]]] = {}
    for rect in rects:
        height = rect["bottom"] - rect["top"]
        if height < _MIN_HEADER_HEIGHT:
            continue
        key = (round(rect["top"], 1), round(rect["bottom"], 1))
        grouped.setdefault(key, []).append(rect)

    candidates: list[list[dict[str, float]]] = []
    for group in grouped.values():
        ordered = sorted(group, key=lambda item: item["x0"])
        if not _MIN_TABLE_COLUMNS <= len(ordered) <= _MAX_TABLE_COLUMNS:
            continue
        if not _contiguous_spans(ordered):
            continue
        width = ordered[-1]["x1"] - ordered[0]["x0"]
        if width < page_width * _MIN_TABLE_WIDTH_RATIO:
            continue
        candidates.append(ordered)
    candidates.sort(key=lambda group: group[0]["top"])
    return candidates


def _contiguous_spans(rects: list[dict[str, float]]) -> bool:
    return all(
        abs(left["x1"] - right["x0"]) <= _COORD_TOLERANCE
        for left, right in pairwise(rects)
    )


def _matching_separators(
    rects: list[dict[str, float]],
    columns: list[tuple[float, float]],
    header_bottom: float,
    limit: float,
) -> list[float]:
    groups: dict[float, list[dict[str, float]]] = {}
    for rect in rects:
        height = rect["bottom"] - rect["top"]
        if height > _TABLE_LINE_HEIGHT:
            continue
        if rect["top"] < header_bottom - _COORD_TOLERANCE or rect["top"] >= limit:
            continue
        groups.setdefault(round(rect["top"], 1), []).append(rect)

    matches: list[float] = []
    previous = header_bottom
    for top in sorted(groups):
        spans = sorted(groups[top], key=lambda item: item["x0"])
        if not _spans_match_columns(spans, columns):
            continue
        if matches and top - previous > _TABLE_ROW_MAX_HEIGHT:
            break
        if not matches and abs(top - header_bottom) > _COORD_TOLERANCE * 2:
            continue
        if not matches or top - matches[-1] > _COORD_TOLERANCE:
            matches.append(top)
            previous = top
    return matches


def _spans_match_columns(
    spans: list[dict[str, float]],
    columns: list[tuple[float, float]],
) -> bool:
    for x0, x1 in columns:
        if not any(
            abs(span["x0"] - x0) <= _COORD_TOLERANCE
            and abs(span["x1"] - x1) <= _COORD_TOLERANCE
            for span in spans
        ):
            return False
    return True


def _extract_table_row(
    page: _PdfPlumberPage,
    columns: list[tuple[float, float]],
    top: float,
    bottom: float,
) -> list[str]:
    cells: list[str] = []
    for x0, x1 in columns:
        cropped = page.crop(
            (x0 + 0.5, top + 0.5, x1 - 0.5, bottom - 0.1),
            strict=False,
        )
        value = cropped.extract_text(x_tolerance=2, y_tolerance=3) or ""
        cells.append(_clean_cell(value))
    return cells


def _clean_cell(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "<br>".join(line for line in lines if line)


def _extract_text_elements(
    page: _PdfPlumberPage,
    tables: list[_TableRegion],
    page_number: int,
) -> list[_PageElement]:
    raw_lines = page.extract_text_lines(return_chars=True)
    lines = _mark_bulleted_lines(
        [line for line in raw_lines if not _line_in_table(line, tables)],
        page.curves,
    )
    elements: list[_PageElement] = []
    paragraph: list[dict[str, Any]] = []
    code_lines: list[dict[str, Any]] = []
    list_lines: list[dict[str, Any]] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = _join_paragraph_lines(paragraph, float(page.width))
        if text:
            elements.append(
                _PageElement(
                    page=page_number,
                    top=float(paragraph[0]["top"]),
                    kind="text",
                    markdown=text,
                )
            )
        paragraph.clear()

    def flush_code() -> None:
        if not code_lines:
            return
        text_lines = [str(line["text"]).rstrip() for line in code_lines]
        language = "mermaid" if _MERMAID_START.match(text_lines[0].strip()) else "text"
        elements.append(
            _PageElement(
                page=page_number,
                top=float(code_lines[0]["top"]),
                kind="code",
                markdown=f"```{language}\n" + "\n".join(text_lines) + "\n```",
            )
        )
        code_lines.clear()

    def flush_list() -> None:
        if not list_lines:
            return
        elements.append(
            _PageElement(
                page=page_number,
                top=float(list_lines[0]["top"]),
                kind="list",
                markdown="\n".join(str(line["text"]).strip() for line in list_lines),
            )
        )
        list_lines.clear()

    for line in lines:
        text = str(line["text"]).strip()
        if not text:
            continue
        if _is_code_line(line):
            flush_paragraph()
            flush_list()
            code_lines.append(line)
            continue
        flush_code()
        if text.startswith("- "):
            flush_paragraph()
            list_lines.append(line)
            continue
        flush_list()
        heading_level = _heading_level(line)
        if heading_level:
            flush_paragraph()
            elements.append(
                _PageElement(
                    page=page_number,
                    top=float(line["top"]),
                    kind="heading",
                    markdown=f"{'#' * heading_level} {text}",
                )
            )
            continue
        if paragraph and not _continues_paragraph(paragraph[-1], line, float(page.width)):
            flush_paragraph()
        paragraph.append(line)

    flush_code()
    flush_list()
    flush_paragraph()
    return elements


def _mark_bulleted_lines(
    lines: list[dict[str, Any]],
    curves: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bullets = []
    for curve in curves:
        width = float(curve["x1"]) - float(curve["x0"])
        height = float(curve["bottom"]) - float(curve["top"])
        if 0 < width <= _BULLET_MAX_SIZE and 0 < height <= _BULLET_MAX_SIZE:
            bullets.append(curve)

    marked: list[dict[str, Any]] = []
    for line in lines:
        line_top = float(line["top"])
        line_bottom = float(line["bottom"])
        line_x0 = float(line["x0"])
        has_bullet = any(
            line_top <= (float(bullet["top"]) + float(bullet["bottom"])) / 2 <= line_bottom
            and 0 <= line_x0 - float(bullet["x1"]) <= _BULLET_MAX_GAP
            for bullet in bullets
        )
        marked_line = (
            {**line, "text": f"- {str(line['text']).strip()}"} if has_bullet else line
        )
        marked.append(marked_line)
    return marked


def _line_in_table(line: dict[str, Any], tables: list[_TableRegion]) -> bool:
    center_x = (float(line["x0"]) + float(line["x1"])) / 2
    center_y = (float(line["top"]) + float(line["bottom"])) / 2
    return any(
        x0 - 1 <= center_x <= x1 + 1 and top - 1 <= center_y <= bottom + 1
        for x0, top, x1, bottom in (table.bbox for table in tables)
    )


def _is_code_line(line: dict[str, Any]) -> bool:
    fonts = {str(char.get("fontname", "")).lower() for char in line.get("chars", [])}
    return bool(fonts) and sum("consolas" in font or "courier" in font for font in fonts) >= 1


def _heading_level(line: dict[str, Any]) -> int:
    chars = line.get("chars", [])
    if not chars:
        return 0
    sizes = [float(char.get("size", 0)) for char in chars]
    fonts = {str(char.get("fontname", "")).lower() for char in chars}
    bold = any("hei" in font or "bold" in font for font in fonts)
    size = median(sizes)
    text = str(line["text"]).strip()
    match = _HEADING_PATTERN.match(text)
    if bold and match:
        depth = match.group(1).count(".") + 1
        return min(depth + 1, 6)
    if not bold:
        return 0
    if size >= _HEADING_LEVEL_ONE_SIZE:
        return 1
    if size >= _HEADING_LEVEL_TWO_SIZE:
        return 2
    if size >= _HEADING_LEVEL_THREE_SIZE:
        return 3
    return 0


def _continues_paragraph(
    previous: dict[str, Any],
    current: dict[str, Any],
    page_width: float,
) -> bool:
    gap = float(current["top"]) - float(previous["bottom"])
    if gap > _PARAGRAPH_MAX_GAP:
        return False
    previous_text = str(previous["text"]).rstrip()
    if previous_text.endswith(("。", "！", "？", "；", ":", "：", ".", "!", "?")):
        return False
    return float(previous["x1"]) >= page_width * 0.84


def _join_paragraph_lines(lines: list[dict[str, Any]], page_width: float) -> str:
    del page_width
    values = [str(line["text"]).strip() for line in lines]
    result = values[0]
    for value in values[1:]:
        separator = " " if _needs_space(result, value) else ""
        result += separator + value
    return result


def _needs_space(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left[-1].isascii() and right[0].isascii() and left[-1].isalnum() and right[0].isalnum()


def _extract_image_elements(
    page: _FitzPage,
    assets_dir: Path,
    page_number: int,
    seen_images: set[str],
    image_index: int,
) -> tuple[list[_PageElement], int]:
    elements: list[_PageElement] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 1 or not block.get("image"):
            continue
        data = bytes(block["image"])
        digest = hashlib.sha1(data).hexdigest()  # noqa: S324 - 仅用于图片去重
        if digest in seen_images:
            continue
        seen_images.add(digest)
        image_index += 1
        extension = str(block.get("ext") or "png").lower()
        name = f"pdf_image_p{page_number:03d}_{image_index:03d}.{extension}"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / name).write_bytes(data)
        elements.append(
            _PageElement(
                page=page_number,
                top=float(block["bbox"][1]),
                kind="image",
                markdown=f"![第 {page_number} 页图片](assets/media/{name})",
            )
        )
    return elements, image_index


def _merge_adjacent_tables(elements: list[_PageElement]) -> list[_PageElement]:
    merged: list[_PageElement] = []
    for element in elements:
        if (
            element.kind == "table"
            and element.rows
            and merged
            and merged[-1].kind == "table"
            and merged[-1].rows
            and _same_header(merged[-1].rows[0], element.rows[0])
        ):
            merged[-1].rows.extend(element.rows[1:])
            continue
        merged.append(element)
    return merged


def _same_header(left: list[str], right: list[str]) -> bool:
    return len(left) == len(right) and [cell.strip() for cell in left] == [
        cell.strip() for cell in right
    ]


def _render_element(element: _PageElement) -> str:
    if element.kind == "table" and element.rows:
        return _table_to_markdown(element.rows)
    return element.markdown.strip()


def _table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalised = [row + [""] * (width - len(row)) for row in rows]

    def render_row(row: list[str]) -> str:
        cells = [cell.replace("|", "\\|").strip() or " " for cell in row]
        return "| " + " | ".join(cells) + " |"

    separator = "| " + " | ".join("---" for _ in range(width)) + " |"
    return "\n".join(
        [render_row(normalised[0]), separator, *(render_row(row) for row in normalised[1:])]
    )


def _element_priority(kind: str) -> int:
    priorities = {
        "heading": 0,
        "text": 1,
        "code": 1,
        "list": 1,
        "table": 2,
        "image": 3,
    }
    return priorities.get(kind, 9)
