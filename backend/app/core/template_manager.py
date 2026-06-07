"""模版加载与管理"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.log import log
from app.models.templates import ConversionOptions, TemplateInfo
from config.paths import TEMPLATES_DIR


class TemplateManager:
    """模版管理器 — 扫描、加载、组装 Pandoc 参数"""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or TEMPLATES_DIR

    def list_templates(self) -> list[TemplateInfo]:
        """列出所有可用模版"""
        templates: list[TemplateInfo] = []

        if not self._dir.exists():
            log.warning(f"模版目录不存在: {self._dir}")
            return templates

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            info = self._load_template(entry)
            if info:
                templates.append(info)

        return templates

    def get_template(self, slug: str) -> TemplateInfo | None:
        """根据 slug 获取模版信息"""
        template_dir = self._dir / slug
        if not template_dir.is_dir():
            return None
        return self._load_template(template_dir)

    def build_extra_args(self, options: ConversionOptions | None = None) -> list[str]:
        """
        组装 Pandoc extra_args

        根据模版 slug 和高级选项生成完整参数列表：
        --reference-doc / --lua-filter / --toc / --metadata
        """
        if options is None:
            options = ConversionOptions()

        args: list[str] = []
        template_dir = self._dir / options.template_slug

        if template_dir.is_dir():
            # reference doc
            ref_path = template_dir / "reference.docx"
            if ref_path.exists():
                args.extend(["--reference-doc", str(ref_path.resolve())])

            # lua filters
            filters_dir = template_dir / "filters"
            if filters_dir.is_dir():
                for lua_file in sorted(filters_dir.glob("*.lua")):
                    args.extend(["--lua-filter", str(lua_file.resolve())])

        # toc
        if options.toc:
            args.append("--toc")
            args.extend(["--toc-depth", str(options.toc_depth)])

        # metadata
        for key, value in options.metadata.items():
            args.extend(["--metadata", f"{key}={value}"])

        return args

    def _load_template(self, template_dir: Path) -> TemplateInfo | None:
        """从目录加载单个模版"""
        yaml_path = template_dir / "template.yaml"
        if not yaml_path.exists():
            log.debug(f"跳过无 template.yaml 的目录: {template_dir.name}")
            return None

        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as e:
            log.warning(f"解析 template.yaml 失败: {yaml_path} — {e}")
            return None

        ref_doc = (template_dir / "reference.docx").exists()
        filters_dir = template_dir / "filters"
        has_filters = filters_dir.is_dir() and any(filters_dir.glob("*.lua"))

        return TemplateInfo(
            slug=data.get("slug", template_dir.name),
            name=data.get("name", template_dir.name),
            version=data.get("version", "unknown"),
            description=data.get("description", ""),
            author=data.get("author", "MarkFlow"),
            target_formats=data.get("target_formats", ["docx"]),
            has_reference_doc=ref_doc,
            has_lua_filters=has_filters,
        )
