from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.exceptions import AccessDenied, AuthRequired
from app.core.security import decode_token
from app.modules.auth import service as auth_service
from app.modules.auth.models import User

#: Routes a caller may still reach while a password change is outstanding. Each
#: is needed to complete the change or to leave: refreshing the token keeps the
#: session alive, reading the profile tells the UI who is signed in, and logout
#: has to remain possible. Everything else answers
#: ``403 PASSWORD_CHANGE_REQUIRED``.
_PASSWORD_CHANGE_ALLOWED_SUFFIXES = (
    "/auth/change-password",
    "/auth/logout",
    "/auth/refresh",
    "/auth/me",
)


def _refuse_until_password_changed(request: Request, payload: dict) -> None:
    """Block the API for a credential an administrator set.

    The flag rides in the access token (``pwd``) rather than being read from the
    database, so this costs no query. A token issued before the reset cannot
    bypass it either: setting the flag revokes every session and bumps the token
    version, so that token is already rejected above.
    """
    if not payload.get("pwd"):
        return
    path = request.url.path.rstrip("/")
    if any(path.endswith(suffix) for suffix in _PASSWORD_CHANGE_ALLOWED_SUFFIXES):
        return
    raise AccessDenied(
        "Your password was set by an administrator. Choose a new one to continue."
    )


async def get_current_context(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RequestContext:
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get(settings.access_cookie_name)
    if not token:
        raise AuthRequired()
    try:
        payload = decode_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AuthRequired("Invalid or expired access token.") from exc
    if payload.get("type") != "access":
        raise AuthRequired("Invalid token type.")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthRequired()
    user = await session.get(User, int(user_id))
    if user is None:
        raise AuthRequired("User not found.")
    if str(user.status or "").upper() not in {"ACTIVE"}:
        raise AuthRequired("This account is not active.")
    if int(payload.get("tv", 0)) != int(getattr(user, "token_version", 0) or 0):
        raise AuthRequired("Session has been revoked. Please sign in again.")
    _refuse_until_password_changed(request, payload)
    request_id = getattr(request.state, "request_id", None) or payload.get("jti", "")
    context = await auth_service.build_context(
        session,
        user,
        request_id=request_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    request.state.context = context
    request.state.actor_user_id = context.user_id
    return context


async def get_optional_context(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RequestContext | None:
    """Resolve the caller when possible, falling back to the access cookie.

    Returns ``None`` when neither a bearer token nor a valid cookie session is
    present (or the access token is expired/revoked).
    """
    try:
        return await get_current_context(request, authorization, session)
    except HTTPException:
        return None


def require_permission(code: str) -> Callable[..., RequestContext]:
    async def dependency(
        context: RequestContext = Depends(get_current_context),
        session: AsyncSession = Depends(get_session),
    ) -> RequestContext:
        if not context.has_permission(code):
            # Permission denials happen before the route handler, so record them
            # here; otherwise direct API bypass attempts would leave no trace.
            from app.modules.audit.service import write_audit

            await write_audit(
                session,
                context,
                event_type="AUTHORIZATION_DENIED",
                entity_type="permission",
                entity_id=0,
                action=code,
                result="REJECTED",
                reason=f"Missing permission: {code}",
            )
            await session.commit()
            raise AccessDenied(f"Missing permission: {code}")
        return context

    return dependency
