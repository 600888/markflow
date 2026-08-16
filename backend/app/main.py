"""MarkFlow 后端入口 - FastAPI 应用"""

from __future__ import annotations

import argparse
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.errors import register_error_handlers
from app.api.router import init, router
from app.core.engine import PandocEngine
from app.core.template_manager import TemplateManager
from app.core.to_markdown_engine import ToMarkdownEngineRegistry
from app.core.word_to_pdf_engine import WordToPdfEngineRegistry
from app.db import ConversionRepository, CustomTemplateRepository, Database
from app.services.artifact_storage import ArtifactStorage
from app.services.converter import ConversionService
from app.services.log_service import LogService, install_loguru_sink
from app.services.template_artifact_store import TemplateArtifactStore
from app.services.template_generator import TemplateGenerator
from app.services.template_service import TemplateService
from app.utils.config import AppSettings
from app.utils.logger import Log
from config.paths import LOG_DIR, TEMPLATES_DIR


def _parse_cli_args() -> argparse.Namespace:
    """解析命令行参数（Tauri sidecar 传入 --port 和 --data-dir）"""
    parser = argparse.ArgumentParser(description="MarkFlow Backend")
    parser.add_argument("--port", type=int, default=None, help="服务端口号")
    parser.add_argument(
        "--data-dir", type=str, default=None, help="数据资源目录（含 Pandoc MSI 等）"
    )
    args, _ = parser.parse_known_args()
    return args


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """应用生命周期 — 组装依赖并注入"""
    Log(
        cmdlevel=settings.log_level,
        filelevel=settings.log_level,
        filename=str(LOG_DIR / "markflow.log"),
        backup_count=7,
        limit="20 MB",
    )
    logger.info("MarkFlow 后端启动，端口: {}", settings.port)

    # 依赖组装
    database = Database(settings.data_dir)
    database.initialize()
    repository = ConversionRepository(database.session_factory)
    interrupted = repository.mark_interrupted()
    if interrupted:
        logger.warning("已将 {} 个未完成任务标记为中断", interrupted)

    artifact_storage = ArtifactStorage(settings.data_dir)
    template_gen = TemplateGenerator()
    template_mgr = TemplateService(
        builtin_manager=TemplateManager(),
        repository=CustomTemplateRepository(database.session_factory),
        artifact_store=TemplateArtifactStore(settings.data_dir),
        generator=template_gen,
    )
    imported, failed = template_mgr.import_legacy_templates(
        [TEMPLATES_DIR / "custom", settings.data_dir / "templates" / "custom"]
    )
    if imported or failed:
        logger.info("旧自定义模板迁移完成：导入 {} 个，失败 {} 个", imported, failed)
    cleanup = template_mgr.cleanup_orphan_artifacts()
    if any(cleanup.values()):
        logger.info(
            "模板派生文件清理完成：临时文件 {}，孤儿文件 {}，空目录 {}",
            cleanup["temporary_files"],
            cleanup["orphan_files"],
            cleanup["directories"],
        )
    engine = PandocEngine(settings, template_manager=template_mgr)
    word_engine = WordToPdfEngineRegistry(settings, engine)
    to_markdown_engine = ToMarkdownEngineRegistry(settings)
    conv_svc = ConversionService(
        engine=engine,
        repository=repository,
        artifact_storage=artifact_storage,
        max_file_size=settings.max_file_size,
        max_concurrent=settings.max_concurrent_tasks,
        word_engine=word_engine,
        max_concurrent_word=settings.max_concurrent_word_tasks,
        to_markdown_engine=to_markdown_engine,
        max_concurrent_to_markdown=settings.max_concurrent_to_markdown_tasks,
    )

    # 日志服务（内存环形缓冲区 + loguru sink 自动采集）
    log_svc = LogService()
    install_loguru_sink(log_svc)

    # 注入到路由层
    init(
        conv_svc,
        template_mgr,
        template_gen,
        log_svc=log_svc,
        repository=repository,
        artifact_storage=artifact_storage,
        word_to_pdf_registry=word_engine,
        to_markdown_registry=to_markdown_engine,
    )

    # ── 启动时检查 Mermaid 和 Pandoc 环境 ──
    from app.core.mermaid_renderer import get_diagnostic_message as mermaid_diag

    logger.info(mermaid_diag())

    from app.core.pandoc_check import pandoc_manager

    if pandoc_manager.is_installed():
        info = pandoc_manager.get_info()
        logger.info(f"Pandoc 已就绪, 版本: {info.get('version', 'unknown')}")
    else:
        logger.warning("Pandoc 未安装，转换功能暂不可用。请在设置中安装 Pandoc 模块。")

    yield

    logger.info("MarkFlow 后端关闭")
    database.close()


settings = AppSettings()


def create_app() -> FastAPI:
    """应用工厂"""
    from config.version import APP_VERSION

    app = FastAPI(
        title="MarkFlow Converter",
        description="Markdown 转 Word / PDF / HTML 等格式的转换服务",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    register_error_handlers(app)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    cli_args = _parse_cli_args()

    # Tauri sidecar 传入的 --port 覆盖配置
    if cli_args.port is not None:
        settings.port = cli_args.port

    # Tauri sidecar 传入的 --data-dir（备选：当环境变量未成功传递时使用）
    if cli_args.data_dir is not None:
        os.environ.setdefault("MARKFLOW_DATA_DIR", cli_args.data_dir)
        logger.info(f"通过 --data-dir 设置 MARKFLOW_DATA_DIR: {cli_args.data_dir}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
