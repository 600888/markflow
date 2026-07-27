"""模版数据模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConversionOptions(BaseModel):
    """转换高级选项"""

    template_slug: str = "academic"
    title_page: bool = False
    page_header: str = ""
    toc: bool = False
    toc_depth: int = Field(default=3, ge=1, le=6)
    metadata: dict[str, str] = Field(default_factory=dict)
    formula_position: str = "inline"  # inline | display | smart
    keep_separator: bool = True
    convert_images: bool = True
    convert_mermaid: bool = True


class TemplateInfo(BaseModel):
    """模版元信息"""

    slug: str
    name: str
    version: str
    description: str
    author: str = "MarkFlow"
    target_formats: list[str] = Field(default_factory=lambda: ["docx"])
    has_reference_doc: bool = False
    has_lua_filters: bool = False
    is_custom: bool = False
