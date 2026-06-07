"""API 路由"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.api.log import log
from app.api.schemas import (
    ConvertResponse,
    HealthResponse,
    TaskStatusResponse,
    TemplateItem,
    TemplateListResponse,
)
from app.core.template_manager import TemplateManager
from app.models.models import ConversionStatus, OutputFormat
from app.services.converter import ConversionService

router = APIRouter()

# ---- 单例（由 main.py 注入） ----
_conv_service: ConversionService | None = None
_template_mgr: TemplateManager | None = None


def init(svc: ConversionService, mgr: TemplateManager) -> None:
    """初始化全局服务实例"""
    global _conv_service, _template_mgr
    _conv_service = svc
    _template_mgr = mgr


def get_svc() -> ConversionService:
    if _conv_service is None:
        raise RuntimeError("ConversionService 未初始化")
    return _conv_service


def get_mgr() -> TemplateManager:
    if _template_mgr is None:
        raise RuntimeError("TemplateManager 未初始化")
    return _template_mgr


# ========== 健康检查 ==========
@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


# ========== 模版列表 ==========
@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(mgr: Annotated[TemplateManager, Depends(get_mgr)]) -> TemplateListResponse:
    items = [TemplateItem(**t.model_dump()) for t in mgr.list_templates()]
    return TemplateListResponse(templates=items)


# ========== 文件转换 ==========
@router.post("/convert", response_model=ConvertResponse)
async def convert(
    file: Annotated[UploadFile, File()],
    output_format: Annotated[str, Form()] = "docx",
    template_slug: Annotated[str, Form()] = "minimal",
    toc: Annotated[str, Form()] = "false",
    toc_depth: Annotated[int, Form()] = 3,
    formula_position: Annotated[str, Form()] = "inline",
    keep_separator: Annotated[str, Form()] = "true",
    metadata: Annotated[str | None, Form()] = None,
    svc: Annotated[ConversionService, Depends(get_svc)] = None,
    mgr: Annotated[TemplateManager, Depends(get_mgr)] = None,
) -> ConvertResponse:
    # 解析输出格式
    try:
        fmt = OutputFormat(output_format)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {output_format}")

    # 读取文件
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    # 组装额外参数
    from app.models.templates import ConversionOptions

    options = ConversionOptions(
        template_slug=template_slug,
        toc=(toc.lower() == "true"),
        toc_depth=toc_depth,
        formula_position=formula_position,
        keep_separator=(keep_separator.lower() == "true"),
        metadata=_parse_metadata(metadata),
    )
    extra_args = mgr.build_extra_args(options)
    log.info(f"模版={template_slug}, toc={toc}, formula={formula_position}, keep_sep={keep_separator}, metadata={options.metadata}, args={extra_args}")

    # 提交任务
    filename = file.filename or "input.md"
    task = await svc.submit(content, filename, fmt, extra_args, template_slug)

    # 后台执行
    asyncio.create_task(_run_convert(svc, task.task_id))

    return ConvertResponse(
        task_id=str(task.task_id),
        status=task.status.value,
        message="任务已提交",
    )


# ========== 任务状态 ==========
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    svc: Annotated[ConversionService, Depends(get_svc)],
) -> TaskStatusResponse:
    task = svc.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskStatusResponse(
        task_id=str(task.task_id),
        status=task.status.value,
        progress=task.progress,
    )


# ========== SSE 进度推送 ==========
@router.get("/tasks/{task_id}/progress")
async def stream_progress(
    task_id: UUID,
    svc: Annotated[ConversionService, Depends(get_svc)],
) -> EventSourceResponse:
    async def event_gen():
        while True:
            task = svc.get_task(task_id)
            if task is None:
                yield {"event": "error", "data": "任务不存在"}
                return

            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "progress": task.progress,
                        "status": task.status.value,
                    }
                ),
            }

            if task.status == ConversionStatus.FAILED:
                yield {
                    "event": "error",
                    "data": json.dumps({"detail": task.error or "转换失败"}),
                }
                return
            if task.status == ConversionStatus.COMPLETED:
                yield {
                    "event": "completed",
                    "data": json.dumps({"task_id": str(task_id)}),
                }
                return

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_gen(), ping=5)


# ========== 下载结果 ==========
@router.get("/tasks/{task_id}/download")
async def download_result(
    task_id: UUID,
    svc: Annotated[ConversionService, Depends(get_svc)],
) -> FileResponse:
    task = svc.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != ConversionStatus.COMPLETED or task.output_path is None:
        raise HTTPException(status_code=400, detail="任务未完成")
    return FileResponse(
        task.output_path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "inline"},
    )


# ========== 辅助 ==========
async def _run_convert(svc: ConversionService, task_id: UUID) -> None:
    try:
        await svc.execute(task_id)
    except Exception:
        pass  # 错误已标记在 task.status 中


def _parse_metadata(raw: str | None) -> dict[str, str]:
    """解析前端传来的 metadata JSON 字符串或 FormData"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
