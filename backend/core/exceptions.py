"""Application-level exceptions and their FastAPI exception handlers.

Keeps the error response shape consistent (`{"detail": ...}`) whether the
failure is a known domain error (404, bad filter/sort field) or something
unexpected, instead of leaking a raw traceback to API consumers.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

logger = get_logger(__name__)


class APIError(Exception):
    """Base class for domain errors that map to a specific HTTP status code."""

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotFoundError(APIError):
    """Raised when a requested resource (driver, session, etc.) doesn't exist."""

    status_code = status.HTTP_404_NOT_FOUND


class InvalidQueryError(APIError):
    """Raised for semantically invalid query parameters (e.g. an unknown sort field)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()}
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error processing %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )
