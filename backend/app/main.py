"""MarkFlow 后端入口 - FastAPI 应用"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.utils.config import AppSettings
from app.utils.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    setup_logging(settings.log_level)
    yield


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
