from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, PKMixin


class CasbinRule(PKMixin, Base):
    """One Casbin policy line.

    ``ptype`` is ``p`` (a permission grant) or ``g`` (a user→role assignment;
    role inheritance is not supported). This table is the **only** editable
    authorization store: the ``roles`` and ``permissions`` tables keep display
    metadata for the administration UI and never decide access.
    """

    __tablename__ = "casbin_rule"
    __table_args__ = (
        UniqueConstraint("ptype", "v0", "v1", "v2", "v3", "v4", "v5", name="uq_casbin_rule"),
        # One user holds exactly one role: at most one assignment edge per
        # user subject. Role subjects (``role:...``) are exempt — those are
        # legacy inheritance edges, which are no longer written or loaded.
        Index(
            "uq_casbin_rule_single_user_role",
            "v0",
            unique=True,
            sqlite_where=text("ptype = 'g' AND v0 LIKE 'user:%'"),
            postgresql_where=text("ptype = 'g' AND v0 LIKE 'user:%'"),
        ),
    )

    ptype: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    v0: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    v1: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    v2: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    v3: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    v4: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    v5: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
