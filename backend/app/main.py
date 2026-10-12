from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import close_redis
from app.core.security import constant_time_compare, verify_csrf_token
from app.modules.backup.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", "")
    if existing:
        return existing
    supplied = request.headers.get("X-Request-Id", "")
    request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied) else uuid.uuid4().hex
    request.state.request_id = request_id
    return request_id


async def _sync_permission_catalog() -> None:
    """Best-effort: add newly introduced permissions/roles for existing installs."""
    from app.core.bootstrap import ensure_permission_catalog

    try:
        async with SessionLocal() as session:
            await ensure_permission_catalog(session)
    except Exception as exc:  # noqa: BLE001 - startup must not fail if DB is not ready
        logger.warning("Permission catalog sync skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _sync_permission_catalog()
    start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler()
        await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=None if settings.environment.lower() == "production" else "/docs",
    redoc_url=None if settings.environment.lower() == "production" else "/redoc",
    openapi_url=None if settings.environment.lower() == "production" else "/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        settings.csrf_header_name,
        "X-Requested-With",
        "X-Request-Id",
        "Idempotency-Key",
    ],
    expose_headers=["X-Request-Id"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = _request_id(request)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    if request.url.path.startswith(settings.api_v1_prefix):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Protect browser cookie sessions with a signed double-submit token."""
    if request.method.upper() in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return await call_next(request)

    public_auth_paths = {
        f"{settings.api_v1_prefix}/auth/login",
        f"{settings.api_v1_prefix}/auth/forgot-password",
        f"{settings.api_v1_prefix}/auth/forgot-password/verify",
        f"{settings.api_v1_prefix}/auth/forgot-password/resend",
        f"{settings.api_v1_prefix}/auth/forgot-password/reset",
        f"{settings.api_v1_prefix}/auth/setup/initialize",
    }
    if request.url.path in public_auth_paths:
        return await call_next(request)

    access_cookie = request.cookies.get(settings.access_cookie_name)
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name)
    uses_bearer = request.headers.get("authorization", "").lower().startswith("bearer ")
    if uses_bearer or not (access_cookie or refresh_cookie):
        return await call_next(request)

    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    header_token = request.headers.get(settings.csrf_header_name, "")
    valid = (
        bool(refresh_cookie and cookie_token and header_token)
        and constant_time_compare(cookie_token, header_token)
        and verify_csrf_token(cookie_token, refresh_cookie)
    )
    if not valid:
        request_id = _request_id(request)
        response = JSONResponse(
            status_code=403,
            content={
                "code": "CSRF_VALIDATION_FAILED",
                "message": "The CSRF token is missing or invalid.",
                "request_id": request_id,
                "field_errors": {},
            },
        )
        response.headers["X-Request-Id"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        payload = {
            "code": detail.get("code", "ERROR"),
            "message": detail.get("message", "Request failed."),
            "request_id": request_id or "",
            "field_errors": detail.get("field_errors") or {},
        }
    else:
        payload = {"code": "ERROR", "message": str(detail), "request_id": request_id or "", "field_errors": {}}
    return JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    field_errors = {
        ".".join(str(part) for part in error.get("loc", []) if part != "body"): error.get("msg", "Invalid")
        for error in exc.errors()
    }
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "The submitted data is invalid.",
            "request_id": request_id or "",
            "field_errors": field_errors,
        },
    )


@app.get("/health")
async def root_health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    from sqlalchemy import text

    from app.core.database import SessionLocal
    from app.core.redis import redis_health

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})

    # Redis is an optional accelerator (cache + rate limiting fall back to
    # in-process state). Report it, but do not fail readiness when it is down.
    redis_status = await redis_health()
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready" if redis_status != "down" else "degraded",
            "database": "up",
            "redis": redis_status,
        },
    )


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict:
    docs = None if settings.environment.lower() == "production" else "/docs"
    return {"name": settings.app_name, "docs": docs, "api": settings.api_v1_prefix}
