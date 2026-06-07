"""MarkFlow 后端入口 - FastAPI 应用"""

from __future__ import annotations

import argparse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.errors import register_error_handlers
from app.api.router import init, router
from app.core.engine import PandocEngine
from app.core.file_manager import TempFileManager
from app.core.template_manager import TemplateManager
from app.services.converter import ConversionService
from app.utils.config import AppSettings
from app.utils.logger import Log


def _parse_cli_args() -> argparse.Namespace:
    """解析命令行参数（Tauri sidecar 传入 --port）"""
    parser = argparse.ArgumentParser(description="MarkFlow Backend")
    parser.add_argument("--port", type=int, default=None, help="服务端口号")
    args, _ = parser.parse_known_args()
    return args


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """应用生命周期 — 组装依赖并注入"""
    Log(
        cmdlevel=settings.log_level,
        filelevel=settings.log_level,
        filename="logs/markflow.log",
        backup_count=7,
        limit="20 MB",
    )
    logger.info("MarkFlow 后端启动，端口: {}", settings.port)

    # 依赖组装
    engine = PandocEngine(settings)
    file_mgr = TempFileManager(settings)
    template_mgr = TemplateManager()
    conv_svc = ConversionService(
        engine=engine,
        file_manager=file_mgr,
        max_file_size=settings.max_file_size,
        max_concurrent=settings.max_concurrent_tasks,
    )

    # 注入到路由层
    init(conv_svc, template_mgr)

    yield

    logger.info("MarkFlow 后端关闭")


settings = AppSettings()


def create_app() -> FastAPI:
    """应用工厂"""
    app = FastAPI(
        title="MarkFlow Converter",
        description="Markdown 转 Word / PDF / HTML 等格式的转换服务",
        version="0.1.0",
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

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
