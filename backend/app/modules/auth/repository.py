from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import authorization
from app.core.pagination import PageParams, count_query, list_sort_orders
from app.modules.auth.models import Role, User, UserCredential, UserSession


class AuthRepository:
    """Persistence operations for identities and sessions.

    Roles and permissions live in ``casbin_rule`` and are read through
    ``app.core.authorization``; this repository only keeps the user/role rows and
    the authentication records. It deliberately does not commit: authentication
    workflows own their transaction boundary.
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

    async def users_with_role_codes(
        self, page: PageParams | None = None
    ) -> tuple[list[tuple[User, list[str]]], int]:
        orders = list_sort_orders(User, page, User.id) if page else [User.id]
        stmt = select(User)
        total = await count_query(self.session, stmt) if page is not None else 0
        query = stmt.order_by(*orders)
        if page is not None:
            query = query.offset(page.offset).limit(page.page_size)
        users = list((await self.session.execute(query)).scalars().all())
        codes = await authorization.users_role_codes(self.session, [user.id for user in users])
        return [(user, codes.get(user.id, [])) for user in users], (total or len(users))

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
        codes = await authorization.roles_permission_codes(self.session, [role.code for role in roles])
        return [(role, codes.get(role.code, [])) for role in roles], total
