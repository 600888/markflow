"""全局错误处理"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.exceptions import (
    ConversionError,
    FileTooLargeError,
    MarkflowError,
    UnsupportedFormatError,
)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(FileTooLargeError)
    async def handle_file_too_large(request: Request, exc: FileTooLargeError) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={"detail": exc.message},
        )

    @app.exception_handler(UnsupportedFormatError)
    async def handle_unsupported_format(
        request: Request,
        exc: UnsupportedFormatError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": exc.message},
        )

    @app.exception_handler(ConversionError)
    async def handle_conversion_error(request: Request, exc: ConversionError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.message},
        )

    @app.exception_handler(MarkflowError)
    async def handle_markflow_error(request: Request, exc: MarkflowError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.message},
        )
