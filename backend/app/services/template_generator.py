"""模板生成服务 — 从样式配置生成 reference.docx"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from shutil import rmtree

import yaml
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from config.paths import TEMPLATES_DIR

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

HEX_COLOR_LEN = 6


class TemplateGenerator:
    """根据样式配置生成 reference.docx"""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or TEMPLATES_DIR

    # ---- 公共接口 ----

    def generate_reference(self, styles_config: dict) -> bytes:
        """从样式配置字典直接生成 reference.docx，返回文档字节流"""
        return self._do_generate(styles_config)

    def generate_from_yaml(self, template_dir: Path) -> bytes | None:
        """从已有模板目录的 template.yaml 生成 reference.docx"""
        yaml_path = template_dir / "template.yaml"
        if not yaml_path.exists():
            return None
        cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        styles_cfg = cfg.get("styles", {})
        if not styles_cfg:
            return None
        return self._do_generate(styles_cfg)

    def save_custom_template(  # noqa: PLR0913
        self,
        name: str,
        slug: str,
        styles_config: dict,
        description: str = "",
        author: str = "MarkFlow",
        target_formats: list[str] | None = None,
        version: str = "1.0.0",
    ) -> Path:
        """
        保存自定义模板：生成 reference.docx 并写入 template.yaml

        Args:
            name: 模板显示名称
            slug: 唯一标识符（目录名）
            styles_config: 样式配置（与 template.yaml 的 styles 部分结构一致）
            description: 模板描述
            author: 作者
            target_formats: 目标格式列表
            version: 版本号

        Returns:
            模板目录路径

        """
        custom_dir = self._dir / "custom" / slug
        custom_dir.mkdir(parents=True, exist_ok=True)

        # 生成 reference.docx
        ref_bytes = self.generate_reference(styles_config)
        ref_path = custom_dir / "reference.docx"
        ref_path.write_bytes(ref_bytes)

        # 写入 template.yaml
        config: dict = {
            "name": name,
            "slug": slug,
            "version": version,
            "description": description or f"自定义模板 - {name}",
            "author": author,
            "target_formats": target_formats or ["docx"],
            "styles": styles_config,
        }
        yaml_path = custom_dir / "template.yaml"
        yaml_path.write_text(
            yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        return custom_dir

    def delete_custom_template(self, slug: str) -> bool:
        """删除自定义模板目录"""
        target = self._dir / "custom" / slug
        if not target.exists() or not target.is_dir():
            return False

        rmtree(target)
        return True

    def list_custom_templates(self) -> list[dict]:
        """列出 custom/ 下所有自定义模板"""
        custom_dir = self._dir / "custom"
        if not custom_dir.exists():
            return []
        results: list[dict] = []
        for entry in sorted(custom_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            yaml_path = entry / "template.yaml"
            if not yaml_path.exists():
                continue
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, OSError):
                continue
            has_ref = (entry / "reference.docx").exists()
            results.append(
                {
                    "slug": data.get("slug", entry.name),
                    "name": data.get("name", entry.name),
                    "version": data.get("version", "1.0.0"),
                    "description": data.get("description", ""),
                    "author": data.get("author", "MarkFlow"),
                    "target_formats": data.get("target_formats", ["docx"]),
                    "has_reference_doc": has_ref,
                    "is_custom": True,
                }
            )
        return results

    # ---- 内部实现 ----

    def _do_generate(self, styles_cfg: dict) -> bytes:
        """核心：用样式配置生成 reference.docx 并返回字节流"""
        doc = Document()

        # 确保 Code 样式存在
        try:
            doc.styles["Code"]
        except KeyError:
            doc.styles.add_style("Code", style_type=1)

        # 确保 Caption 样式存在
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
                # 样式不存在时创建（如 Heading 4/5/6 python-docx 默认不提供）
                style = doc.styles.add_style(word_style_name, 1)  # 1 = WD_STYLE_TYPE.PARAGRAPH
                # 设置标题大纲级别，使 Word 正确识别标题层级
                if word_style_name.startswith("Heading "):
                    try:
                        level = int(word_style_name.split()[1]) - 1
                        pPr = style.element.get_or_add_pPr()
                        outline_lvl = OxmlElement("w:outlineLvl")
                        outline_lvl.set(qn("w:val"), str(level))
                        pPr.append(outline_lvl)
                    except (ValueError, IndexError):
                        pass
            self._apply_font(style, sc)
            # Normal 不设置首行缩进（由 Body Text 样式处理）
            sc_para = dict(sc)
            if yaml_key == "body":
                sc_para.pop("first_line_indent", None)
            self._apply_para(style, sc_para)

        # Body Text：字体同 Normal + 首行缩进
        body_cfg = styles_cfg.get("body", {})
        indent_str = str(body_cfg.get("first_line_indent", "2 字符"))
        num_str = "".join(c for c in indent_str if c.isdigit() or c == ".")
        if num_str:
            twips = int(float(num_str) * 0.5 * 567)
            bt = doc.styles["Body Text"]
            bt_el = bt.element
            # 设置字体
            rpr = bt_el.get_or_add_rPr()
            rfonts = bt_el.makeelement(
                qn("w:rFonts"),
                {
                    qn("w:ascii"): body_cfg.get("font", "宋体"),
                    qn("w:eastAsia"): body_cfg.get("font", "宋体"),
                    qn("w:hAnsi"): body_cfg.get("font", "宋体"),
                },
            )
            rpr.insert(0, rfonts)
            # 设置首行缩进
            ppr = bt_el.get_or_add_pPr()
            ind_el = bt_el.makeelement(qn("w:ind"), {qn("w:firstLine"): str(twips)})
            ppr.append(ind_el)

        # Caption 样式
        table_cfg = styles_cfg.get("table", {})
        cap_font = table_cfg.get("caption_font", "")
        cap_size = table_cfg.get("caption_size", "")
        cap_bold = table_cfg.get("caption_bold", False)
        if cap_font or cap_size:
            try:
                cap_style = doc.styles["Caption"]
                self._apply_font(cap_style, {"font": cap_font, "size": cap_size, "bold": cap_bold})
                cap_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_style.paragraph_format.first_line_indent = Pt(0)
            except KeyError:
                pass

        # 保存到字节流

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()

    # ---- 样式应用工具方法 ----

    @staticmethod
    def _parse_size(raw: str | float) -> float | None:
        """解析字号：中文号数 / pt数字 / 字符串数值"""
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

    @staticmethod
    def _parse_color(raw: str | None) -> RGBColor | None:
        if not raw:
            return None
        raw = raw.strip().lstrip("#")
        if len(raw) == HEX_COLOR_LEN:
            return RGBColor(*[int(raw[i : i + 2], 16) for i in (0, 2, 4)])
        return None

    @staticmethod
    def _apply_font(style, config: dict) -> None:
        font = style.font
        name = config.get("font", "").strip()
        if name:
            font.name = name
            rpr = style.element.get_or_add_rPr()
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is None:
                rfonts = style.element.makeelement(qn("w:rFonts"), {})
                rpr.insert(0, rfonts)
            rfonts.set(qn("w:ascii"), name)
            rfonts.set(qn("w:eastAsia"), name)
            rfonts.set(qn("w:hAnsi"), name)
            theme_attrs = [
                qn("w:asciiTheme"),
                qn("w:eastAsiaTheme"),
                qn("w:hAnsiTheme"),
                qn("w:cstheme"),
            ]
            for attr in theme_attrs:
                if attr in rfonts.attrib:
                    del rfonts.attrib[attr]

        size_raw = config.get("size")
        size_pt = (
            TemplateGenerator._parse_size(size_raw)
            if isinstance(size_raw, (str, float, int))
            else None
        )
        if size_pt:
            font.size = Pt(size_pt)
            rpr = style.element.find(qn("w:rPr"))
            if rpr is not None:
                szcs = rpr.find(qn("w:szCs"))
                if szcs is not None:
                    rpr.remove(szcs)

        if config.get("bold"):
            font.bold = True
        else:
            rpr = style.element.find(qn("w:rPr"))
            if rpr is not None:
                b = rpr.find(qn("w:b"))
                if b is not None:
                    rpr.remove(b)

        color = TemplateGenerator._parse_color(config.get("color"))
        if color:
            font.color.rgb = color
        else:
            rpr = style.element.find(qn("w:rPr"))
            if rpr is not None:
                c = rpr.find(qn("w:color"))
                if c is not None:
                    rpr.remove(c)

    @staticmethod
    def _apply_para(style, config: dict) -> None:
        pf = style.paragraph_format

        if "alignment" in config:
            al = ALIGN_MAP.get(config["alignment"])
            if al:
                pf.alignment = al

        for key, attr in [("space_before", "space_before"), ("space_after", "space_after")]:
            raw = config.get(key)
            if raw is None:
                continue
            s = str(raw).strip()
            num_str = "".join(c for c in s if c.isdigit() or c == ".")
            if not num_str:
                continue
            num = float(num_str)
            if "pt" in s.lower():
                setattr(pf, attr, Pt(num))
            elif "倍" in s or "行" in s:
                setattr(pf, attr, Pt(num * 12))
            else:
                setattr(pf, attr, Pt(num))

        ls = config.get("line_spacing")
        if ls is not None:
            pf.line_spacing = float(ls)

        indent = config.get("first_line_indent")
        if indent:
            s = str(indent).strip()
            num_str = "".join(c for c in s if c.isdigit() or c == ".")
            if num_str:
                num = float(num_str)
                if "字符" in s or "em" in s.lower():
                    pf.first_line_indent = Cm(num * 0.5)
                else:
                    pf.first_line_indent = Pt(num)
