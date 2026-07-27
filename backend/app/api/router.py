"""API 路由"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse

from app.api.log import log
from app.api.schemas import (
    ConvertResponse,
    HealthResponse,
    LogEntryResponse,
    LogListResponse,
    MermaidRenderRequest,
    MermaidStatusResponse,
    PandocStatusResponse,
    TaskStatusResponse,
    TemplateGenerateRequest,
    TemplateGenerateResponse,
    TemplateItem,
    TemplateListResponse,
)
from app.core.browser_check import edge_manager
from app.core.pandoc_check import pandoc_manager
from app.core.template_manager import TemplateManager
from app.models.models import ConversionStatus, OutputFormat
from app.services.converter import ConversionService
from app.services.log_service import LogService
from app.services.template_generator import TemplateGenerator

router = APIRouter()

# ---- 单例（由 main.py 注入） ----
_conv_service: ConversionService | None = None
_template_mgr: TemplateManager | None = None
_template_gen: TemplateGenerator | None = None
_log_svc: LogService | None = None


def init(
    svc: ConversionService,
    mgr: TemplateManager,
    gen: TemplateGenerator,
    log_svc: LogService | None = None,
) -> None:
    """初始化全局服务实例"""
    global _conv_service, _template_mgr, _template_gen, _log_svc
    _conv_service = svc
    _template_mgr = mgr
    _template_gen = gen
    _log_svc = log_svc


def get_log_svc() -> LogService:
    if _log_svc is None:
        raise RuntimeError("LogService 未初始化")
    return _log_svc


def get_svc() -> ConversionService:
    if _conv_service is None:
        raise RuntimeError("ConversionService 未初始化")
    return _conv_service


def get_mgr() -> TemplateManager:
    if _template_mgr is None:
        raise RuntimeError("TemplateManager 未初始化")
    return _template_mgr


def get_gen() -> TemplateGenerator:
    if _template_gen is None:
        raise RuntimeError("TemplateGenerator 未初始化")
    return _template_gen


# ========== 健康检查 ==========
@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


# ========== Mermaid 渲染器状态 ==========
@router.get("/mermaid-status", response_model=MermaidStatusResponse)
async def mermaid_status() -> MermaidStatusResponse:
    from app.core.mermaid_renderer import _load_mermaid_js, get_diagnostic_message

    js_loaded = bool(_load_mermaid_js())
    edge_ok = edge_manager.check()
    return MermaidStatusResponse(
        chromium_ready=edge_ok,
        mermaid_js_loaded=js_loaded,
        mermaid_available=edge_ok and js_loaded,
        diagnostic=get_diagnostic_message(),
    )


@router.post("/mermaid/render-png")
async def render_mermaid_png(req: MermaidRenderRequest) -> Response:
    from app.core.mermaid_renderer import render_diagram

    with tempfile.TemporaryDirectory(prefix="markflow-mermaid-export-") as temp_dir:
        output_path = Path(temp_dir) / "diagram.png"
        success = await render_diagram(req.source, output_path, theme=req.theme)
        if not success or not output_path.exists():
            raise HTTPException(status_code=503, detail="Mermaid PNG 渲染失败")
        return Response(
            content=output_path.read_bytes(),
            media_type="image/png",
            headers={"Content-Disposition": 'attachment; filename="mermaid-diagram.png"'},
        )


# ========== 模版列表 ==========
@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(mgr: Annotated[TemplateManager, Depends(get_mgr)]) -> TemplateListResponse:
    items = [TemplateItem(**t.model_dump()) for t in mgr.list_templates()]
    return TemplateListResponse(templates=items)


# ========== 自定义模版生成 ==========
@router.post("/templates/generate", response_model=TemplateGenerateResponse)
async def generate_template(
    req: TemplateGenerateRequest,
    gen: Annotated[TemplateGenerator, Depends(get_gen)],
    mgr: Annotated[TemplateManager, Depends(get_mgr)],
) -> TemplateGenerateResponse:
    # 检查 slug 是否已存在（内置或自定义）
    existing = mgr.get_template(req.slug)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"模版 slug '{req.slug}' 已存在")

    # 将 Pydantic models 转为普通 dict（TemplateGenerator 的 styles_config 需要）
    styles_dict: dict = {}
    for key, sc in req.styles.items():
        styles_dict[key] = sc.model_dump(exclude_none=True)

    gen.save_custom_template(
        name=req.name,
        slug=req.slug,
        styles_config=styles_dict,
        description=req.description,
        author=req.author,
        target_formats=req.target_formats,
        version=req.version,
    )

    return TemplateGenerateResponse(
        slug=req.slug,
        name=req.name,
        path=f"custom/{req.slug}",
    )


@router.get("/templates/custom", response_model=TemplateListResponse)
async def list_custom_templates(
    gen: Annotated[TemplateGenerator, Depends(get_gen)],
) -> TemplateListResponse:
    items = gen.list_custom_templates()
    return TemplateListResponse(templates=[TemplateItem(**t) for t in items])


@router.delete("/templates/{slug}")
async def delete_template(
    slug: str,
    gen: Annotated[TemplateGenerator, Depends(get_gen)],
) -> dict:
    # 仅允许删除自定义模版
    custom_gen = gen.list_custom_templates()
    if not any(t["slug"] == slug for t in custom_gen):
        raise HTTPException(status_code=404, detail=f"自定义模版 '{slug}' 不存在")
    gen.delete_custom_template(slug)
    return {"detail": f"模版 '{slug}' 已删除"}


# ========== 文件转换 ==========
@router.post("/convert", response_model=ConvertResponse)
async def convert(
    file: Annotated[UploadFile, File()],
    output_format: Annotated[str, Form()] = "docx",
    template_slug: Annotated[str, Form()] = "academic",
    title_page: Annotated[str, Form()] = "false",
    page_header: Annotated[str, Form()] = "",
    toc: Annotated[str, Form()] = "false",
    toc_depth: Annotated[int, Form()] = 3,
    formula_position: Annotated[str, Form()] = "inline",
    keep_separator: Annotated[str, Form()] = "true",
    convert_images: Annotated[str, Form()] = "true",
    convert_mermaid: Annotated[str, Form()] = "true",
    metadata: Annotated[str | None, Form()] = None,
    svc: Annotated[ConversionService | None, Depends(get_svc)] = None,
    mgr: Annotated[TemplateManager | None, Depends(get_mgr)] = None,
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

    parsed_metadata = _parse_metadata(metadata)
    if title_page.lower() == "true" and not parsed_metadata.get("title"):
        markdown_title = _extract_markdown_title(content)
        parsed_metadata["title"] = markdown_title or Path(
            file.filename or "document",
        ).stem

    options = ConversionOptions(
        template_slug=template_slug,
        title_page=(title_page.lower() == "true"),
        page_header=page_header,
        toc=(toc.lower() == "true"),
        toc_depth=toc_depth,
        formula_position=formula_position,
        keep_separator=(keep_separator.lower() == "true"),
        convert_images=(convert_images.lower() == "true"),
        convert_mermaid=(convert_mermaid.lower() == "true"),
        metadata=parsed_metadata,
    )
    extra_args = mgr.build_extra_args(options)
    log.info(
        f"模版={template_slug}, title_page={title_page}, page_header={page_header!r}, "
        f"toc={toc}, formula={formula_position}, "
        f"keep_sep={keep_separator}, convert_images={convert_images}, "
        f"convert_mermaid={convert_mermaid}, "
        f"metadata={options.metadata}, args={extra_args}"
    )

    # 提交任务
    filename = file.filename or "input.md"
    task = await svc.submit(
        content,
        filename,
        fmt,
        extra_args,
        template_slug,
        convert_images=options.convert_images,
        convert_mermaid=options.convert_mermaid,
    )

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


# ========== 日志 ==========
@router.get("/logs", response_model=LogListResponse)
async def get_logs(
    level: str = "ALL",
    search: str = "",
    limit: int = 200,
    log_svc: Annotated[LogService, Depends(get_log_svc)] = None,
) -> LogListResponse:
    logs = log_svc.get_logs(
        level=None if level.upper() == "ALL" else level.upper(),
        search=search or None,
        limit=limit,
    )
    return LogListResponse(logs=[LogEntryResponse(**e) for e in logs], total=len(logs))


@router.delete("/logs")
async def clear_logs(
    log_svc: Annotated[LogService, Depends(get_log_svc)] = None,
) -> dict:
    log_svc.clear()
    return {"detail": "日志已清空"}


# ========== 模块管理 ==========


# ========== Pandoc 状态 ==========
@router.get("/pandoc-status", response_model=PandocStatusResponse)
async def pandoc_status() -> PandocStatusResponse:
    """获取 Pandoc 模块状态"""
    info = pandoc_manager.get_info()
    return PandocStatusResponse(
        available=bool(info.get("available", False)),
        version=str(info.get("version", "")),
        installer_found=bool(info.get("installer_found", False)),
        installer_path=str(info.get("installer_path", "")),
    )


async def _install_mermaid_flow():
    """Mermaid 使用系统 Edge，无需额外安装"""
    ok = edge_manager.is_ready()
    yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "Edge 已就绪" if ok else "未找到 Edge"})}
    yield {"event": "completed", "data": json.dumps({"success": ok})}


async def _uninstall_mermaid_flow():
    """Edge 是系统组件，不可卸载"""
    yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "Edge 是系统组件，无需卸载"})}
    yield {"event": "completed", "data": json.dumps({"success": True})}


# ── Pandoc ────────────────────────────────────────────────


async def _install_pandoc_flow():
    """内部：Pandoc 安装 SSE 事件流"""
    if pandoc_manager.is_installed():
        yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "已安装"})}
        yield {"event": "completed", "data": json.dumps({"success": True})}
        return

    task = asyncio.create_task(pandoc_manager.ensure())
    last_pct = -1
    pulse = 0
    while not task.done():
        prog = pandoc_manager.get_install_progress()
        pct = prog.get("progress", 0)
        msg = prog.get("message", "安装中...")
        if pct > last_pct:
            last_pct = pct
            pulse = 0
            yield {"event": "progress", "data": json.dumps({"progress": pct, "message": msg})}
        else:
            pulse += 1
            if pulse % 6 == 0:
                yield {
                    "event": "progress",
                    "data": json.dumps({"progress": last_pct, "message": msg}),
                }
        await asyncio.sleep(0.5)

    if task.result():
        yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "Pandoc 安装完成"})}
        yield {"event": "completed", "data": json.dumps({"success": True})}
    else:
        # 获取最终进度信息
        prog = pandoc_manager.get_install_progress()
        detail = prog.get("message", "Pandoc 安装失败")
        yield {"event": "error", "data": json.dumps({"detail": detail})}


async def _uninstall_pandoc_flow():
    """内部：Pandoc 卸载 SSE 事件流"""
    if not pandoc_manager.is_installed():
        yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "已卸载"})}
        yield {"event": "completed", "data": json.dumps({"success": True})}
        return

    yield {
        "event": "progress",
        "data": json.dumps({"progress": 10, "message": "正在卸载 Pandoc..."}),
    }

    yield {
        "event": "progress",
        "data": json.dumps({"progress": 30, "message": "正在查找 Pandoc 产品信息..."}),
    }

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, pandoc_manager.remove)

    if success:
        yield {"event": "progress", "data": json.dumps({"progress": 100, "message": "Pandoc 卸载完成"})}
        yield {"event": "completed", "data": json.dumps({"success": True})}
    else:
        prog = pandoc_manager.get_install_progress()
        detail = prog.get("message", "Pandoc 卸载失败")
        yield {"event": "error", "data": json.dumps({"detail": detail})}


@router.get("/modules/{module_id}/progress")
async def stream_module_progress(
    module_id: str,
    action: str = "install",
) -> EventSourceResponse:
    """SSE 流式返回模块安装/卸载进度"""

    async def event_gen():
        if action not in ("install", "uninstall"):
            yield {"event": "error", "data": json.dumps({"detail": f"未知操作: {action}"})}
            return

        if module_id == "mermaid":
            flow = _install_mermaid_flow if action == "install" else _uninstall_mermaid_flow
            async for evt in flow():
                yield evt
        elif module_id == "pandoc":
            flow = _install_pandoc_flow if action == "install" else _uninstall_pandoc_flow
            async for evt in flow():
                yield evt
        else:
            yield {"event": "error", "data": json.dumps({"detail": f"未知模块: {module_id}"})}
            return

    return EventSourceResponse(event_gen(), ping=5)


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
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _extract_markdown_title(content: bytes) -> str:
    """从 Markdown 的首个 ATX 一级标题提取标题页标题。"""
    text = content.decode("utf-8-sig", errors="replace")
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        stripped = line.strip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        heading = re.match(r"^#(?!#)\s+(.+?)\s*#*\s*$", stripped)
        if heading:
            return heading.group(1).strip()
    return ""
