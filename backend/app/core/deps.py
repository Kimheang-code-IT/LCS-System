from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request
from jwt import ExpiredSignatureError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.exceptions import AccessDenied, AuthRequired, Conflict
from app.core.security import decode_token
from app.modules.auth import service as auth_service
from app.modules.auth.models import User, UserCredential, UserSession

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


def _refuse_until_password_changed(request: Request, payload: dict, *, required: bool | None = None, message: str | None = None) -> None:
    """Block the API for a credential that must be replaced.

    The flag rides in the access token (``pwd``) rather than being read from the
    database, so this costs no query. A token issued before the reset cannot
    bypass it either: setting the flag revokes every session and bumps the token
    version, so that token is already rejected above.
    """
    if required is None:
        required = bool(payload.get("pwd"))
    if not required:
        return
    path = request.url.path.rstrip("/")
    if any(path.endswith(suffix) for suffix in _PASSWORD_CHANGE_ALLOWED_SUFFIXES):
        return
    raise AccessDenied(
        message or "Your password was set by an administrator. Choose a new one to continue."
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
    except ExpiredSignatureError as exc:
        raise AuthRequired("Access token expired.", code="ACCESS_TOKEN_EXPIRED") from exc
    except Exception as exc:  # noqa: BLE001
        raise AuthRequired("Invalid access token.") from exc
    if payload.get("type") != "access":
        raise AuthRequired("Invalid token type.")
    user_id = payload.get("sub")
    if user_id is None:
        raise AuthRequired()
    sid = payload.get("sid")
    if sid is None:
        raise AuthRequired("Renew your session.", code="ACCESS_TOKEN_EXPIRED")
    try:
        identity = (await session.execute(select(User, UserSession).join(
            UserSession, UserSession.user_id == User.id,
        ).where(User.id == int(user_id), UserSession.id == int(sid)))).one_or_none()
    except (TypeError, ValueError) as exc:
        raise AuthRequired("Invalid session.") from exc
    if identity is None:
        raise AuthRequired("Session has been revoked.", code="SESSION_REVOKED")
    user, record = identity
    expected_user = request.headers.get("X-Expected-User-Id")
    if expected_user is not None and expected_user != str(user.id):
        raise Conflict("SESSION_ACCOUNT_CHANGED", "Another account signed in. Sign in to the original account before submitting this draft.")
    if str(user.status or "").upper() not in {"ACTIVE"}:
        raise AuthRequired("This account is not active.", code="SESSION_REVOKED")
    if int(payload.get("tv", 0)) != int(getattr(user, "token_version", 0) or 0):
        raise AuthRequired("Session has been revoked. Please sign in again.", code="SESSION_REVOKED")
    _refuse_until_password_changed(request, payload)

    from datetime import UTC, datetime, timedelta

    from app.modules.settings.service import get_access_policy

    policy = await get_access_policy(session)
    record = await auth_service.validate_session(session, record, user.id)
    request.state.auth_session_id = record.id
    # Only an explicit user interaction marker extends idle activity. Passive
    # GETs, permission probes and refresh requests do not keep sessions alive.
    now = datetime.now(UTC)
    if request.headers.get("X-User-Activity") == "1" and not request.url.path.endswith("/auth/me"):
        previous = record.last_activity_at or record.created_at
        if now - auth_service._as_utc(previous) >= timedelta(seconds=15):
            await session.execute(update(UserSession).where(
                UserSession.id == record.id, UserSession.revoked_at.is_(None),
                UserSession.last_activity_at == record.last_activity_at,
            ).values(last_activity_at=now))
            await session.commit()

    credential = None
    if policy["passwordExpiryDays"] > 0 or (
        policy["requirePasswordChange"] and policy["requirePasswordChangeSince"]
    ):
        credential = await session.get(UserCredential, user.id)
    if credential is not None:
        changed_at = credential.password_changed_at
        if changed_at is not None and changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=UTC)
        expired = bool(
            policy["passwordExpiryDays"] > 0
            and changed_at is not None
            and changed_at + timedelta(days=policy["passwordExpiryDays"]) <= datetime.now(UTC)
        )
        rollout_since = policy["requirePasswordChangeSince"]
        due_to_policy = False
        if policy["requirePasswordChange"] and rollout_since and changed_at is not None:
            try:
                since = datetime.fromisoformat(rollout_since)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=UTC)
                due_to_policy = changed_at < since
            except ValueError:
                due_to_policy = False
        if expired or due_to_policy:
            if not credential.must_change_password:
                credential.must_change_password = True
                await session.commit()
            _refuse_until_password_changed(
                request,
                payload,
                required=True,
                message="Your password must be changed before you can continue.",
            )

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
    from app.core.access_modes import enforce_access_modes

    await enforce_access_modes(request, context, session)
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


def require_any_permission(*codes: str) -> Callable[..., RequestContext]:
    """Accept a caller holding at least one of ``codes``.

    Used where a precise matrix page code is preferred but a legacy coarse
    permission must keep working for roles created before the matrix existed.
    """

    async def dependency(
        context: RequestContext = Depends(get_current_context),
    ) -> RequestContext:
        if not context.has_any_permission(*codes):
            # The denial audit is written centrally by the AccessDenied handler.
            raise AccessDenied("Missing permission: " + " or ".join(codes))
        return context

    return dependency


def require_permission(*codes: str) -> Callable[..., RequestContext]:
    """Require every code in ``codes`` (the common case is one code)."""

    async def dependency(
        context: RequestContext = Depends(get_current_context),
    ) -> RequestContext:
        for code in codes:
            if not context.has_permission(code):
                raise AccessDenied(f"Missing permission: {code}")
        return context

    return dependency

