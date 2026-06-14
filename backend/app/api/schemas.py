"""请求/响应 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.version import APP_VERSION


# ========== 健康检查 ==========
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = APP_VERSION


# ========== Mermaid 渲染器状态 ==========
class MermaidStatusResponse(BaseModel):
    chromium_ready: bool = False  # Edge 就绪（兼容旧字段名）
    mermaid_js_loaded: bool = False
    mermaid_available: bool = False
    diagnostic: str = ""


# ========== 转换 ==========
class ConvertResponse(BaseModel):
    task_id: str
    status: str
    message: str


# ========== 任务状态 ==========
class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: float


# ========== 错误 ==========
class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["文件过大 / 格式不支持 / 任务不存在"])


# ========== 模版列表 ==========
class TemplateItem(BaseModel):
    slug: str
    name: str
    version: str
    description: str
    author: str
    target_formats: list[str]
    has_reference_doc: bool
    has_lua_filters: bool
    is_custom: bool = False


class TemplateListResponse(BaseModel):
    templates: list[TemplateItem]


# ========== 自定义模版生成 ==========
class StyleConfig(BaseModel):
    """单个样式配置（如 heading1, body, code 等）"""

    font: str | None = None
    size: str | None = None
    bold: bool | None = None
    color: str | None = None
    alignment: str | None = None
    space_before: str | None = None
    space_after: str | None = None
    line_spacing: float | None = None
    first_line_indent: str | None = None
    background: str | None = None


class TableStyleConfig(BaseModel):
    """表格样式配置"""

    font: str | None = None
    size: str | None = None
    line_spacing: float | None = None
    alignment: str | None = None
    first_line_indent: str | None = None
    space_before: str | None = None
    space_after: str | None = None
    header_font: str | None = None
    header_size: str | None = None
    header_bold: bool | None = None
    header_alignment: str | None = None
    header_background: str | None = None
    body_font: str | None = None
    body_size: str | None = None
    body_alignment: str | None = None
    caption_font: str | None = None
    caption_size: str | None = None
    caption_bold: bool | None = None


class TemplateGenerateRequest(BaseModel):
    """模版生成请求"""

    name: str = Field(..., description="模版显示名称")
    slug: str = Field(..., description="模版唯一标识符", pattern=r"^[a-z0-9_-]+$")
    description: str = ""
    author: str = "MarkFlow"
    target_formats: list[str] = Field(default_factory=lambda: ["docx"])
    version: str = "1.0.0"
    styles: dict[str, StyleConfig | TableStyleConfig] = Field(
        ..., description="样式配置，key 为 heading1/heading2/heading3/heading4/body/code/table"
    )


class TemplateGenerateResponse(BaseModel):
    """模版生成响应"""

    slug: str
    name: str
    path: str


# ========== 日志 ==========
class LogEntryResponse(BaseModel):
    """单条日志响应"""

    timestamp: str
    level: str
    message: str
    source: str


class LogListResponse(BaseModel):
    """日志列表响应"""

    logs: list[LogEntryResponse]
    total: int


# ========== Pandoc 状态 ==========
class PandocStatusResponse(BaseModel):
    """Pandoc 模块状态响应"""

    available: bool = False
    version: str = ""
    installer_found: bool = False
    installer_path: str = ""


# ========== 模块状态 ==========
class ModuleStatusResponse(BaseModel):
    """模块状态统一响应"""

    id: str
    available: bool
    version: str = ""
    installer_found: bool = False
