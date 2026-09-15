from __future__ import annotations

from typing import Any

from fastapi import Request


def apply_scope(stmt: Any, model: Any, ctx: RequestContext) -> Any:
    """Apply organization and branch isolation to a select statement."""
    stmt = stmt.where(model.organization_id == ctx.organization_id)
    if not ctx.can_select_all_branches and ctx.branch_id is not None:
        stmt = stmt.where(model.branch_id == ctx.branch_id)
    return stmt


class RequestContext:
    """Resolved authorization context attached to every authenticated request."""

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        email: str,
        display_name: str,
        organization_id: int,
        organization_code: str,
        organization_name: str,
        branch_id: int | None,
        branch_name: str | None,
        assigned_branch_ids: list[int],
        permissions: set[str],
        permission_scope: str,
        is_platform_admin: bool,
        request_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        avatar: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.email = email
        self.display_name = display_name
        self.organization_id = organization_id
        self.organization_code = organization_code
        self.organization_name = organization_name
        self.branch_id = branch_id
        self.branch_name = branch_name
        self.assigned_branch_ids = assigned_branch_ids
        self.permissions = permissions
        self.permission_scope = permission_scope
        self.is_platform_admin = is_platform_admin
        self.request_id = request_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.avatar = avatar

    @property
    def can_select_all_branches(self) -> bool:
        return self.permission_scope == "ORGANIZATION" or self.is_platform_admin

    def has_permission(self, code: str) -> bool:
        if self.is_platform_admin:
            return True
        return code in self.permissions

    def require(self, code: str) -> RequestContext:
        from app.core.exceptions import AccessDenied

        if not self.has_permission(code):
            raise AccessDenied(f"Missing permission: {code}")
        return self

    def assert_branch(self, branch_id: int | None) -> None:
        from app.core.exceptions import AccessDenied

        if branch_id is None or self.can_select_all_branches:
            return
        if branch_id not in self.assigned_branch_ids and branch_id != self.branch_id:
            raise AccessDenied("Branch is outside your assigned scope.")

    @staticmethod
    def from_request(request: Request) -> RequestContext:
        return request.state.context
