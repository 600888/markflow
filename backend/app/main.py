"""MarkFlow 后端入口 - FastAPI 应用"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.utils.config import AppSettings
from app.utils.logger import Log


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """应用生命周期"""
    Log(
        cmdlevel=settings.log_level,
        filelevel=settings.log_level,
        filename="logs/markflow.log",
        backup_count=7,
        limit="20 MB",
    )
    logger.info("MarkFlow 后端服务启动，端口: {}", settings.port)
    yield
    logger.info("MarkFlow 后端服务关闭")


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

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
