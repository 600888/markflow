"""请求/响应 Schema"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ========== 健康检查 ==========
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


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


class TemplateListResponse(BaseModel):
    templates: list[TemplateItem]
