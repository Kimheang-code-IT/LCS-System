from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, get_optional_context, require_permission
from app.core.exceptions import AccessDenied, AuthRequired, ValidationFailed
from app.core.pagination import PageParams, page_params
from app.core.rate_limit import client_ip, enforce_rate_limit, opaque_key
from app.core.security import create_csrf_token
from app.modules.audit.service import write_audit
from app.modules.auth import service
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    RoleAssignmentCreate,
    RoleCreate,
    RoleDuplicate,
    RoleUpdate,
    SetPasswordRequest,
    UserCreate,
    UserUpdate,
    VerifyCodeRequest,
)

router = APIRouter()


async def _record_rejected_admin_operation(
    session: AsyncSession,
    context: RequestContext,
    error: AccessDenied,
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    action: str,
    metadata: dict | None = None,
) -> None:
    """Persist denied administrative attempts after discarding pending edits."""
    await session.rollback()
    await write_audit(
        session,
        context,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        result="REJECTED",
        reason=error.message,
        metadata=metadata,
    )
    await session.commit()


def _set_auth_cookies(response: Response, access: str, refresh: str, *, remember_me: bool) -> None:
    access_max_age = settings.access_token_expire_minutes * 60
    refresh_max_age = settings.refresh_token_expire_days * 86400
    response.set_cookie(
        settings.access_cookie_name,
        access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=access_max_age if remember_me else None,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=refresh_max_age if remember_me else None,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        create_csrf_token(refresh),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=refresh_max_age if remember_me else None,
        domain=settings.cookie_domain,
        path="/",
    )


def _auth_tokens(access: str, refresh: str) -> dict[str, str]:
    if not settings.auth_return_tokens:
        return {}
    return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer"}


def _clear_auth_cookies(response: Response) -> None:
    for name in (settings.access_cookie_name, settings.refresh_cookie_name, settings.csrf_cookie_name):
        # Secure must be echoed so ``__Host-`` prefixed cookies can be deleted.
        response.delete_cookie(
            name,
            path="/",
            domain=settings.cookie_domain,
            secure=settings.cookie_secure,
            samesite="lax",
        )


@router.get("/auth/setup/status")
async def setup_status(session: AsyncSession = Depends(get_session)) -> dict:
    return {"data": await service.setup_status(session)}


@router.post("/auth/setup/initialize", status_code=status.HTTP_201_CREATED)
async def setup_initialize(
    request: Request,
    payload: dict = Body(default={}),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await enforce_rate_limit(f"setup:ip:{opaque_key(client_ip(request))}", limit=10, window_seconds=3600)
    return {"data": await service.setup_initialize(session, payload)}


@router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    login_value = payload.username or payload.email or ""
    if not login_value:
        raise ValidationFailed("Username or email is required.")
    await enforce_rate_limit(f"login:ip:{opaque_key(client_ip(request))}", limit=30, window_seconds=300)
    await enforce_rate_limit(f"login:account:{opaque_key(login_value)}", limit=10, window_seconds=900)
    user = await service.authenticate(session, login_value, payload.password)
    context = await service.build_context(
        session,
        user,
        request_id=getattr(request.state, "request_id", ""),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _, role_codes = await service.resolve_permissions(session, user.id)
    access, refresh = await service.create_session(
        session,
        user,
        ip=context.ip_address,
        user_agent=context.user_agent,
        remember_me=payload.remember_me,
    )
    auth_user = service.build_auth_user(
        context,
        service.role_label(role_codes),
        must_change_password=await service.must_change_password(session, user.id),
    )
    await write_audit(
        session,
        context,
        event_type="LOGIN",
        entity_type="user",
        entity_id=user.id,
        action="login",
        after={"email": user.email},
    )
    await session.commit()
    _set_auth_cookies(response, access, refresh, remember_me=payload.remember_me)
    return {
        "data": {
            "user": auth_user,
            **_auth_tokens(access, refresh),
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = None,
    context: RequestContext | None = Depends(get_optional_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    refresh_token = refresh_token or request.cookies.get(settings.refresh_cookie_name)
    # Logout must revoke the refresh session even when the short-lived access
    # token has already expired; the refresh token identifies the session.
    user_id = await service.revoke_session(session, context.user_id if context else None, refresh_token)
    actor_id = context.user_id if context else user_id
    if actor_id is None:
        raise AuthRequired("Session is no longer valid.")
    await write_audit(
        session, context, event_type="LOGOUT", entity_type="user", entity_id=actor_id, action="logout"
    )
    await session.commit()
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/auth/refresh")
async def refresh(
    payload: RefreshRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> dict:
    token = payload.refresh_token or request.cookies.get(settings.refresh_cookie_name) or ""
    user, access, refresh_token, remember_me = await service.rotate_refresh_token(
        session,
        token,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    context = await service.build_context(session, user, request_id=getattr(request.state, "request_id", ""))
    _, role_codes = await service.resolve_permissions(session, user.id)
    _set_auth_cookies(response, access, refresh_token, remember_me=remember_me)
    return {
        "data": {
            "user": service.build_auth_user(
                context,
                service.role_label(role_codes),
                must_change_password=await service.must_change_password(session, user.id),
            ),
            **_auth_tokens(access, refresh_token),
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    }


@router.get("/auth/me")
async def me(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    page_permissions, page_access = service.resolve_page_keys(context.permissions, context.is_platform_admin)
    return {
        "data": {
            "id": context.user_id,
            "name": context.display_name,
            "email": context.email,
            "avatar": context.avatar,
            "permissions": page_access,
            "sourcePermissions": page_permissions,
            # Reported so a reload recovers the forced-change state from the
            # server rather than trusting a cookie that may be stale.
            "mustChangePassword": await service.must_change_password(session, context.user_id),
        }
    }


@router.post("/auth/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await enforce_rate_limit(f"reset-request:ip:{opaque_key(client_ip(request))}", limit=10, window_seconds=3600)
    await enforce_rate_limit(f"reset-request:account:{opaque_key(payload.email)}", limit=5, window_seconds=3600)
    await service.request_password_reset(session, payload.email)
    return {"data": {"sent": True}}


@router.post("/auth/forgot-password/verify")
async def verify_code(
    payload: VerifyCodeRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await enforce_rate_limit(f"reset-verify:ip:{opaque_key(client_ip(request))}", limit=20, window_seconds=900)
    await enforce_rate_limit(f"reset-verify:account:{opaque_key(payload.email)}", limit=8, window_seconds=900)
    verified = await service.verify_reset_code(session, payload.email, payload.code)
    if not verified:
        raise ValidationFailed("Invalid reset code.")
    return {"data": {"verified": True}}


@router.post("/auth/forgot-password/resend")
async def resend_code(
    payload: ForgotPasswordRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await enforce_rate_limit(f"reset-resend:ip:{opaque_key(client_ip(request))}", limit=10, window_seconds=3600)
    await enforce_rate_limit(f"reset-resend:account:{opaque_key(payload.email)}", limit=5, window_seconds=3600)
    await service.request_password_reset(session, payload.email)
    return {"data": {"sent": True}}


@router.post("/auth/forgot-password/reset")
async def reset_password(
    payload: ResetPasswordRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> dict:
    await enforce_rate_limit(f"reset-submit:ip:{opaque_key(client_ip(request))}", limit=20, window_seconds=900)
    await enforce_rate_limit(f"reset-submit:account:{opaque_key(payload.email)}", limit=8, window_seconds=900)
    if payload.password_confirmation is not None and payload.password != payload.password_confirmation:
        raise ValidationFailed("Passwords do not match.")
    await service.reset_password(session, payload.email, payload.code, payload.password)
    return {"data": {"reset": True}}


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.password_confirmation is not None and payload.password != payload.password_confirmation:
        raise ValidationFailed("Passwords do not match.")
    user = await service.get_user(session, context.user_id)
    await service.change_password(session, user, payload.current_password, payload.password)
    await write_audit(
        session, context, event_type="PASSWORD_CHANGED", entity_type="user",
        entity_id=context.user_id, action="change_password",
    )
    await session.commit()
    # Every session (including this one) is revoked by the password change.
    _clear_auth_cookies(response)
    return {"data": {"changed": True}}


@router.post("/auth/profile/avatar")
async def update_profile_avatar(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    avatar = str(payload.get("avatar") or "").strip() or None
    result = await service.set_user_avatar(session, context, avatar)
    return {"data": {"avatar": result}}


@router.delete("/auth/profile/avatar")
async def remove_profile_avatar(
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await service.clear_user_avatar(session, context)
    return {"data": {"removed": True}}



@router.get("/users")
async def list_users(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("user.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_users(session, page)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await service.create_user(session, payload.model_dump(), context)
    await write_audit(
        session, context, event_type="USER_CREATED", entity_type="user", entity_id=user.id,
        action="create", after={"username": user.username, "email": user.email},
    )
    await session.commit()
    return {"data": await service.user_payload(session, user)}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    context: RequestContext = Depends(require_permission("user.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await service.get_user(session, user_id)
    return {"data": await service.user_payload(session, user)}


@router.post("/users/{user_id}/password")
async def set_user_password(
    user_id: int,
    payload: SetPasswordRequest,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set a password on another account.

    Gated on ``user.manage`` rather than a new permission: creating a user already
    means choosing that user's password, so this is a recovery path, not a wider
    capability. The password is hashed and never returned.
    """
    user = await service.set_user_password(
        session,
        context,
        user_id,
        payload.password,
        must_change=payload.must_change_password,
    )
    await write_audit(
        session,
        context,
        event_type="USER_PASSWORD_SET_BY_ADMIN",
        entity_type="user",
        entity_id=user.id,
        action="reset_password",
        after={"username": user.username, "mustChangePassword": payload.must_change_password},
    )
    await session.commit()
    return {"data": await service.user_payload(session, user)}


@router.patch("/users/{user_id}")
@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    changes = payload.model_dump(exclude_none=True)
    try:
        user = await service.update_user(session, user_id, changes, context)
    except AccessDenied as exc:
        await _record_rejected_admin_operation(
            session, context, exc, event_type="USER_UPDATE_REJECTED",
            entity_type="user", entity_id=user_id, action="update", metadata={"fields": sorted(changes)},
        )
        raise
    await write_audit(
        session, context, event_type="USER_UPDATED", entity_type="user", entity_id=user_id,
        action="update", after=changes,
    )
    await session.commit()
    return {"data": await service.user_payload(session, user)}


@router.delete("/users")
async def delete_users(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    try:
        await service.delete_users(session, ids, context)
    except AccessDenied as exc:
        await _record_rejected_admin_operation(
            session, context, exc, event_type="USER_DELETE_REJECTED",
            entity_type="user", entity_id=0, action="delete", metadata={"ids": ids},
        )
        raise
    await write_audit(
        session, context, event_type="USER_DELETED", entity_type="user", entity_id=0,
        action="delete", metadata={"ids": ids},
    )
    await session.commit()
    return {"data": {"removed": len(ids)}}


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_user_sessions(
    user_id: int,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await service.force_logout_user(session, user_id)
    await write_audit(
        session, context, event_type="SESSION_REVOKED", entity_type="user", entity_id=user_id,
        action="revoke_sessions",
    )
    await session.commit()
    return {"data": {"revoked": True}}


@router.get("/users/{user_id}/role-assignments")
async def list_role_assignments(
    user_id: int,
    context: RequestContext = Depends(require_permission("role.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_role_assignments(session, user_id)}


@router.post("/users/{user_id}/role-assignments", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: int,
    payload: RoleAssignmentCreate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    requested = payload.model_dump()
    try:
        assignment = await service.assign_role(session, user_id, requested, context)
    except AccessDenied as exc:
        await _record_rejected_admin_operation(
            session, context, exc, event_type="ROLE_ASSIGNMENT_REJECTED",
            entity_type="user", entity_id=user_id, action="assign_role",
            metadata={"roleId": payload.role_id, "roleCode": payload.role_code},
        )
        raise
    await write_audit(
        session, context, event_type="ROLE_ASSIGNED", entity_type="user", entity_id=user_id,
        action="assign_role",
        after={"roleId": assignment.role_id, "roleCode": payload.role_code},
    )
    await session.commit()
    return {"data": {"id": assignment.id, "userId": assignment.user_id, "roleId": assignment.role_id}}


@router.get("/roles")
async def list_roles(
    page: PageParams = Depends(page_params),
    context: RequestContext = Depends(require_permission("role.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_roles(session, page, q=page.q, status=page.status)}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await service.create_role(session, payload.model_dump(), context)
    await write_audit(
        session, context, event_type="ROLE_CREATED", entity_type="role", entity_id=role.id,
        action="create", after={"code": role.code, "permissions": payload.permissions},
    )
    await session.commit()
    return {"data": await service.role_payload(session, role)}


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    before = await service.get_role(session, role_id)
    changes = payload.model_dump(exclude_none=True)
    try:
        role = await service.update_role(session, role_id, changes, context)
    except AccessDenied as exc:
        await _record_rejected_admin_operation(
            session, context, exc, event_type="ROLE_UPDATE_REJECTED",
            entity_type="role", entity_id=role_id, action="update", metadata={"fields": sorted(changes)},
        )
        raise
    await write_audit(
        session, context, event_type="ROLE_UPDATED", entity_type="role", entity_id=role_id,
        action="update",
        before={"permissions": before.get("permissions"), "status": before.get("status")},
        after=changes,
    )
    await session.commit()
    return {"data": await service.role_payload(session, role)}


@router.post("/roles/{role_id}/duplicate", status_code=status.HTTP_201_CREATED)
async def duplicate_role(
    role_id: int,
    payload: RoleDuplicate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await service.duplicate_role(session, role_id, payload.model_dump(exclude_none=True), context)
    await write_audit(
        session,
        context,
        event_type="ROLE_DUPLICATED",
        entity_type="role",
        entity_id=role.id,
        action="duplicate",
        after={"sourceRoleId": role_id, "code": role.code},
    )
    await session.commit()
    return {"data": await service.role_payload(session, role)}


@router.get("/roles/{role_id}")
async def get_role(
    role_id: int,
    context: RequestContext = Depends(require_permission("role.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.get_role(session, role_id)}


@router.delete("/roles")
async def delete_roles(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    try:
        await service.delete_roles(session, ids)
    except AccessDenied as exc:
        await _record_rejected_admin_operation(
            session, context, exc, event_type="ROLE_DELETE_REJECTED",
            entity_type="role", entity_id=0, action="delete", metadata={"ids": ids},
        )
        raise
    await write_audit(
        session, context, event_type="ROLE_DELETED", entity_type="role", entity_id=0,
        action="delete", metadata={"ids": ids},
    )
    await session.commit()
    return {"data": {"removed": len(ids)}}


@router.get("/permissions")
async def list_permissions(
    context: RequestContext = Depends(require_permission("role.read")),
) -> dict:
    from app.core.permissions import PERMISSION_CATALOG, permission_name

    return {
        "data": [
            {"code": code, "resource": resource, "action": action, "name": permission_name(code)}
            for code, resource, action in PERMISSION_CATALOG
        ]
    }
