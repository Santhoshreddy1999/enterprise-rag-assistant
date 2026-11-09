from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.application.services import (
    ConflictError,
    InvalidCredentialsError,
    ResourceNotFoundError,
)
from app.core.config import Settings
from app.core.telemetry import configure_logging, observe_request
from app.infrastructure.database import Database
from app.infrastructure.documents import (
    DocumentTooLargeError,
    InvalidDocumentError,
    UnsupportedDocumentError,
)
from app.infrastructure.embeddings import DeterministicEmbedding
from app.infrastructure.providers import ProviderError, build_answer_provider
from app.infrastructure.retrieval import HybridRetriever


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    configure_logging(resolved_settings.log_level)
    database = Database(resolved_settings.database_url)
    embedding = DeterministicEmbedding(resolved_settings.embedding_dimension)
    retriever = HybridRetriever(
        embedding,
        candidate_limit=resolved_settings.retrieval_candidate_limit,
        rrf_constant=resolved_settings.rrf_constant,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.auto_create_schema:
            database.create_schema()
        yield
        database.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = database
    app.state.embedding = embedding
    app.state.retriever = retriever
    app.state.answer_provider = build_answer_provider(resolved_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
    )
    app.middleware("http")(observe_request)
    app.include_router(router, prefix="/api/v1")

    @app.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    async def credentials_handler(_request: Request, _exc: InvalidCredentialsError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid authentication credentials"},
        )

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_handler(_request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DocumentTooLargeError)
    async def document_too_large_handler(
        _request: Request, exc: DocumentTooLargeError
    ) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedDocumentError)
    async def unsupported_document_handler(
        _request: Request, exc: UnsupportedDocumentError
    ) -> JSONResponse:
        return JSONResponse(status_code=415, content={"detail": str(exc)})

    @app.exception_handler(InvalidDocumentError)
    async def invalid_document_handler(
        _request: Request, exc: InvalidDocumentError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_handler(_request: Request, _exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "The configured answer provider is unavailable"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "loc": error.get("loc", ()),
                "msg": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("rag.error").error(
            "unhandled_request_error",
            extra={
                "event": "unhandled_request_error",
                "request_id": getattr(request.state, "request_id", "unknown"),
                "method": request.method,
                "path": request.url.path,
                "error_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
