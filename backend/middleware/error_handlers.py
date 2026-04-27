"""
Error Handlers

Custom exception handlers for standardized API errors.

Phase 13: Production Ready
"""

import logging
from typing import Union
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception with error code."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(AppException):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' not found",
            error_code=f"{resource.upper()}_NOT_FOUND",
            status_code=404
        )


class UnauthorizedError(AppException):
    """Unauthorized access error."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=401
        )


class ForbiddenError(AppException):
    """Forbidden access error."""

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            status_code=403
        )


class BadRequestError(AppException):
    """Bad request error."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="BAD_REQUEST",
            status_code=400
        )


def create_error_response(
    message: str,
    error_code: str,
    status_code: int,
    details: dict = None
) -> dict:
    """
    Create a standardized error response.

    Args:
        message: Human-readable error message
        error_code: Machine-readable error code
        status_code: HTTP status code
        details: Additional error details (optional)

    Returns:
        Standardized error response dictionary
    """
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    if details:
        response["error"]["details"] = details

    return response


def register_error_handlers(app: FastAPI) -> None:
    """
    Register custom error handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Handle custom application exceptions."""
        logger.warning(
            f"AppException: {exc.error_code} - {exc.message}",
            extra={"path": request.url.path}
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                message=exc.message,
                error_code=exc.error_code,
                status_code=exc.status_code,
                details=exc.details
            )
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        logger.warning(
            f"ValidationError: {exc.errors()}",
            extra={"path": request.url.path}
        )

        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=create_error_response(
                message="Request validation failed",
                error_code="VALIDATION_ERROR",
                status_code=422,
                details={"errors": errors}
            )
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """Handle rate limit exceeded errors."""
        logger.warning(
            f"RateLimitExceeded: {request.client.host}",
            extra={"path": request.url.path}
        )

        return JSONResponse(
            status_code=429,
            content=create_error_response(
                message="Rate limit exceeded. Please slow down.",
                error_code="RATE_LIMIT_EXCEEDED",
                status_code=429,
                details={"retry_after": getattr(exc, "retry_after", None)}
            )
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions - no internal details leaked."""
        logger.error(
            f"Unhandled exception: {type(exc).__name__}",
            extra={
                "path": request.url.path,
                "error": str(exc),
                "type": type(exc).__name__
            }
        )

        return JSONResponse(
            status_code=500,
            content=create_error_response(
                message="An unexpected error occurred. Please try again later.",
                error_code="INTERNAL_ERROR",
                status_code=500
            )
        )
