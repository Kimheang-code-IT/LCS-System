from __future__ import annotations

import secrets

from fastapi import APIRouter, Body, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.context import RequestContext
from app.core.database import get_session
from app.core.deps import get_current_context, require_permission
from app.core.exceptions import AuthRequired, ValidationFailed
from app.modules.audit.service import write_audit
from app.modules.auth import service
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    RoleAssignmentCreate,
    RoleCreate,
    RoleUpdate,
    UserCreate,
    UserUpdate,
    VerifyCodeRequest,
)

router = APIRouter()


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        settings.access_cookie_name,
        access,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        domain=settings.cookie_domain,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        secrets.token_urlsafe(16),
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (settings.access_cookie_name, settings.refresh_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/", domain=settings.cookie_domain)


@router.post("/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    login_value = payload.username or payload.email or ""
    if not login_value:
        raise ValidationFailed("Username or email is required.")
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
        session, user, ip=context.ip_address, user_agent=context.user_agent
    )
    auth_user = service.build_auth_user(context, service.role_label(role_codes))
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
    _set_auth_cookies(response, access, refresh)
    return {
        "data": {
            "user": auth_user,
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = None,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    refresh_token = refresh_token or request.cookies.get(settings.refresh_cookie_name)
    await service.revoke_session(session, context.user_id, refresh_token)
    await write_audit(
        session, context, event_type="LOGOUT", entity_type="user", entity_id=context.user_id, action="logout"
    )
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/auth/refresh")
async def refresh(
    payload: RefreshRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> dict:
    token = payload.refresh_token or request.cookies.get(settings.refresh_cookie_name) or ""
    user, access, refresh_token = await service.rotate_refresh_token(
        session,
        token,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    context = await service.build_context(session, user, request_id=getattr(request.state, "request_id", ""))
    _, role_codes = await service.resolve_permissions(session, user.id)
    _set_auth_cookies(response, access, refresh_token)
    return {
        "data": {
            "user": service.build_auth_user(context, service.role_label(role_codes)),
            "access_token": access,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }
    }


@router.get("/auth/me")
async def me(context: RequestContext = Depends(get_current_context)) -> dict:
    return {
        "data": {
            "id": context.user_id,
            "name": context.display_name,
            "email": context.email,
            "avatar": context.avatar,
            "permissions": service.resolve_page_keys(context.permissions, context.is_platform_admin)[1],
            "sourcePermissions": service.resolve_page_keys(context.permissions, context.is_platform_admin)[0],
        }
    }


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)) -> dict:
    await service.request_password_reset(session, payload.email)
    return {"data": {"sent": True}}


@router.post("/auth/forgot-password/verify")
async def verify_code(payload: VerifyCodeRequest, session: AsyncSession = Depends(get_session)) -> dict:
    verified = await service.verify_reset_code(session, payload.email, payload.code)
    if not verified:
        raise ValidationFailed("Invalid reset code.")
    return {"data": {"verified": True}}


@router.post("/auth/forgot-password/resend")
async def resend_code(payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)) -> dict:
    await service.request_password_reset(session, payload.email)
    return {"data": {"sent": True}}


@router.post("/auth/forgot-password/reset")
async def reset_password(payload: ResetPasswordRequest, session: AsyncSession = Depends(get_session)) -> dict:
    if payload.password_confirmation is not None and payload.password != payload.password_confirmation:
        raise ValidationFailed("Passwords do not match.")
    await service.reset_password(session, payload.email, payload.code, payload.password)
    return {"data": {"reset": True}}


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    context: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.password_confirmation is not None and payload.password != payload.password_confirmation:
        raise ValidationFailed("Passwords do not match.")
    user = await session.get(User, context.user_id)
    if user is None:
        raise AuthRequired()
    await service.change_password(session, user, payload.current_password, payload.password)
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
    context: RequestContext = Depends(require_permission("user.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_users(session)}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await service.create_user(session, payload.model_dump(), context)
    return {"data": {"id": user.id, "username": user.username, "email": user.email, "displayName": user.display_name, "status": user.status}}


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    context: RequestContext = Depends(require_permission("user.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise AuthRequired("User not found.")
    return {"data": {"id": user.id, "username": user.username, "email": user.email, "displayName": user.display_name, "phone": user.phone, "status": user.status}}


@router.patch("/users/{user_id}")
@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await service.update_user(session, user_id, payload.model_dump(exclude_none=True))
    return {"data": {"id": user.id, "username": user.username, "email": user.email, "status": user.status}}


@router.delete("/users")
async def delete_users(
    payload: dict = Body(default={}),
    context: RequestContext = Depends(require_permission("user.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ids = [int(value) for value in payload.get("ids") or [] if str(value).isdigit()]
    await service.delete_users(session, ids)
    return {"data": {"removed": len(ids)}}


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
    assignment = await service.assign_role(session, user_id, payload.model_dump(), context)
    return {"data": {"id": assignment.id, "userId": assignment.user_id, "roleId": assignment.role_id}}


@router.get("/roles")
async def list_roles(
    context: RequestContext = Depends(require_permission("role.read")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"data": await service.list_roles(session)}


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await service.create_role(session, payload.model_dump())
    return {"data": await service.role_payload(session, role)}


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    context: RequestContext = Depends(require_permission("role.manage")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await service.update_role(session, role_id, payload.model_dump(exclude_none=True))
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
    await service.delete_roles(session, ids)
    return {"data": {"removed": len(ids)}}


@router.get("/permissions")
async def list_permissions(
    context: RequestContext = Depends(require_permission("role.read")),
) -> dict:
    from app.core.permissions import PERMISSION_CATALOG

    return {
        "data": [
            {"code": code, "resource": resource, "action": action, "name": permission_name}
            for code, resource, action in PERMISSION_CATALOG
            for permission_name in [code.replace(".", " ").replace("_", " ").title()]
        ]
    }
