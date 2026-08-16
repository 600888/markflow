"""全局错误处理"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.exceptions import (
    ConversionError,
    FileTooLargeError,
    InvalidWordFileError,
    MarkflowError,
    ToMarkdownUnavailableError,
    UnsupportedFormatError,
    WordEngineUnavailableError,
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

    @app.exception_handler(InvalidWordFileError)
    async def handle_invalid_word_file(
        request: Request,
        exc: InvalidWordFileError,
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @app.exception_handler(WordEngineUnavailableError)
    async def handle_word_engine_unavailable(
        request: Request,
        exc: WordEngineUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.message})

    @app.exception_handler(ToMarkdownUnavailableError)
    async def handle_to_markdown_unavailable(
        request: Request,
        exc: ToMarkdownUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.message})

    @app.exception_handler(MarkflowError)
    async def handle_markflow_error(request: Request, exc: MarkflowError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": exc.message},
        )
