from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, false, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, PKMixin, TimestampMixin

PROTECTED_SYSTEM_ADMIN_IDENTITY = "DEFAULT_SYSTEM_ADMIN"


class User(PKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    user_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    # Stable machine identity for built-in accounts. Unlike username/email/user
    # code, this value is never accepted from an API payload or changed by user
    # management operations.
    system_identity: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped whenever all of a user's sessions must be invalidated (deactivate,
    # forced logout, password change). Access tokens embed it so revocation is
    # immediate even though the JWT itself is stateless.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    credential: Mapped[UserCredential | None] = relationship(back_populates="user", uselist=False)


class UserCredential(TimestampMixin, Base):
    __tablename__ = "user_credentials"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="argon2id")
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    failed_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="credential")


class UserSession(PKMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Remember me" sessions get persistent cookies and the full configured
    # lifetime; other sessions are browser-session cookies with a short
    # server-enforced deadline. Rotation carries this flag forward.
    remember_me: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())


class Role(PKMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")


class Permission(PKMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserRoleAssignment(PKMixin, TimestampMixin, Base):
    __tablename__ = "user_role_assignments"
    # Single-Role RBAC: a user may hold at most one *active* (non-expiring)
    # assignment. Replacing a role expires the previous row instead of deleting
    # it, so history is preserved while this partial index keeps the active role
    # unique — the database guarantee behind "one user = one role".
    __table_args__ = (
        Index(
            "uq_user_role_assignments_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("expires_at IS NULL"),
            sqlite_where=text("expires_at IS NULL"),
        ),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id"), nullable=False)
    assigned_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(PKMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
