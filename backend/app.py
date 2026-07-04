from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.exceptions import AppError, app_error_handler
from backend.core.logging import configure_logging
from backend.core.middleware import JWTContextMiddleware

settings = get_settings()
configure_logging(settings)

app = FastAPI(
    title="AI Workforce API",
    version="0.1.0",
    description="Authentication, organization, tenancy, and integration services for AI Workforce.",
    openapi_url=settings.openapi_url,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JWTContextMiddleware, settings=settings)

app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "code": "validation_error"})


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/healthz", include_in_schema=False)
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
