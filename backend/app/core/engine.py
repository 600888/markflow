"""Pandoc 转换引擎实现"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path
from uuid import UUID

import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.core.interfaces import ConversionEngine, ProgressCallback
from app.core.log import log
from app.core.template_manager import TemplateManager
from app.models import ConversionResult, OutputFormat
from app.models.templates import ConversionOptions
from app.utils.config import AppSettings
from app.utils.exceptions import ConversionError, PandocNotFoundError, UnsupportedFormatError

# ── 字号映射 ──────────────────────────────────────────────
SIZE_MAP: dict[str, float] = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24,
    "二号": 22, "小二": 18, "三号": 16, "小三": 15,
    "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
    "六号": 7.5, "小六": 6.5, "七号": 5.5, "八号": 5,
}

ALIGN_MAP: dict[str, WD_ALIGN_PARAGRAPH] = {
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _parse_size(raw: str | float) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if s in SIZE_MAP:
        return SIZE_MAP[s]
    num = "".join(c for c in s if c.isdigit() or c == ".")
    try:
        return float(num)
    except ValueError:
        return None


# ── 表格 XML 操作辅助 ─────────────────────────────────────
def _resolve_tc(cell_or_tc: object):
    """统一入口：从 python-docx Cell 或 CT_Tc 元素获取 CT_Tc"""
    if hasattr(cell_or_tc, "_tc"):
        return cell_or_tc._tc  # type: ignore[attr-defined]
    return cell_or_tc  # 已是 CT_Tc


def _set_cell_border(cell_or_tc: object, edge: str, weight: float, color: str) -> None:
    """设置单元格单边边框"""
    tc = _resolve_tc(cell_or_tc)
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    # 移除同边旧定义
    for old in tcBorders.findall(qn(f"w:{edge}")):
        tcBorders.remove(old)
    el = OxmlElement(f"w:{edge}")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(int(weight * 8)))  # 1pt = 8 eighths
    el.set(qn("w:space"), "0")
    el.set(qn("w:color"), color)
    tcBorders.append(el)


def _clear_cell_border(cell_or_tc: object, edge: str) -> None:
    """清除单元格单边边框"""
    tc = _resolve_tc(cell_or_tc)
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        return
    for old in tcBorders.findall(qn(f"w:{edge}")):
        tcBorders.remove(old)


def _set_cell_margins(cell_or_tc: object, top: int, bottom: int, left: int, right: int) -> None:
    """设置单元格内边距（单位: dxa，1pt ≈ 20 dxa）"""
    tc = _resolve_tc(cell_or_tc)
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:tcMar")):
        tcPr.remove(old)
    tcMar = OxmlElement("w:tcMar")
    for direction, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        mar = OxmlElement(f"w:{direction}")
        mar.set(qn("w:w"), str(val * 20))  # dxa
        mar.set(qn("w:type"), "dxa")
        tcMar.append(mar)
    tcPr.append(tcMar)


def _set_cell_shading(cell_or_tc: object, fill_hex: str) -> None:
    """设置单元格底色"""
    tc = _resolve_tc(cell_or_tc)
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex.lstrip("#"))
    tcPr.append(shd)


def _apply_cell_text_format(cell_or_tc: object, font_name: str | None = None,
                             font_size_pt: float | None = None,
                             bold: bool | None = None,
                             alignment: WD_ALIGN_PARAGRAPH | None = None) -> None:
    """对单元格内所有段落应用文本格式"""
    tc = _resolve_tc(cell_or_tc)
    for paragraph in tc.getchildren():  # type: ignore[attr-defined]
        p = paragraph  # w:p element
        if alignment is not None:
            pPr = p.find(qn("w:pPr"))
            if pPr is None:
                pPr = OxmlElement("w:pPr")
                p.insert(0, pPr)
            jc = pPr.find(qn("w:jc"))
            if jc is None:
                jc = OxmlElement("w:jc")
                pPr.append(jc)
            jc.set(qn("w:val"), {
                WD_ALIGN_PARAGRAPH.CENTER: "center",
                WD_ALIGN_PARAGRAPH.LEFT: "left",
                WD_ALIGN_PARAGRAPH.RIGHT: "right",
                WD_ALIGN_PARAGRAPH.JUSTIFY: "both",
            }.get(alignment, "left"))

        for r in p.findall(qn("w:r")):
            rPr = r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                r.insert(0, rPr)

            if font_name:
                rFonts = rPr.find(qn("w:rFonts"))
                if rFonts is None:
                    rFonts = OxmlElement("w:rFonts")
                    rPr.insert(0, rFonts)
                rFonts.set(qn("w:ascii"), font_name)
                rFonts.set(qn("w:eastAsia"), font_name)
                rFonts.set(qn("w:hAnsi"), font_name)
                for attr in (qn("w:asciiTheme"), qn("w:eastAsiaTheme"),
                             qn("w:hAnsiTheme"), qn("w:cstheme")):
                    if attr in rFonts.attrib:
                        del rFonts.attrib[attr]

            if font_size_pt is not None:
                sz = rPr.find(qn("w:sz"))
                if sz is None:
                    sz = OxmlElement("w:sz")
                    rPr.append(sz)
                sz.set(qn("w:val"), str(int(font_size_pt * 2)))
                szCs = rPr.find(qn("w:szCs"))
                if szCs is not None:
                    rPr.remove(szCs)

            if bold is not None:
                existing_b = rPr.find(qn("w:b"))
                if bold:
                    if existing_b is None:
                        rPr.append(OxmlElement("w:b"))
                elif existing_b is not None:
                    rPr.remove(existing_b)


def _apply_three_line_border(table: object, tc: dict) -> None:
    """对整个表格应用三线表边框"""
    tbl = table._tbl  # type: ignore[attr-defined]
    rows = list(tbl.findall(qn("w:tr")))

    # 1) 表级属性：四边无边框 + 内无横竖线
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)

    tblBorders = OxmlElement("w:tblBorders")
    _top_cfg = tc.get("border_top", {})
    _btm_cfg = tc.get("border_bottom", {})
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "none")
        b.set(qn("w:sz"), "0")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "auto")
        tblBorders.append(b)
    tblPr.append(tblBorders)

    if not rows:
        return

    # 2) 顶线 → 首行所有单元格的上边框
    top_w = _top_cfg.get("weight", 1.5)
    top_c = _top_cfg.get("color", "black")
    for cell_obj in rows[0].findall(qn("w:tc")):
        _set_cell_border(cell_obj, "top", top_w, top_c)

    # 3) 底线 → 末行所有单元格的下边框
    btm_w = _btm_cfg.get("weight", 1.5)
    btm_c = _btm_cfg.get("color", "black")
    for cell_obj in rows[-1].findall(qn("w:tc")):
        _set_cell_border(cell_obj, "bottom", btm_w, btm_c)

    # 4) 表头下框线 → 首行所有单元格的下边框
    hdr_cfg = tc.get("border_header_bottom", {})
    hdr_w = hdr_cfg.get("weight", 0.75)
    hdr_c = hdr_cfg.get("color", "black")
    for cell_obj in rows[0].findall(qn("w:tc")):
        _set_cell_border(cell_obj, "bottom", hdr_w, hdr_c)

    # 5) 清除其他所有单元格的上下左右边框
    no_h = tc.get("border_horizontal_internal", False)
    no_v = tc.get("border_vertical", False)
    for row_idx, row in enumerate(rows):
        for cell_obj in row.findall(qn("w:tc")):
            if no_h and row_idx > 0:
                _clear_cell_border(cell_obj, "top")
            if no_v:
                _clear_cell_border(cell_obj, "left")
                _clear_cell_border(cell_obj, "right")


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

        # 预处理 Markdown：标准化数学公式定界符
        self._normalize_math_in_file(input_path)
        # 预处理 Markdown：渲染 Mermaid 图表
        self._preprocess_mermaid(input_path)

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

            # 后处理：应用表格样式（仅 docx）
            if output_format == OutputFormat.DOCX and template_slug:
                if on_progress:
                    await on_progress(0.9, "应用表格样式...")
                await loop.run_in_executor(
                    None, self._apply_table_styles, output_path, template_slug
                )

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
            log.error(f"Pandoc 转换失败: {input_path.name} → {output_format.value}: {e}")
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

    # ── 数学公式预处理 ───────────────────────────────────

    @staticmethod
    def _normalize_math_in_file(path: Path) -> None:
        """
        将 Markdown 中 `[ ... ]` 显示公式转为 Pandoc 标准语法 `$$ ... $$`

        Pandoc 只识别 $$...$$ 和 \\[...\\] 作为显示公式，
        许多作者习惯用 [ ... ]，需要提前转换。

        支持两种格式：
        1. 单行：[ I_1 = K_3 I_N ]
        2. 多行：[ \\n content \\n ]
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return

        # 统一换行符（Windows \r\n → \n），否则 $ 锚点不匹配
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        new_text = text

        # ── 多行显示公式 ──
        # 匹配：独占一行的 [ ，到独占一行的 ] ，中间为公式内容
        new_text = re.sub(
            r"^[ \t]*\[[ \t]*$\n(.*?)^[ \t]*\][ \t]*$",
            lambda m: "$$\n" + m.group(1) + "$$",
            new_text,
            flags=re.MULTILINE | re.DOTALL,
        )

        # ── 单行显示公式 ──
        # 匹配：[ math content ] 整个在一行
        new_text = re.sub(
            r"^[ \t]*\[[ \t]*(.+?(?:[_\\{}]|[a-z]+\^|sum|int|lim|prod|frac|sqrt|sin|cos|log).+?)[ \t]*\][ \t]*$",  # noqa: E501
            r"$$ \1 $$",
            new_text,
            flags=re.MULTILINE,
        )

        if new_text != text:
            try:
                path.write_text(new_text, encoding="utf-8")
                log.info(f"已标准化数学公式: {path.name}")
            except OSError:
                pass

    # ── Mermaid 图表预处理 ────────────────────────────────

    @staticmethod
    def _mmdc_config_path() -> Path:
        """Mmdc 无头浏览器配置文件路径"""
        cfg = Path(__file__).resolve().parent.parent.parent / "config" / "mmdc_puppeteer.json"
        if not cfg.exists():
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text(
                json.dumps({
                    "args": ["--no-sandbox", "--disable-setuid-sandbox"],
                }),
                encoding="utf-8",
            )
        return cfg

    @staticmethod
    def _preprocess_mermaid(input_path: Path) -> None:
        """
        将 Markdown 中的 ```mermaid 代码块渲染为图片

        流程：
        1. 扫描文件中的 ```mermaid ... ``` 代码块
        2. 每个代码块生成一个临时 .mmd 文件
        3. 用 mmdc（mermaid-cli）渲染为 PNG
        4. 将原代码块替换为 ![Mermaid diagram](<图片路径>)
        5. 写回文件

        如果 mmdc 不可用或渲染失败，仅记录警告，不阻断转换。
        """
        try:
            text = input_path.read_text(encoding="utf-8")
        except OSError:
            return

        # 匹配 ```mermaid ... ``` 代码块（支持 mermaid / mermaid-example 等变体）
        pattern = re.compile(
            r"```mermaid\w*[ \t]*\n(.*?)```",
            re.DOTALL,
        )

        matches = list(pattern.finditer(text))
        if not matches:
            return

        # 创建临时目录存放中间文件
        tmp_dir = input_path.parent / f".mermaid_{input_path.stem}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        mmdc_cmd = _find_mmdc()
        if mmdc_cmd is None:
            log.warning("mmdc (mermaid-cli) 未安装，跳过 Mermaid 渲染")
            # 清理空目录
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
            return

        config_path = PandocEngine._mmdc_config_path()

        new_text = text
        # 倒序替换，避免位置偏移
        for idx, m in enumerate(reversed(matches)):
            code_content = m.group(1).strip()
            if not code_content:
                # 空代码块，替换为空行
                start, end = m.start(), m.end()
                new_text = new_text[:start] + "\n" + new_text[end:]
                continue

            mmd_file = tmp_dir / f"diagram_{idx}.mmd"
            png_file = tmp_dir / f"diagram_{idx}.png"

            try:
                mmd_file.write_text(code_content, encoding="utf-8")

                subprocess.run(
                    [*mmdc_cmd, "-i", str(mmd_file), "-o", str(png_file),
                     "-b", "transparent", "-s", "2",
                     "-p", str(config_path)],
                    capture_output=True, timeout=30, check=False,
                )

                if png_file.exists():
                    # 相对路径（相对于输入文件所在目录）
                    rel_path = png_file.relative_to(input_path.parent)
                    img_md = f"![Mermaid diagram]({rel_path.as_posix()})\n"
                    start, end = m.start(), m.end()
                    new_text = new_text[:start] + img_md + new_text[end:]
                    log.info(f"Mermaid 图表 #{idx} 渲染成功: {png_file.name}")
                else:
                    log.warning(f"Mermaid 图表 #{idx} 渲染失败，保留原文")
            except (subprocess.TimeoutExpired, OSError) as e:
                log.warning(f"Mermaid 图表 #{idx} 渲染异常: {e}，保留原文")

        if new_text != text:
            try:
                input_path.write_text(new_text, encoding="utf-8")
                log.info(f"Mermaid 预处理完成，共处理 {len(matches)} 个图表")
            except OSError:
                pass

    # ── 表格样式后处理 ─────────────────────────────────────

    def _apply_table_styles(self, docx_path: Path, slug: str) -> None:
        """对 docx 中所有表格应用模板的 table 样式配置"""
        tc = self._template_mgr.get_table_config(slug)
        if not tc:
            log.debug(f"模板 '{slug}' 无表格样式配置，跳过")
            return

        try:
            doc = Document(str(docx_path))
        except Exception as e:
            log.warning(f"无法打开 docx 应用表格样式: {e}")
            return

        tables = doc.tables
        if not tables:
            return

        log.info(f"模板 '{slug}' 表格样式: 共 {len(tables)} 个表格")

        # 字体/字号解析
        font_name = str(tc.get("font", "")).strip() or None
        font_size_pt = _parse_size(tc.get("size", "")) if tc.get("size") else None

        # 段落格式
        align = ALIGN_MAP.get(str(tc.get("alignment", "")).strip())

        # 表头样式
        hdr_font = str(tc.get("header_font", "")).strip() or font_name
        header_size = tc.get("header_size")
        hdr_size_pt = _parse_size(header_size) if header_size else font_size_pt
        hdr_bold = tc.get("header_bold", False)
        hdr_align = ALIGN_MAP.get(str(tc.get("header_alignment", "")).strip(), align)
        hdr_bg = str(tc.get("header_background", "")).strip() or None

        # 表体样式
        body_font = str(tc.get("body_font", "")).strip() or font_name
        body_size_pt = _parse_size(tc.get("body_size", "")) if tc.get("body_size") else font_size_pt
        body_align = ALIGN_MAP.get(str(tc.get("body_alignment", "")).strip(), align)

        # 单元格内边距
        pad = tc.get("cell_padding", {})
        pad_top = pad.get("top", 2)
        pad_bot = pad.get("bottom", 2)
        pad_left = pad.get("left", 4)
        pad_right = pad.get("right", 4)

        # 斑马纹
        stripe = tc.get("stripe_rows", False)
        stripe_color = str(tc.get("stripe_color", "")).strip() or None

        for table in tables:
            rows = table.rows
            if not rows:
                continue

            # 三线表边框
            if tc.get("border_style") == "three_line_table":
                _apply_three_line_border(table, tc)

            for row_idx, row in enumerate(rows):
                is_header = (row_idx == 0)
                cells = row.cells

                for cell in cells:
                    # 内边距
                    _set_cell_margins(cell, pad_top, pad_bot, pad_left, pad_right)

                    if is_header:
                        # 表头
                        _apply_cell_text_format(
                            cell,
                            font_name=hdr_font,
                            font_size_pt=hdr_size_pt,
                            bold=hdr_bold,
                            alignment=hdr_align,
                        )
                        if hdr_bg:
                            _set_cell_shading(cell, hdr_bg)
                    else:
                        # 表体
                        _apply_cell_text_format(
                            cell,
                            font_name=body_font,
                            font_size_pt=body_size_pt,
                            bold=None,
                            alignment=body_align,
                        )
                        # 斑马纹
                        if stripe and stripe_color and row_idx % 2 == 0:
                            _set_cell_shading(cell, stripe_color)

        try:
            doc.save(str(docx_path))
        except Exception as e:
            log.warning(f"保存 docx 表格样式失败: {e}")


def _find_mmdc() -> list[str] | None:
    """查找可用的 mmdc 命令（npx / 全局安装），返回命令前缀列表"""
    # 优先使用 npx（自动下载）
    try:
        result = subprocess.run(
            ["npx", "--yes", "@mermaid-js/mermaid-cli", "--version"],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            return ["npx", "-y", "@mermaid-js/mermaid-cli"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 尝试全局安装的 mmdc
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return ["mmdc"]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None
