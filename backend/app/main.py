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
from app.modules.telegram.client import TelegramError

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
    from app.modules.telegram.worker import start_worker, stop_worker

    await _sync_permission_catalog()
    from app.modules.telegram.service import encrypt_legacy_credentials

    try:
        async with SessionLocal() as session:
            await encrypt_legacy_credentials(session)
    except Exception:
        logger.warning("Telegram credential migration deferred until settings are available.")
    # The seeded record vocabularies never pass through the API, so without
    # this attribution their rows show no creator in the master-data lists.
    # Idempotent: rows that already carry a creation event are skipped.
    try:
        from app.modules.master_data.service import ensure_vocabulary_creation_audit

        async with SessionLocal() as session:
            await ensure_vocabulary_creation_audit(session)
            await session.commit()
    except Exception:
        logger.warning("Vocabulary creator attribution deferred until the database is available.")
    start_scheduler()
    start_worker()
    try:
        yield
    finally:
        await stop_scheduler()
        await stop_worker()
        await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=None if settings.environment.lower() == "production" else "/docs",
    redoc_url=None if settings.environment.lower() == "production" else "/redoc",
    openapi_url=None if settings.environment.lower() == "production" else "/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(TelegramError)
async def telegram_error_handler(request: Request, exc: TelegramError) -> JSONResponse:
    return JSONResponse(status_code=503 if exc.retryable else 422, content={"code": "TELEGRAM_UNAVAILABLE", "message": exc.code, "request_id": _request_id(request), "field_errors": {}})

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
        "X-User-Activity",
        "X-Expected-User-Id",
        "X-Request-Id",
        "Idempotency-Key",
    ],
    expose_headers=["X-Request-Id"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    import time

    from app.modules.telegram.monitor import rate_violations, server_errors

    request_id = _request_id(request)
    try:
        response = await call_next(request)
    except Exception:
        server_errors.append(time.monotonic())
        raise
    if response.status_code >= 500:
        server_errors.append(time.monotonic())
    elif response.status_code == 429:
        rate_violations.append(time.monotonic())
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
        # This endpoint authenticates with Telegram's independent webhook secret.
        f"{settings.api_v1_prefix}/integrations/telegram/webhook",
    }
    if request.url.path in public_auth_paths:
        return await call_next(request)

    access_cookie = request.cookies.get(settings.access_cookie_name)
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name) or (request.cookies.get("__Host-refresh_token") if settings.cookie_secure else None)
    uses_bearer = request.headers.get("authorization", "").lower().startswith("bearer ")
    cookie_action = request.url.path in {f"{settings.api_v1_prefix}/auth/refresh", f"{settings.api_v1_prefix}/auth/logout"}
    origin = request.headers.get("origin")
    expected_origin = str(request.base_url).rstrip("/")
    if cookie_action and origin and origin not in {expected_origin, *settings.cors_origin_list}:
        return JSONResponse(status_code=403, content={"code": "CSRF_VALIDATION_FAILED", "message": "Untrusted request origin.", "request_id": _request_id(request), "field_errors": {}})
    if (uses_bearer and not cookie_action) or not (access_cookie or refresh_cookie):
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
                "success": False,
                "code": "CSRF_VALIDATION_FAILED",
                "message": "The CSRF token is missing or invalid.",
                "request_id": request_id,
                "field_errors": {},
                "errors": [],
            },
        )
        response.headers["X-Request-Id"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        return response
    return await call_next(request)


#: Pydantic error type -> stable API code. Anything unknown is an invalid format,
#: which is the truthful, non-leaking answer for a value that did not parse.
_PYDANTIC_CODES = {
    "missing": "REQUIRED",
    "string_too_short": "TOO_SHORT",
    "string_too_long": "TOO_LONG",
    "greater_than": "OUT_OF_RANGE",
    "greater_than_equal": "OUT_OF_RANGE",
    "less_than": "OUT_OF_RANGE",
    "less_than_equal": "OUT_OF_RANGE",
    "decimal_parsing": "INVALID_TYPE",
    "decimal_max_digits": "INVALID_PRECISION",
    "decimal_max_places": "INVALID_PRECISION",
    "int_parsing": "INVALID_TYPE",
    "int_type": "INVALID_TYPE",
    "float_parsing": "INVALID_TYPE",
    "float_type": "INVALID_TYPE",
    "bool_parsing": "INVALID_TYPE",
    "bool_type": "INVALID_TYPE",
    "date_from_datetime_parsing": "INVALID_FORMAT",
    "date_parsing": "INVALID_FORMAT",
    "datetime_parsing": "INVALID_FORMAT",
    "enum": "INVALID_CHOICE",
    "literal_error": "INVALID_CHOICE",
    "value_error": "INVALID_FORMAT",
    "string_pattern_mismatch": "INVALID_FORMAT",
    "string_type": "INVALID_TYPE",
    "list_type": "INVALID_TYPE",
    "dict_type": "INVALID_TYPE",
    "extra_forbidden": "UNKNOWN_FIELD",
}


def _infer_error_code(message: str) -> str:
    """Best-effort code for a field error raised without an explicit one."""
    text = str(message or "").casefold()
    if "required" in text or "left empty" in text:
        return "REQUIRED"
    if "already" in text or "duplicate" in text:
        return "DUPLICATE"
    if "unknown" in text or "not found" in text or "does not match" in text:
        return "REFERENCE_NOT_FOUND"
    if "decimal place" in text or "precision" in text:
        return "INVALID_PRECISION"
    if "at most" in text or "too long" in text:
        return "TOO_LONG"
    if "at least" in text or "too short" in text:
        return "TOO_SHORT"
    if any(word in text for word in ("greater", "less", "positive", "negative", "between", "range")):
        return "OUT_OF_RANGE"
    if "valid date" in text:
        return "INVALID_FORMAT"
    if "choose" in text or "select " in text:
        return "INVALID_CHOICE"
    return "INVALID_FORMAT"


def _error_items(
    field_errors: dict[str, str] | None,
    errors: list[dict] | None,
) -> list[dict[str, str]]:
    """Ordered, coded list derived from whichever representation is present."""
    if errors:
        return [
            {
                "field": str(item.get("field", "")),
                "code": str(item.get("code") or _infer_error_code(str(item.get("message", "")))),
                "message": str(item.get("message", "")),
            }
            for item in errors
        ]
    return [
        {"field": field, "code": _infer_error_code(message), "message": message}
        for field, message in (field_errors or {}).items()
    ]


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        field_errors = detail.get("field_errors") or {}
        items = _error_items(field_errors, detail.get("errors"))
        payload = {
            "success": False,
            "code": detail.get("code", "ERROR"),
            "message": detail.get("message", "Request failed."),
            "request_id": request_id or "",
            "field_errors": field_errors,
            "errors": items,
        }
    else:
        payload = {
            "success": False,
            "code": "ERROR",
            "message": str(detail),
            "request_id": request_id or "",
            "field_errors": {},
            "errors": [],
        }
    response = JSONResponse(status_code=exc.status_code, content=payload, headers=exc.headers)
    if request.url.path.endswith("/auth/refresh") and exc.status_code == 401:
        from app.modules.auth.router import _clear_auth_cookies

        _clear_auth_cookies(response)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    field_errors: dict[str, str] = {}
    items: list[dict[str, str]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", [])]
        # Strip the request-part envelope (`body`, `query`, ...) but keep array
        # indices so `lines.1.amount` still addresses the right row cell.
        if location and location[0] in {"body", "query", "path", "header", "cookie"}:
            location = location[1:]
        field = ".".join(location)
        message = str(error.get("msg", "Invalid value."))
        code = _PYDANTIC_CODES.get(str(error.get("type", "")), "INVALID_FORMAT")
        if field and field not in field_errors:
            field_errors[field] = message
        items.append({"field": field, "code": code, "message": message})
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": "VALIDATION_ERROR",
            "message": "The submitted data is invalid.",
            "request_id": request_id or "",
            "field_errors": field_errors,
            "errors": items,
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
