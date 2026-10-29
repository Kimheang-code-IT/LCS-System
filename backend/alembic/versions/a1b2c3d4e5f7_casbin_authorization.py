"""Casbin authorization: policy table, permission module, multi-role assignments

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-27

Replaces the two editable authorization mappings (``role_permissions`` and
``user_role_assignments``) with the Casbin policy table ``casbin_rule``, which
becomes the single authorization store:

* ``p, role:SALES, quotation, read`` — a grant (the permission code split at its
  last dot into object and action);
* ``g, user:15, role:SALES`` — a role assignment;
* ``g, role:MANAGER, role:VIEWER`` — role inheritance;
* ``p, role:SUPER_ADMIN, *, *`` — the protected super administrator.

Existing grants and assignments are copied across before the old tables are
dropped, so this migration does not silently revoke access. ``PLATFORM_ADMIN``
is renamed to ``SUPER_ADMIN``; the ``roles`` and ``permissions`` rows stay as
display metadata for the administration UI.

The development database may be reset instead — nothing here depends on that.
Production is never reset by this migration: it only moves rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f7"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUPER_ADMIN = "SUPER_ADMIN"
LEGACY_SUPER_ADMIN = "PLATFORM_ADMIN"


def _split(code: str) -> tuple[str, str]:
    obj, separator, act = str(code).rpartition(".")
    return (obj, act) if separator else (str(code), "")


def _insert(bind, seen: set, ptype: str, v0: str, v1: str = "", v2: str = "") -> None:
    key = (ptype, v0, v1, v2)
    if key in seen:
        return
    seen.add(key)
    bind.execute(
        sa.text("INSERT INTO casbin_rule (ptype, v0, v1, v2) VALUES (:ptype, :v0, :v1, :v2)"),
        {"ptype": ptype, "v0": v0, "v1": v1, "v2": v2},
    )


def upgrade() -> None:
    op.create_table(
        "casbin_rule",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ptype", sa.String(length=100), nullable=False),
        sa.Column("v0", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("v1", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("v2", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("v3", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("v4", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("v5", sa.String(length=255), nullable=False, server_default=""),
        sa.UniqueConstraint("ptype", "v0", "v1", "v2", "v3", "v4", "v5", name="uq_casbin_rule"),
    )
    op.create_index("ix_casbin_rule_ptype", "casbin_rule", ["ptype"], unique=False)
    op.add_column(
        "permissions",
        sa.Column("module", sa.String(length=64), nullable=False, server_default="general"),
    )

    bind = op.get_bind()
    for permission_id, code in bind.execute(sa.text("SELECT id, code FROM permissions")).all():
        bind.execute(
            sa.text("UPDATE permissions SET module = :module WHERE id = :id"),
            {"module": str(code).split(".", 1)[0], "id": permission_id},
        )

    bind.execute(
        sa.text("UPDATE roles SET code = :new WHERE code = :old"),
        {"new": SUPER_ADMIN, "old": LEGACY_SUPER_ADMIN},
    )

    seen: set = set()
    grants = bind.execute(
        sa.text(
            "SELECT r.code, p.code FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "JOIN permissions p ON p.id = rp.permission_id"
        )
    ).all()
    for role_code, permission_code in grants:
        obj, act = _split(permission_code)
        _insert(bind, seen, "p", f"role:{role_code}", obj, act)

    assignments = bind.execute(
        sa.text(
            "SELECT ura.user_id, r.code FROM user_role_assignments ura "
            "JOIN roles r ON r.id = ura.role_id "
            "WHERE ura.expires_at IS NULL"
        )
    ).all()
    for user_id, role_code in assignments:
        _insert(bind, seen, "g", f"user:{int(user_id)}", f"role:{role_code}")

    # The protected super administrator always holds the wildcard grant.
    _insert(bind, seen, "p", f"role:{SUPER_ADMIN}", "*", "*")

    op.drop_table("role_permissions")
    op.drop_table("user_role_assignments")


def downgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("assigned_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_user_role_assignments_user_id", "user_role_assignments", ["user_id"], unique=False
    )
    op.create_index(
        "uq_user_role_assignments_active_user",
        "user_role_assignments",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("expires_at IS NULL"),
    )

    role_ids = {
        code: role_id
        for role_id, code in bind.execute(sa.text("SELECT id, code FROM roles")).all()
    }
    permission_ids = {
        code: permission_id
        for permission_id, code in bind.execute(sa.text("SELECT id, code FROM permissions")).all()
    }
    for ptype, v0, v1, v2 in bind.execute(
        sa.text("SELECT ptype, v0, v1, v2 FROM casbin_rule")
    ).all():
        if ptype == "p" and v0.startswith("role:") and v1 != "*":
            role_id = role_ids.get(v0[5:])
            permission_id = permission_ids.get(f"{v1}.{v2}")
            if role_id is not None and permission_id is not None:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id) ON CONFLICT DO NOTHING"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )
        elif ptype == "g" and v0.startswith("user:") and v1.startswith("role:"):
            role_id = role_ids.get(v1[5:])
            if role_id is not None:
                bind.execute(
                    sa.text(
                        "INSERT INTO user_role_assignments (user_id, role_id) VALUES (:user_id, :role_id)"
                    ),
                    {"user_id": int(v0[5:]), "role_id": role_id},
                )

    bind.execute(
        sa.text("UPDATE roles SET code = :old WHERE code = :new"),
        {"new": SUPER_ADMIN, "old": LEGACY_SUPER_ADMIN},
    )

    op.drop_index("ix_casbin_rule_ptype", table_name="casbin_rule")
    op.drop_table("casbin_rule")
    op.drop_column("permissions", "module")
