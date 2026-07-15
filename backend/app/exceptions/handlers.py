"""
AMASCI Global Exception Handler
=================================
Centralized exception-to-HTTP-response mapping.
"""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from app.exceptions import (
    AmasciBaseException,
    AuthException,
    DatabaseException,
    ForecastException,
    GraphException,
    InvalidCredentialsException,
    InsufficientPermissionsException,
    MLException,
    PipelineException,
    RecordNotFoundException,
    TokenExpiredException,
    TPKEException,
    UploadException,
    ValidationException,
)

logger = logging.getLogger(__name__)

# Map exception types to HTTP status codes
EXCEPTION_STATUS_MAP: dict[type, int] = {
    ValidationException: 422,
    UploadException: 400,
    InvalidCredentialsException: 401,
    TokenExpiredException: 401,
    InsufficientPermissionsException: 403,
    RecordNotFoundException: 404,
    MLException: 500,
    GraphException: 500,
    TPKEException: 500,
    ForecastException: 500,
    DatabaseException: 500,
    PipelineException: 500,
    AuthException: 401,
}


def _get_status_code(exc: AmasciBaseException) -> int:
    """Determine HTTP status code from exception type."""
    for exc_type, status in EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return status
    return 500


def _build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standardized error response payload."""
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "status_code": status_code,
        },
    }
    if details:
        response["error"]["details"] = details
    return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""

    @app.exception_handler(AmasciBaseException)
    async def amasci_exception_handler(
        request: Request, exc: AmasciBaseException
    ) -> ORJSONResponse:
        status_code = _get_status_code(exc)
        logger.error(
            f"[{exc.error_code}] {exc.message}",
            extra={"details": exc.details, "path": request.url.path},
        )
        return ORJSONResponse(
            status_code=status_code,
            content=_build_error_response(
                status_code=status_code,
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request, exc: ValueError
    ) -> ORJSONResponse:
        logger.warning(f"ValueError: {exc}", extra={"path": request.url.path})
        return ORJSONResponse(
            status_code=422,
            content=_build_error_response(
                status_code=422,
                error_code="VALIDATION_ERROR",
                message=str(exc),
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        logger.critical(
            f"Unhandled exception: {exc}",
            extra={"path": request.url.path, "traceback": traceback.format_exc()},
        )
        return ORJSONResponse(
            status_code=500,
            content=_build_error_response(
                status_code=500,
                error_code="INTERNAL_ERROR",
                message="An unexpected error occurred" if not logger.isEnabledFor(logging.DEBUG) else str(exc),
            ),
        )
