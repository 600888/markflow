"""
从 template.yaml 自动生成 reference.docx
用法: python scripts/generate_reference.py [slug...]
示例: python scripts/generate_reference.py academic report
      不带参数则生成全部模版
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# 中文号数 → pt 映射
SIZE_MAP: dict[str, float] = {
    "初号": 42,
    "小初": 36,
    "一号": 26,
    "小一": 24,
    "二号": 22,
    "小二": 18,
    "三号": 16,
    "小三": 15,
    "四号": 14,
    "小四": 12,
    "五号": 10.5,
    "小五": 9,
    "六号": 7.5,
    "小六": 6.5,
    "七号": 5.5,
    "八号": 5,
}

# 段落对齐映射
ALIGN_MAP: dict[str, WD_ALIGN_PARAGRAPH] = {
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

# style.yaml → Word 样式名
STYLE_MAP = {
    "heading1": "Heading 1",
    "heading2": "Heading 2",
    "heading3": "Heading 3",
    "heading4": "Heading 4",
    "body": "Normal",
    "code": "Code",
}

# 正文缩进样式（Lua filter 将正文映射到此样式）
BODY_TEXT_STYLE = "Body Text"


def parse_size(raw: str | float) -> float | None:
    """解析字号：中文号数 / pt数字 / 字符串数值"""
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if s in SIZE_MAP:
        return SIZE_MAP[s]
    # 尝试直接转数字（如 "12pt" → 12）
    num = "".join(c for c in s if c.isdigit() or c == ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_color(raw: str | None) -> RGBColor | None:
    if not raw:
        return None
    raw = raw.strip().lstrip("#")
    if len(raw) == 6:
        return RGBColor(*[int(raw[i : i + 2], 16) for i in (0, 2, 4)])  # type: ignore[no-any-return]
    return None


def apply_font(style, config: dict) -> None:
    font = style.font
    name = config.get("font", "").strip()
    if name:
        font.name = name
        # 在样式 xml 中设置 w:ascii / w:eastAsia / w:hAnsi
        rPr = style.element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = style.element.makeelement(qn("w:rFonts"), {})
            rPr.insert(0, rFonts)
        # 三个属性全部设为同一字体，确保中英文都生效
        rFonts.set(qn("w:ascii"), name)
        rFonts.set(qn("w:eastAsia"), name)
        rFonts.set(qn("w:hAnsi"), name)
        # 清除主题字体引用（否则会覆盖我们的设置）
        theme_attrs = [
            qn("w:asciiTheme"),
            qn("w:eastAsiaTheme"),
            qn("w:hAnsiTheme"),
            qn("w:cstheme"),
        ]
        for attr in theme_attrs:
            if attr in rFonts.attrib:
                del rFonts.attrib[attr]

    size_raw = config.get("size")
    size_pt = parse_size(size_raw) if isinstance(size_raw, (str, float, int)) else None
    if size_pt:
        font.size = Pt(size_pt)
        # 同时清除 szCs（复杂脚本字号，可能覆盖 sz）
        rPr = style.element.find(qn("w:rPr"))
        if rPr is not None:
            szCs = rPr.find(qn("w:szCs"))
            if szCs is not None:
                rPr.remove(szCs)

    if config.get("bold"):
        font.bold = True
    else:
        rPr = style.element.find(qn("w:rPr"))
        if rPr is not None:
            b = rPr.find(qn("w:b"))
            if b is not None:
                rPr.remove(b)

    color = parse_color(config.get("color"))
    if color:
        font.color.rgb = color
    else:
        # 清除主题颜色（Heading 样式默认有蓝色）
        rPr = style.element.find(qn("w:rPr"))
        if rPr is not None:
            c = rPr.find(qn("w:color"))
            if c is not None:
                rPr.remove(c)


def apply_para(style, config: dict) -> None:
    pf = style.paragraph_format

    if "alignment" in config:
        al = ALIGN_MAP.get(config["alignment"])
        if al:
            pf.alignment = al

    # 段前/段后 — 支持 "12pt" 或 "1.5 倍行距" 等形式
    for key, attr in [("space_before", "space_before"), ("space_after", "space_after")]:
        raw = config.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        # 提取数字
        num_str = "".join(c for c in s if c.isdigit() or c == ".")
        if not num_str:
            continue
        num = float(num_str)
        if "pt" in s.lower():
            setattr(pf, attr, Pt(num))
        elif "倍" in s or "行" in s:
            setattr(pf, attr, Pt(num * 12))  # 近似 1 倍 ≈ 12pt
        else:
            setattr(pf, attr, Pt(num))

    # 行距
    ls = config.get("line_spacing")
    if ls is not None:
        pf.line_spacing = float(ls)

    # 首行缩进
    indent = config.get("first_line_indent")
    if indent:
        s = str(indent).strip()
        num_str = "".join(c for c in s if c.isdigit() or c == ".")
        if num_str:
            num = float(num_str)
            if "字符" in s or "em" in s.lower():
                pf.first_line_indent = Cm(num * 0.5)  # 1 字符 ≈ 0.5cm
            else:
                pf.first_line_indent = Pt(num)


def build_reference(template_dir: Path) -> None:
    yaml_path = template_dir / "template.yaml"
    if not yaml_path.exists():
        print(f"  [WARN] no template.yaml, skip {template_dir.name}")
        return

    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    styles_cfg = cfg.get("styles", {})
    if not styles_cfg:
        print(f"  [WARN] no styles, skip {template_dir.name}")
        return

    doc = Document()

    # 确保 Code 样式存在（非 Word 内建，Pandoc 需要）
    try:
        doc.styles["Code"]
    except KeyError:
        doc.styles.add_style("Code", style_type=1)  # WD_STYLE_TYPE.PARAGRAPH

    # 确保 Caption 样式存在（表格标题用）
    try:
        doc.styles["Caption"]
    except KeyError:
        doc.styles.add_style("Caption", style_type=1)

    for yaml_key, word_style_name in STYLE_MAP.items():
        sc = styles_cfg.get(yaml_key)
        if not sc:
            continue
        try:
            style = doc.styles[word_style_name]
        except KeyError:
            print(f"    [WARN] style '{word_style_name}' missing, skip")
            continue
        apply_font(style, sc)
        # Normal 不设置首行缩进（由 Body Text 样式处理）
        sc_para = dict(sc)
        if yaml_key == "body":
            sc_para.pop("first_line_indent", None)
        apply_para(style, sc_para)

    # Body Text：字体同 Normal + 首行缩进（通过 Lua filter 映射正文段落）
    body_cfg = styles_cfg.get("body", {})
    indent_str = str(body_cfg.get("first_line_indent", "2 字符"))
    num_str = "".join(c for c in indent_str if c.isdigit() or c == ".")
    if num_str:
        twips = int(float(num_str) * 0.5 * 567)
        bt = doc.styles["Body Text"]
        bt_el = bt.element
        # 设置字体
        rPr = bt_el.get_or_add_rPr()
        rFonts = bt_el.makeelement(
            qn("w:rFonts"),
            {
                qn("w:ascii"): body_cfg.get("font", "宋体"),
                qn("w:eastAsia"): body_cfg.get("font", "宋体"),
                qn("w:hAnsi"): body_cfg.get("font", "宋体"),
            },
        )
        rPr.insert(0, rFonts)
        # 设置首行缩进
        pPr = bt_el.get_or_add_pPr()
        ind_el = bt_el.makeelement(qn("w:ind"), {qn("w:firstLine"): str(twips)})
        pPr.append(ind_el)

    # Caption 样式（表格标题）
    table_cfg = styles_cfg.get("table", {})
    cap_font = table_cfg.get("caption_font", "")
    cap_size = table_cfg.get("caption_size", "")
    cap_bold = table_cfg.get("caption_bold", False)
    if cap_font or cap_size:
        try:
            cap_style = doc.styles["Caption"]
            apply_font(cap_style, {"font": cap_font, "size": cap_size, "bold": cap_bold})
            # 标题居中
            cap_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # 清除 Normal 继承的缩进
            cap_style.paragraph_format.first_line_indent = Pt(0)
        except KeyError:
            pass

    ref_path = template_dir / "reference.docx"
    doc.save(str(ref_path))
    print(f"  [OK] {template_dir.name}/reference.docx")


def main() -> None:
    slugs = sys.argv[1:] if len(sys.argv) > 1 else None

    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or entry.name == "custom":
            continue
        if slugs and entry.name not in slugs:
            continue
        slug = entry.name
        print(f"[{slug}]")
        build_reference(entry)

    print("完成")


if __name__ == "__main__":
    main()
