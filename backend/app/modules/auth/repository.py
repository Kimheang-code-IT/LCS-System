from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.auth.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRoleAssignment,
    UserSession,
)


class AuthRepository:
    """Persistence operations for identities, sessions, roles and permissions.

    The repository deliberately does not commit: authentication workflows own
    their transaction boundary and can combine these operations atomically.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def user_by_login(self, login: str) -> User | None:
        result = await self.session.execute(select(User).where(or_(User.username == login, User.email == login)))
        return result.scalars().first()

    async def user(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def credential_for_user(self, user_id: int) -> UserCredential | None:
        result = await self.session.execute(select(UserCredential).where(UserCredential.user_id == user_id))
        return result.scalars().first()

    async def session_by_refresh_hash(self, token_hash: str) -> UserSession | None:
        result = await self.session.execute(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        return result.scalars().first()

    async def active_sessions(self, user_id: int) -> list[UserSession]:
        result = await self.session.execute(
            select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        )
        return list(result.scalars().all())

    async def active_role_code(self, user_id: int) -> str | None:
        result = await self.session.execute(
            select(Role.code)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == Role.id)
            .where(UserRoleAssignment.user_id == user_id, UserRoleAssignment.expires_at.is_(None))
        )
        return result.scalars().first()

    async def assignment_rows(self, user_id: int) -> list[tuple[UserRoleAssignment, str]]:
        result = await self.session.execute(
            select(UserRoleAssignment, Role.code)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(UserRoleAssignment.user_id == user_id)
        )
        return list(result.all())

    async def users_with_role_codes(self, page: PageParams | None = None) -> list[tuple[User, list[str]]]:
        orders = list_sort_orders(User, page, User.id) if page else [User.id]
        users = list((await self.session.execute(select(User).order_by(*orders))).scalars().all())
        if not users:
            return []
        role_result = await self.session.execute(
            select(UserRoleAssignment.user_id, Role.code)
            .join(Role, Role.id == UserRoleAssignment.role_id)
            .where(
                UserRoleAssignment.user_id.in_([user.id for user in users]),
                UserRoleAssignment.expires_at.is_(None),
            )
        )
        codes: defaultdict[int, list[str]] = defaultdict(list)
        for user_id, code in role_result.all():
            codes[user_id].append(code)
        return [(user, codes[user.id]) for user in users]

    async def roles_with_permissions(
        self, page: PageParams | None = None, *, q: str | None = None, status: str | None = None
    ) -> tuple[list[tuple[Role, list[str]]], int]:
        orders = list_sort_orders(Role, page, Role.id) if page else [Role.id]
        stmt = select(Role)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(Role.name.ilike(pattern), Role.code.ilike(pattern)))
        if status:
            stmt = stmt.where(Role.status == status.upper())
        total = await count_query(self.session, stmt)
        query = stmt.order_by(*orders)
        if page:
            query = query.offset(page.offset).limit(page.page_size)
        roles = list((await self.session.execute(query)).scalars().all())
        if not roles:
            return [], total
        permission_result = await self.session.execute(
            select(RolePermission.role_id, Permission.code)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id.in_([role.id for role in roles]))
        )
        permissions: defaultdict[int, list[str]] = defaultdict(list)
        for role_id, code in permission_result.all():
            permissions[role_id].append(code)
        return [(role, permissions[role.id]) for role in roles], total
