from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class AppError(Exception):
    message: str
    status_code: int = 400
    code: str = "app_error"


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message=message, status_code=401, code="authentication_failed")


class AuthorizationError(AppError):
    def __init__(self, message: str = "You are not authorized to perform this action") -> None:
        super().__init__(message=message, status_code=403, code="authorization_failed")


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, status_code=404, code="not_found")


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message=message, status_code=409, code="conflict")


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message=message, status_code=422, code="validation_error")


class TokenError(AppError):
    def __init__(self, message: str = "Token is invalid or expired") -> None:
        super().__init__(message=message, status_code=401, code="token_error")


def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )
