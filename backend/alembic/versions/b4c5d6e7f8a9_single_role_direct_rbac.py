"""Direct RBAC: one role per user, no role inheritance.

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f7
Create Date: 2026-10-28

* Every role-inheritance edge (``g, role:CHILD, role:PARENT``) is materialized:
  each parent's grants are copied onto the child role as its own ``p`` rows, so
  no user loses effective access when the edges are removed.
* Users holding more than one role abort the migration: the conflicting
  assignments are reported and must be resolved explicitly — the revision never
  silently picks which role to keep.
* A partial unique index enforces one active assignment per user subject at the
  database level.

Downgrade drops the index only. The materialized grants stay, so access is
unchanged on rollback; the inheritance edges themselves are not restored
(their effect now lives as the child role's direct grants).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: str | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Report multi-role users and abort: choosing a role for an existing user
    # is a business decision, not a migration default.
    multi = bind.execute(
        sa.text(
            "SELECT v0 FROM casbin_rule "
            "WHERE ptype = 'g' AND v0 LIKE 'user:%' "
            "GROUP BY v0 HAVING count(*) > 1 ORDER BY v0"
        )
    ).scalars().all()
    if multi:
        subjects = []
        for subject in multi:
            assignments = bind.execute(
                sa.text("SELECT v1 FROM casbin_rule WHERE ptype = 'g' AND v0 = :subject ORDER BY v1"),
                {"subject": subject},
            ).scalars().all()
            subjects.append(f"{subject}: {', '.join(assignments)}")
        raise RuntimeError(
            "Users with more than one assigned role were found. Resolve them "
            "before upgrading (keep one `g, user:<id>, role:<code>` row each):\n"
            + "\n".join(subjects)
        )

    # 2. Materialize inherited grants: copy every ancestor's `p` rows onto the
    # child role as its own grants, walking each inheritance chain once.
    edges = bind.execute(
        sa.text("SELECT v0, v1 FROM casbin_rule WHERE ptype = 'g' AND v0 LIKE 'role:%'")
    ).all()
    parent_of = {child: parent.split(":", 1)[1] for child, parent in edges}

    def ancestors(code: str) -> list[str]:
        chain: list[str] = []
        visited: set[str] = set()
        current = code
        while current in parent_of and current not in visited:
            visited.add(current)
            current = parent_of[current]
            chain.append(current)
        return chain

    grants = bind.execute(
        sa.text("SELECT v0, v1, v2 FROM casbin_rule WHERE ptype = 'p' AND v0 LIKE 'role:%'")
    ).all()
    grants_by_role: dict[str, set[tuple[str, str]]] = {}
    for subject, obj, act in grants:
        grants_by_role.setdefault(subject.split(":", 1)[1], set()).add((obj or "", act or ""))
    for child in parent_of:
        child_grants = grants_by_role.setdefault(child, set())
        for parent in ancestors(child):
            child_grants.update(grants_by_role.get(parent, set()))
        for obj, act in sorted(child_grants):
            if not obj:
                continue
            bind.execute(
                sa.text("INSERT INTO casbin_rule (ptype, v0, v1, v2) SELECT 'p', :s, :o, :a "
                        "WHERE NOT EXISTS (SELECT 1 FROM casbin_rule WHERE ptype = 'p' "
                        "AND v0 = :s AND v1 = :o AND v2 = :a)"),
                {"s": child, "o": obj, "a": act},
            )

    # 3. Remove the inheritance relationships themselves.
    op.execute(sa.text("DELETE FROM casbin_rule WHERE ptype = 'g' AND v0 LIKE 'role:%'"))

    # 4. Enforce one role per user at the database level.
    op.create_index(
        "uq_casbin_rule_single_user_role",
        "casbin_rule",
        ["v0"],
        unique=True,
        postgresql_where=sa.text("ptype = 'g' AND v0 LIKE 'user:%'"),
    )


def downgrade() -> None:
    op.drop_index("uq_casbin_rule_single_user_role", table_name="casbin_rule")
