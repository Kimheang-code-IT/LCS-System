from __future__ import annotations


class RequestContext:
    """Resolved authorization context attached to every authenticated request."""

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

    def has_permission(self, code: str) -> bool:
        if self.is_platform_admin:
            return True
        return code in self.permissions

    def require(self, code: str) -> RequestContext:
        from app.core.exceptions import AccessDenied

        if not self.has_permission(code):
            raise AccessDenied(f"Missing permission: {code}")
        return self
