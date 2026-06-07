"""模版管理单元测试"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest
import yaml

from app.core.template_manager import TemplateManager
from app.models.templates import ConversionOptions, TemplateInfo


class TestTemplateInfo:
    def test_default_values(self) -> None:
        info = TemplateInfo(
            slug="test",
            name="Test Template",
            version="1.0",
            description="desc",
        )
        assert info.author == "MarkFlow"
        assert info.target_formats == ["docx"]
        assert info.has_reference_doc is False
        assert info.has_lua_filters is False

    def test_serialization(self) -> None:
        info = TemplateInfo(
            slug="academic",
            name="学术论文",
            version="1.0",
            description="中文学术论文模版",
            has_reference_doc=True,
        )
        data = info.model_dump()
        assert data["slug"] == "academic"
        assert data["has_reference_doc"] is True


class TestConversionOptions:
    def test_defaults(self) -> None:
        opts = ConversionOptions()
        assert opts.template_slug == "minimal"
        assert opts.toc is False
        assert opts.toc_depth == 3
        assert opts.metadata == {}

    def test_custom(self) -> None:
        opts = ConversionOptions(
            template_slug="academic",
            toc=True,
            toc_depth=4,
            metadata={"author": "张三", "title": "论文标题"},
        )
        assert opts.toc is True
        assert opts.toc_depth == 4
        assert opts.metadata["author"] == "张三"


class TestTemplateManager:
    @pytest.fixture
    def tmp_templates(self) -> Generator[Path, None, None]:
        """创建临时模版目录用于测试"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            # 创建一个有效模版
            tpl_dir = base / "test-tpl"
            tpl_dir.mkdir()
            tpl_dir.joinpath("template.yaml").write_text(
                yaml.dump(
                    {
                        "name": "测试模版",
                        "slug": "test-tpl",
                        "version": "1.0",
                        "description": "单元测试模版",
                        "target_formats": ["docx"],
                    }
                ),
                encoding="utf-8",
            )
            tpl_dir.joinpath("reference.docx").write_text("mock docx")

            # 创建一个无 template.yaml 的目录（应被跳过）
            empty_dir = base / "no-yaml"
            empty_dir.mkdir()

            yield base

    def test_list_templates(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        templates = mgr.list_templates()
        assert len(templates) == 1
        assert templates[0].slug == "test-tpl"
        assert templates[0].has_reference_doc is True

    def test_get_template_found(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        tpl = mgr.get_template("test-tpl")
        assert tpl is not None
        assert tpl.name == "测试模版"

    def test_get_template_not_found(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        assert mgr.get_template("nonexistent") is None

    def test_build_extra_args_minimal(self, tmp_templates: Path) -> None:
        """无模版参数 - 只加载用户传入的 args"""
        mgr = TemplateManager(tmp_templates)
        opts = ConversionOptions(template_slug="minimal")
        args = mgr.build_extra_args(opts)
        assert isinstance(args, list)

    def test_build_extra_args_with_toc(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        opts = ConversionOptions(toc=True, toc_depth=2)
        args = mgr.build_extra_args(opts)
        assert "--toc" in args
        assert "--toc-depth" in args
        assert "2" in args

    def test_build_extra_args_with_metadata(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        opts = ConversionOptions(metadata={"author": "张三"})
        args = mgr.build_extra_args(opts)
        assert "--metadata" in args
        assert "author=张三" in args

    def test_build_extra_args_with_reference_doc(self, tmp_templates: Path) -> None:
        mgr = TemplateManager(tmp_templates)
        opts = ConversionOptions(template_slug="test-tpl")
        args = mgr.build_extra_args(opts)
        assert "--reference-doc" in args

    def test_list_templates_empty_dir(self, tmp_templates: Path) -> None:
        """空目录不应报错"""
        mgr = TemplateManager(Path("/nonexistent/dir"))
        templates = mgr.list_templates()
        assert templates == []


class TestBuiltinTemplates:
    """验证内建模版完整性"""

    def test_builtin_templates_exist(self) -> None:
        mgr = TemplateManager()
        templates = mgr.list_templates()
        slugs = {t.slug for t in templates}
        assert "minimal" in slugs
        assert "academic" in slugs
        assert "report" in slugs

    def test_builtin_templates_have_reference_doc(self) -> None:
        mgr = TemplateManager()
        for t in mgr.list_templates():
            assert t.has_reference_doc, f"{t.slug} 缺少 reference.docx"
