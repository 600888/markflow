"""API 路由"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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
    TaskIdRequest,
    TaskStatusResponse,
    TemplateDetailResponse,
    TemplateItem,
    TemplateListResponse,
    TemplateRevisionDetailResponse,
    TemplateRevisionItem,
    TemplateRevisionListResponse,
    TemplateSaveRequest,
    TemplateSaveResponse,
    WordToPdfStatusResponse,
)
from app.core.browser_check import edge_manager
from app.core.pandoc_check import pandoc_manager
from app.core.template_manager import TemplateManager
from app.core.word_to_pdf_engine import WordToPdfEngineRegistry
from app.db.repository import ConversionRepository
from app.models.models import ConversionPipeline, ConversionStatus, OutputFormat
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService
from app.services.log_service import LogService
from app.services.template_generator import TemplateGenerator
from app.services.template_service import (
    TemplateConflictError,
    TemplateNotFoundError,
    TemplateService,
)
from app.services.word_file_validator import WordFileValidator
from app.utils.exceptions import FileTooLargeError, WordEngineUnavailableError

router = APIRouter()

# ---- 单例（由 main.py 注入） ----
_conv_service: ConversionService | None = None
_template_mgr: TemplateService | TemplateManager | None = None
_template_gen: TemplateGenerator | None = None
_log_svc: LogService | None = None
_repository: ConversionRepository | None = None
_artifact_storage: ArtifactStorage | None = None
_word_to_pdf_registry: WordToPdfEngineRegistry | None = None


def init(
    svc: ConversionService,
    mgr: TemplateService | TemplateManager,
    gen: TemplateGenerator,
    log_svc: LogService | None = None,
    repository: ConversionRepository | None = None,
    artifact_storage: ArtifactStorage | None = None,
    word_to_pdf_registry: WordToPdfEngineRegistry | None = None,
) -> None:
    """初始化全局服务实例"""
    global _conv_service, _template_mgr, _template_gen, _log_svc
    global _repository, _artifact_storage, _word_to_pdf_registry
    _conv_service = svc
    _template_mgr = mgr
    _template_gen = gen
    _log_svc = log_svc
    _repository = repository
    _artifact_storage = artifact_storage
    _word_to_pdf_registry = word_to_pdf_registry


def get_repository() -> ConversionRepository:
    if _repository is None:
        raise RuntimeError("ConversionRepository 未初始化")
    return _repository


def get_artifact_storage() -> ArtifactStorage:
    if _artifact_storage is None:
        raise RuntimeError("ArtifactStorage 未初始化")
    return _artifact_storage


def get_word_to_pdf_registry() -> WordToPdfEngineRegistry:
    if _word_to_pdf_registry is None:
        raise RuntimeError("WordToPdfEngineRegistry 未初始化")
    return _word_to_pdf_registry


def get_log_svc() -> LogService:
    if _log_svc is None:
        raise RuntimeError("LogService 未初始化")
    return _log_svc


def get_svc() -> ConversionService:
    if _conv_service is None:
        raise RuntimeError("ConversionService 未初始化")
    return _conv_service


def get_mgr() -> TemplateService | TemplateManager:
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
async def list_templates(
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateListResponse:
    items = [TemplateItem(**t.model_dump()) for t in mgr.list_templates()]
    return TemplateListResponse(templates=items)


def _template_styles(req: TemplateSaveRequest) -> dict:
    """将 Pydantic 样式模型转为模版生成器使用的普通字典。"""
    return {key: style.model_dump(exclude_none=True) for key, style in req.styles.items()}


def _template_definition(req: TemplateSaveRequest) -> dict:
    return {
        "name": req.name,
        "slug": req.slug,
        "styles": _template_styles(req),
        "description": req.description,
        "author": req.author,
        "target_formats": req.target_formats,
        "version": req.version,
    }


def _template_response(entity) -> TemplateSaveResponse:
    return TemplateSaveResponse(
        id=entity.id,
        slug=entity.slug,
        name=entity.name,
        revision=entity.revision,
        updated_at=entity.updated_at,
    )


# ========== 自定义模版资源 ==========
@router.post("/templates", response_model=TemplateSaveResponse, status_code=201)
async def create_template(
    req: TemplateSaveRequest,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateSaveResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    try:
        return _template_response(mgr.create_custom_template(_template_definition(req)))
    except TemplateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/templates/{slug}", response_model=TemplateSaveResponse)
async def update_template(
    slug: str,
    req: TemplateSaveRequest,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateSaveResponse:
    if slug != req.slug:
        raise HTTPException(status_code=400, detail="路径 slug 与请求内容不一致")
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    try:
        entity = mgr.update_custom_template(
            slug,
            _template_definition(req),
            expected_revision=req.revision,
        )
        return _template_response(entity)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TemplateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/templates/{slug}", response_model=TemplateDetailResponse)
async def get_template_detail(
    slug: str,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateDetailResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    data = mgr.get_template_snapshot(slug)
    if data is None:
        raise HTTPException(status_code=404, detail=f"模版 '{slug}' 不存在")
    return TemplateDetailResponse.model_validate(data)


def _revision_item(revision) -> TemplateRevisionItem:
    return TemplateRevisionItem(
        template_id=revision.template_id,
        slug=revision.slug,
        revision=revision.revision,
        operation=revision.operation,
        name=str(revision.definition_json.get("name", revision.slug)),
        artifact_sha256=revision.artifact_sha256,
        created_at=revision.created_at,
    )


@router.get(
    "/templates/{template_id}/revisions",
    response_model=TemplateRevisionListResponse,
)
async def list_template_revisions(
    template_id: str,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateRevisionListResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    revisions = mgr.list_revisions(template_id)
    if not revisions:
        raise HTTPException(status_code=404, detail="模板修订历史不存在")
    return TemplateRevisionListResponse(revisions=[_revision_item(item) for item in revisions])


@router.get(
    "/template-revisions/deleted",
    response_model=TemplateRevisionListResponse,
)
async def list_deleted_template_histories(
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateRevisionListResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    return TemplateRevisionListResponse(
        revisions=[_revision_item(item) for item in mgr.list_deleted_template_histories()]
    )


@router.get(
    "/templates/{template_id}/revisions/{revision}",
    response_model=TemplateRevisionDetailResponse,
)
async def get_template_revision(
    template_id: str,
    revision: int,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateRevisionDetailResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    item = mgr.get_revision(template_id, revision)
    if item is None:
        raise HTTPException(status_code=404, detail="模板修订不存在")
    summary = _revision_item(item)
    return TemplateRevisionDetailResponse(
        **summary.model_dump(),
        definition=item.definition_json,
    )


@router.post(
    "/templates/{template_id}/revisions/{revision}/restore",
    response_model=TemplateSaveResponse,
)
async def restore_template_revision(
    template_id: str,
    revision: int,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> TemplateSaveResponse:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    try:
        return _template_response(mgr.restore_revision(template_id, revision))
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TemplateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/templates/preview")
async def preview_template(
    req: TemplateSaveRequest,
    gen: Annotated[TemplateGenerator, Depends(get_gen)],
) -> Response:
    content = gen.generate_reference(_template_styles(req))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{req.slug}-preview.docx"'},
    )


@router.delete("/templates/{slug}", status_code=204)
async def delete_template(
    slug: str,
    mgr: Annotated[TemplateService | TemplateManager, Depends(get_mgr)],
) -> Response:
    if not isinstance(mgr, TemplateService):
        raise TypeError("TemplateService 未初始化")
    if not mgr.delete_custom_template(slug):
        raise HTTPException(status_code=404, detail=f"自定义模版 '{slug}' 不存在")
    return Response(status_code=204)


# ========== Word 转 PDF ==========
@router.get("/word-to-pdf/status", response_model=WordToPdfStatusResponse)
async def word_to_pdf_status(
    registry: Annotated[WordToPdfEngineRegistry, Depends(get_word_to_pdf_registry)],
) -> WordToPdfStatusResponse:
    return WordToPdfStatusResponse(**registry.get_info(refresh=True))


@router.post("/word-to-pdf/convert", response_model=ConvertResponse)
async def convert_word_to_pdf(
    file: Annotated[UploadFile, File()],
    output_file_name: Annotated[str, Form(max_length=255)] = "",
    engine: Annotated[str, Form()] = "",
    quality: Annotated[str, Form()] = "standard",
    export_bookmarks: Annotated[bool, Form()] = True,  # noqa: FBT002
    svc: Annotated[ConversionService, Depends(get_svc)] = None,
    registry: Annotated[WordToPdfEngineRegistry, Depends(get_word_to_pdf_registry)] = None,
) -> ConvertResponse:
    if quality not in {"screen", "standard", "print"}:
        raise HTTPException(status_code=400, detail=f"不支持的 PDF 质量选项: {quality}")
    selected_engine = registry.resolve_engine_id(engine, refresh=True)
    if selected_engine not in registry.engines:
        raise HTTPException(status_code=400, detail=f"不支持的导出引擎: {selected_engine}")
    engine_info = registry.get_engine_info(selected_engine, refresh=True)
    if not engine_info["available"]:
        raise WordEngineUnavailableError(str(engine_info["diagnostic"]))

    filename = Path(file.filename or "document.docx").name
    try:
        content = await _read_upload_limited(file, svc.max_file_size)
    finally:
        await file.close()
    WordFileValidator().validate(content, filename)

    options = {
        "quality": quality,
        "export_bookmarks": export_bookmarks,
        "engine": selected_engine,
        "engine_version": engine_info["version"],
    }
    task = await svc.submit(
        content,
        filename,
        OutputFormat.PDF,
        options=options,
        pipeline=ConversionPipeline.WORD_TO_PDF,
        output_file_name=output_file_name.strip() or None,
        convert_images=False,
        convert_mermaid=False,
    )
    asyncio.create_task(_run_convert(svc, task.task_id))
    return ConvertResponse(
        task_id=str(task.task_id),
        status=task.status.value,
        message="任务已提交",
    )


# ========== Markdown 文件转换 ==========
@router.post("/convert", response_model=ConvertResponse)
async def convert(
    req: ConvertRequest,
    svc: Annotated[ConversionService | None, Depends(get_svc)] = None,
    mgr: Annotated[TemplateService | TemplateManager | None, Depends(get_mgr)] = None,
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
    options_snapshot = options.model_dump(mode="json")
    template_info = mgr.get_template(req.template_slug)
    if template_info is not None and template_info.revision is not None:
        options_snapshot["template_revision"] = template_info.revision
    template_snapshot = (
        mgr.get_template_snapshot(req.template_slug) if isinstance(mgr, TemplateService) else None
    )
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
        options=options_snapshot,
        template_snapshot=template_snapshot,
        output_file_name=req.output_file_name.strip() or None,
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
    # 跳过文件索引不完整的旧记录，避免单条脏数据导致整个列表 500
    items = [
        item
        for job in jobs
        if (item := _history_item(job)) is not None
    ]
    return HistoryListResponse(
        items=items,
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
    item = _history_item(job, include_template_snapshot=True)
    if item is None:
        raise HTTPException(status_code=500, detail="历史记录文件索引不完整")
    return item


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


async def _read_upload_limited(file: UploadFile, max_size: int) -> bytes:
    """流式读取上传文件，并在解析过程中执行大小上限。"""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > max_size:
            raise FileTooLargeError(f"文件大小超过上限 {max_size} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


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


def _history_item(
    job,
    *,
    include_template_snapshot: bool = False,
) -> HistoryItemResponse | None:
    artifacts = {artifact.kind: artifact for artifact in job.artifacts}
    source = artifacts.get("source")
    output = artifacts.get("output")
    if source is None or output is None:
        # 文件索引不完整的旧记录：返回 None，由调用方跳过或报错
        return None

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
        pipeline=job.pipeline,
        source_file_name=job.source_file_name,
        output_format=job.output_format,
        template_slug=job.template_slug,
        template_revision=job.template_revision,
        template_snapshot=(job.template_snapshot_json if include_template_snapshot else None),
        options=job.options_json,
        progress=job.progress,
        error_message=job.error_message,
        duration_ms=job.duration_ms,
        created_at=job.created_at,
        completed_at=job.completed_at,
        source=artifact_response(source),
        output=artifact_response(output),
    )
