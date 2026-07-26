"""模版加载与管理"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.log import log
from app.models.templates import ConversionOptions, TemplateInfo
from config.paths import FILTERS_DIR, TEMPLATES_DIR


class TemplateManager:
    """模版管理器 — 扫描、加载、组装 Pandoc 参数"""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or TEMPLATES_DIR
        self._yaml_cache: dict[str, dict] = {}

    def list_templates(self) -> list[TemplateInfo]:
        """列出所有可用模版（包括内置和自定义）"""
        templates: list[TemplateInfo] = []

        if not self._dir.exists():
            log.warning(f"模版目录不存在: {self._dir}")
            return templates

        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name == "custom":
                # custom 目录下的子目录才是自定义模板
                for sub in sorted(entry.iterdir()):
                    if not sub.is_dir() or sub.name.startswith("."):
                        continue
                    info = self._load_template(sub, is_custom=True)
                    if info:
                        templates.append(info)
                continue
            info = self._load_template(entry, is_custom=False)
            if info:
                templates.append(info)

        return templates

    def get_template(self, slug: str) -> TemplateInfo | None:
        """根据 slug 获取模版信息（内置 > 自定义）"""
        # 先查内置
        template_dir = self._dir / slug
        if template_dir.is_dir():
            return self._load_template(template_dir, is_custom=False)
        # 再查自定义
        custom_dir = self._dir / "custom" / slug
        if custom_dir.is_dir():
            return self._load_template(custom_dir, is_custom=True)
        return None

    def build_extra_args(self, options: ConversionOptions | None = None) -> list[str]:
        """
        组装 Pandoc extra_args

        根据模版 slug 和高级选项生成完整参数列表：
        --reference-doc / --lua-filter / --toc / --metadata
        """
        if options is None:
            options = ConversionOptions()

        args: list[str] = []
        template_dir = self._resolve_template_dir(options.template_slug)

        if template_dir is not None:
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
        metadata = dict(options.metadata)
        if options.toc:
            metadata.setdefault("toc-title", "目录")
        for key, value in metadata.items():
            args.extend(["--metadata", f"{key}={value}"])

        # 公式位置过滤器
        if options.formula_position != "smart":
            formula_filter = FILTERS_DIR / "formula_position.lua"
            if formula_filter.exists():
                args.extend(["--lua-filter", str(formula_filter.resolve())])
                args.extend(["--metadata", f"formula-position={options.formula_position}"])

        # 分割线过滤器
        if not options.keep_separator:
            hrule_filter = FILTERS_DIR / "remove_hrule.lua"
            if hrule_filter.exists():
                args.extend(["--lua-filter", str(hrule_filter.resolve())])

        return args

    def get_table_config(self, slug: str) -> dict | None:
        """获取模板的表格样式配置（styles.table）"""
        data = self._yaml_cache.get(slug)
        if data is None:
            data = self._load_yaml(slug)
            if data:
                self._yaml_cache[slug] = data
        if data is None:
            return None
        return data.get("styles", {}).get("table")

    def _load_yaml(self, slug: str) -> dict | None:
        """按 slug 加载 template.yaml（内置 > 自定义）"""
        # 先查内置
        yaml_path = self._dir / slug / "template.yaml"
        if yaml_path.exists():
            try:
                return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, OSError):
                return None
        # 再查自定义
        custom_path = self._dir / "custom" / slug / "template.yaml"
        if custom_path.exists():
            try:
                return yaml.safe_load(custom_path.read_text(encoding="utf-8"))
            except (yaml.YAMLError, OSError):
                return None
        return None

    def _resolve_template_dir(self, slug: str) -> Path | None:
        """查找模板目录（内置 > 自定义）"""
        builtin = self._dir / slug
        if builtin.is_dir():
            return builtin
        custom = self._dir / "custom" / slug
        if custom.is_dir():
            return custom
        return None

    def _load_template(self, template_dir: Path, *, is_custom: bool = False) -> TemplateInfo | None:
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

        # 缓存完整 YAML 供后续查询表格样式等
        self._yaml_cache[data.get("slug", template_dir.name)] = data

        return TemplateInfo(
            slug=data.get("slug", template_dir.name),
            name=data.get("name", template_dir.name),
            version=data.get("version", "unknown"),
            description=data.get("description", ""),
            author=data.get("author", "MarkFlow"),
            target_formats=data.get("target_formats", ["docx"]),
            has_reference_doc=ref_doc,
            has_lua_filters=has_filters,
            is_custom=is_custom,
        )
