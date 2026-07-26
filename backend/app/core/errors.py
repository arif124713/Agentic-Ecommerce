"""Exception hierarchy and handlers producing the standard error envelope (spec §10.5)."""

from __future__ import annotations

import uuid

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("blackcart.errors")


class AppError(Exception):
    """Base class for all domain/application errors that map to a stable error code."""

    code: str = "INTERNAL_ERROR"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        details: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.details = details or []
        self.headers = headers or {}
        super().__init__(self.message)


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "Request failed schema validation."


class NotFoundError(AppError):
    code = "RESOURCE_NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "The requested resource was not found."


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT
    message = "The request conflicts with the current state of the resource."


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"
    message = "An account with this email already exists."


class ItemUnavailableError(ConflictError):
    code = "ITEM_UNAVAILABLE"
    message = "This item is no longer available in the requested quantity."


class CouponInvalidError(ConflictError):
    code = "COUPON_INVALID"
    message = "This coupon can't be applied."


class StockReservationExpiredError(ConflictError):
    code = "RESERVATION_EXPIRED"
    message = "Your checkout session has expired. Please review your cart and try again."


class ReviewNotEligibleError(ConflictError):
    code = "REVIEW_NOT_ELIGIBLE"
    message = "Only a delivered order can be reviewed, and each purchase can be reviewed once."


class ReviewEditWindowClosedError(ConflictError):
    code = "REVIEW_EDIT_WINDOW_CLOSED"
    message = "Reviews can only be edited within 24 hours of posting."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN
    message = "You do not have permission to perform this action."


class UnauthorizedError(AppError):
    code = "INVALID_CREDENTIALS"
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Authentication is required or credentials are invalid."


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Too many requests. Please try again later."


class AccountLockedError(AppError):
    code = "ACCOUNT_LOCKED"
    status_code = status.HTTP_423_LOCKED
    message = "This account is temporarily locked due to repeated failed sign-in attempts."


class DependencyUnavailableError(AppError):
    code = "DEPENDENCY_UNAVAILABLE"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "A required dependency is currently unavailable."


def _envelope(code: str, message: str, request_id: str, details: list[dict] | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = _request_id(request)
        logger.info(
            "app_error",
            code=exc.code,
            status=exc.status_code,
            request_id=request_id,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, request_id, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        request_id = _request_id(request)
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "issue": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope("VALIDATION_ERROR", "Request failed schema validation.", request_id, details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        request_id = _request_id(request)
        code = {
            404: "RESOURCE_NOT_FOUND",
            401: "INVALID_CREDENTIALS",
            403: "FORBIDDEN",
            405: "METHOD_NOT_ALLOWED",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "INTERNAL_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), request_id),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        request_id = _request_id(request)
        logger.error(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            request_id=request_id,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "INTERNAL_ERROR",
                "An unexpected error occurred. Support can look this up by request_id.",
                request_id,
            ),
        )
