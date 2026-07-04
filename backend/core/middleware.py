from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.core.config import Settings
from backend.core.exceptions import TokenError
from backend.core.security import TokenType, decode_token


class JWTContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings, public_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.settings = settings
        self.public_paths = public_paths or {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/healthz",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/accept-invite",
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.current_token = None
        request.state.current_user_claims = None
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
            try:
                request.state.current_user_claims = decode_token(
                    token, self.settings, expected_type=TokenType.ACCESS
                )
                request.state.current_token = token
            except TokenError:
                if request.url.path not in self.public_paths:
                    raise
        return await call_next(request)
