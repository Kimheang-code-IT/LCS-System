from __future__ import annotations


class RequestContext:
    """Resolved identity attached to every authenticated request.

    Authorization decisions are **not** cached in this object: ``has_permission``
    asks Casbin, so a policy change takes effect without rebuilding the context.
    ``permissions`` is the effective permission snapshot the SPA receives; it is
    display data, never the authority.
    """

    def __init__(
        self,
        *,
        user_id: int,
        username: str,
        email: str,
        display_name: str,
        permissions: set[str],
        is_platform_admin: bool,
        request_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        avatar: str | None = None,
        roles: list[str] | None = None,
    ) -> None:
        self.user_id = user_id
        self.username = username
        self.email = email
        self.display_name = display_name
        self.permissions = permissions
        self.is_platform_admin = is_platform_admin
        self.request_id = request_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.avatar = avatar
        #: Role codes the account holds, resolved with the identity snapshot.
        self.roles = list(roles or [])

    def has_permission(self, code: str) -> bool:
        from app.core.authorization import can

        return can(self.user_id, code)

    def has_any_permission(self, *codes: str) -> bool:
        from app.core.authorization import can_any

        return can_any(self.user_id, codes)

    def require(self, code: str) -> RequestContext:
        from app.core.exceptions import AccessDenied

        if not self.has_permission(code):
            raise AccessDenied(f"Missing permission: {code}")
        return self
