"""API 路由"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse

from app.api.log import log
from app.api.schemas import (
    ConfirmRequest,
    ConvertRequest,
    ConvertResponse,
    HealthResponse,
    HistoryArtifactResponse,
    HistoryItemResponse,
    HistoryListResponse,
    LogEntryResponse,
    LogListResponse,
    MermaidRenderRequest,
    MermaidStatusResponse,
    PandocStatusResponse,
    SlugRequest,
    TaskIdRequest,
    TaskStatusResponse,
    TemplateGenerateRequest,
    TemplateGenerateResponse,
    TemplateItem,
    TemplateListResponse,
)
from app.core.browser_check import edge_manager
from app.core.pandoc_check import pandoc_manager
from app.core.template_manager import TemplateManager
from app.db.repository import ConversionRepository
from app.models.models import ConversionStatus, OutputFormat
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService
from app.services.log_service import LogService
from app.services.template_generator import TemplateGenerator

router = APIRouter()

# ---- 单例（由 main.py 注入） ----
_conv_service: ConversionService | None = None
_template_mgr: TemplateManager | None = None
_template_gen: TemplateGenerator | None = None
_log_svc: LogService | None = None
_repository: ConversionRepository | None = None
_artifact_storage: ArtifactStorage | None = None


def init(
    svc: ConversionService,
    mgr: TemplateManager,
    gen: TemplateGenerator,
    log_svc: LogService | None = None,
    repository: ConversionRepository | None = None,
    artifact_storage: ArtifactStorage | None = None,
) -> None:
    """初始化全局服务实例"""
    global _conv_service, _template_mgr, _template_gen, _log_svc, _repository, _artifact_storage
    _conv_service = svc
    _template_mgr = mgr
    _template_gen = gen
    _log_svc = log_svc
    _repository = repository
    _artifact_storage = artifact_storage


def get_repository() -> ConversionRepository:
    if _repository is None:
        raise RuntimeError("ConversionRepository 未初始化")
    return _repository


def get_artifact_storage() -> ArtifactStorage:
    if _artifact_storage is None:
        raise RuntimeError("ArtifactStorage 未初始化")
    return _artifact_storage


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


@router.post("/templates/delete")
async def delete_template(
    req: SlugRequest,
    gen: Annotated[TemplateGenerator, Depends(get_gen)],
) -> dict:
    slug = req.slug
    # 仅允许删除自定义模版
    custom_gen = gen.list_custom_templates()
    if not any(t["slug"] == slug for t in custom_gen):
        raise HTTPException(status_code=404, detail=f"自定义模版 '{slug}' 不存在")
    gen.delete_custom_template(slug)
    return {"detail": f"模版 '{slug}' 已删除"}


# ========== 文件转换 ==========
@router.post("/convert", response_model=ConvertResponse)
async def convert(
    req: ConvertRequest,
    svc: Annotated[ConversionService | None, Depends(get_svc)] = None,
    mgr: Annotated[TemplateManager | None, Depends(get_mgr)] = None,
) -> ConvertResponse:
    # 解析输出格式
    try:
        fmt = OutputFormat(req.output_format)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {req.output_format}")

    content = req.content.encode("utf-8")
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    # 组装额外参数
    from app.models.templates import ConversionOptions

    parsed_metadata = dict(req.options.metadata)
    if req.options.title_page and not parsed_metadata.get("title"):
        markdown_title = _extract_markdown_title(content)
        parsed_metadata["title"] = markdown_title or Path(req.file_name).stem

    options = ConversionOptions(
        template_slug=req.template_slug,
        title_page=req.options.title_page,
        page_header=req.options.page_header,
        toc=req.options.toc,
        toc_depth=req.options.toc_depth,
        formula_position=req.options.formula_position,
        keep_separator=req.options.keep_separator,
        convert_images=req.options.convert_images,
        convert_mermaid=req.options.convert_mermaid,
        metadata=parsed_metadata,
    )
    extra_args = mgr.build_extra_args(options)
    log.info(
        f"模版={req.template_slug}, title_page={options.title_page}, "
        f"page_header={options.page_header!r}, toc={options.toc}, "
        f"formula={options.formula_position}, keep_sep={options.keep_separator}, "
        f"convert_images={options.convert_images}, convert_mermaid={options.convert_mermaid}, "
        f"metadata={options.metadata}, args={extra_args}"
    )

    # 提交任务
    task = await svc.submit(
        content,
        req.file_name,
        fmt,
        extra_args,
        req.template_slug,
        options=options.model_dump(mode="json"),
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
    media_types = {
        OutputFormat.DOCX: (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        OutputFormat.PDF: "application/pdf",
        OutputFormat.HTML: "text/html; charset=utf-8",
        OutputFormat.EPUB: "application/epub+zip",
    }
    return FileResponse(
        task.output_path,
        media_type=media_types.get(task.output_format, "application/octet-stream"),
        filename=task.output_path.name,
    )


# ========== 历史记录 ==========
@router.get("/history", response_model=HistoryListResponse)
async def list_history(
    search: str = "",
    days: Annotated[int | None, Query(ge=1, le=3650)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    repository: Annotated[ConversionRepository, Depends(get_repository)] = None,
) -> HistoryListResponse:
    jobs, total, output_bytes = repository.list_history(
        search=search,
        days=days,
        limit=limit,
        offset=offset,
    )
    return HistoryListResponse(
        items=[_history_item(job) for job in jobs],
        total=total,
        output_bytes=output_bytes,
    )


@router.get("/history/{task_id}", response_model=HistoryItemResponse)
async def get_history(
    task_id: UUID,
    repository: Annotated[ConversionRepository, Depends(get_repository)],
) -> HistoryItemResponse:
    job = repository.get_job(task_id)
    if job is None or job.status != ConversionStatus.COMPLETED.value:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return _history_item(job)


@router.get("/history/{task_id}/{kind}")
async def download_history_artifact(
    task_id: UUID,
    kind: str,
    repository: Annotated[ConversionRepository, Depends(get_repository)],
    storage: Annotated[ArtifactStorage, Depends(get_artifact_storage)],
) -> FileResponse:
    if kind not in {"source", "output"}:
        raise HTTPException(status_code=404, detail="历史文件不存在")
    job = repository.get_job(task_id)
    if job is None or job.status != ConversionStatus.COMPLETED.value:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    artifact = next((item for item in job.artifacts if item.kind == kind), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="历史文件不存在")
    path = storage.resolve(artifact.relative_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="历史文件已丢失")
    return FileResponse(path, media_type=artifact.content_type, filename=artifact.file_name)


@router.post("/history/delete")
async def delete_history(
    req: TaskIdRequest,
    repository: Annotated[ConversionRepository, Depends(get_repository)],
    storage: Annotated[ArtifactStorage, Depends(get_artifact_storage)],
    svc: Annotated[ConversionService, Depends(get_svc)],
) -> dict:
    job = repository.get_job(req.task_id)
    if job is None or job.status != ConversionStatus.COMPLETED.value:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    storage.delete_task(req.task_id)
    repository.delete_job(req.task_id)
    svc.forget_task(req.task_id)
    return {"detail": "历史记录已删除"}


@router.post("/history/clear")
async def clear_history(
    req: ConfirmRequest,
    repository: Annotated[ConversionRepository, Depends(get_repository)],
    storage: Annotated[ArtifactStorage, Depends(get_artifact_storage)],
    svc: Annotated[ConversionService, Depends(get_svc)],
) -> dict:
    if not req.confirm:
        raise HTTPException(status_code=400, detail="需要确认清空历史记录")
    task_ids = repository.clear_history()
    for task_id in task_ids:
        storage.delete_task(task_id)
        svc.forget_task(task_id)
    return {"detail": "历史记录已清空", "deleted": len(task_ids)}


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


@router.post("/logs/clear")
async def clear_logs(
    req: ConfirmRequest,
    log_svc: Annotated[LogService, Depends(get_log_svc)] = None,
) -> dict:
    if not req.confirm:
        raise HTTPException(status_code=400, detail="需要确认清空日志")
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
    yield {
        "event": "progress",
        "data": json.dumps({"progress": 100, "message": "Edge 已就绪" if ok else "未找到 Edge"}),
    }
    yield {"event": "completed", "data": json.dumps({"success": ok})}


async def _uninstall_mermaid_flow():
    """Edge 是系统组件，不可卸载"""
    yield {
        "event": "progress",
        "data": json.dumps({"progress": 100, "message": "Edge 是系统组件，无需卸载"}),
    }
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
        yield {
            "event": "progress",
            "data": json.dumps({"progress": 100, "message": "Pandoc 安装完成"}),
        }
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
        yield {
            "event": "progress",
            "data": json.dumps({"progress": 100, "message": "Pandoc 卸载完成"}),
        }
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


def _history_item(job) -> HistoryItemResponse:
    artifacts = {artifact.kind: artifact for artifact in job.artifacts}
    source = artifacts.get("source")
    output = artifacts.get("output")
    if source is None or output is None:
        raise HTTPException(status_code=500, detail=f"历史记录 {job.id} 的文件索引不完整")

    def artifact_response(artifact) -> HistoryArtifactResponse:
        return HistoryArtifactResponse(
            kind=artifact.kind,
            file_name=artifact.file_name,
            content_type=artifact.content_type,
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
        )

    return HistoryItemResponse(
        task_id=job.id,
        status=job.status,
        source_file_name=job.source_file_name,
        output_format=job.output_format,
        template_slug=job.template_slug,
        options=job.options_json,
        progress=job.progress,
        error_message=job.error_message,
        duration_ms=job.duration_ms,
        created_at=job.created_at,
        completed_at=job.completed_at,
        source=artifact_response(source),
        output=artifact_response(output),
    )
