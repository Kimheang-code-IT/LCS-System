"""Dynamic business-party roles and their many-to-many assignments.

``business_parties.roles`` used to be a JSON list of labels (Customer, Supplier,
Company) with no shared vocabulary. This revision makes the vocabulary a managed
record and the assignment a real relation:

* ``party_roles`` — code, name, description and status. Existing labels are
  inserted as data so a party keeps every role it had.
* ``business_party_roles`` — unique (party, role) pairs. The role FK is
  ``RESTRICT`` so a role that is still assigned cannot be hard-deleted.

Nothing is dropped on upgrade; the JSON column stays as a compatibility snapshot
and a downgrade rebuilds it from the relation before removing the new tables.

Revision ID: a9b8c7d6e5f4
Revises: f2c3d4e5f6a7
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "f2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pk() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "party_roles",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["deleted_by_user_id"],
            ["users.id"],
            name=op.f("fk_party_roles_deleted_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_party_roles")),
    )
    op.create_index(
        "uq_party_roles_code_active",
        "party_roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_party_roles_name_active",
        "party_roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(op.f("ix_party_roles_deleted_at"), "party_roles", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_party_roles_deleted_by_user_id"), "party_roles", ["deleted_by_user_id"], unique=False
    )

    op.create_table(
        "business_party_roles",
        sa.Column("business_party_id", sa.BigInteger(), nullable=False),
        sa.Column("party_role_id", sa.BigInteger(), nullable=False),
        sa.Column("id", _pk(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["business_party_id"],
            ["business_parties.id"],
            name=op.f("fk_business_party_roles_business_party_id_business_parties"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["party_role_id"],
            ["party_roles.id"],
            name=op.f("fk_business_party_roles_party_role_id_party_roles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_party_roles")),
        sa.UniqueConstraint("business_party_id", "party_role_id", name="uq_business_party_roles"),
    )
    op.create_index(
        op.f("ix_business_party_roles_business_party_id"),
        "business_party_roles",
        ["business_party_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_business_party_roles_party_role_id"), "business_party_roles", ["party_role_id"], unique=False
    )

    # Preserve every label already stored on a party. The generated code is the
    # upper-cased label with punctuation collapsed; ON CONFLICT skips a label
    # whose code or name is taken, which keeps the migration non-destructive.
    op.execute(
        """
        INSERT INTO party_roles (code, name, description, status, created_at, updated_at)
        SELECT DISTINCT ON (lower(trim(lbl)))
               upper(regexp_replace(trim(lbl), '[^A-Za-z0-9]+', '_', 'g')),
               trim(lbl), NULL, 'ACTIVE', now(), now()
        FROM business_parties AS bp
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(bp.roles) = 'array' THEN bp.roles ELSE '[]'::jsonb END
        ) AS lbl
        WHERE trim(lbl) <> ''
        ORDER BY lower(trim(lbl)), trim(lbl)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO business_party_roles (business_party_id, party_role_id)
        SELECT bp.id, pr.id
        FROM business_parties AS bp
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(bp.roles) = 'array' THEN bp.roles ELSE '[]'::jsonb END
        ) AS lbl
        JOIN party_roles AS pr
          ON pr.deleted_at IS NULL
         AND lower(pr.name) = lower(trim(lbl))
        ON CONFLICT ON CONSTRAINT uq_business_party_roles DO NOTHING
        """
    )


def downgrade() -> None:
    # Rebuild the legacy label snapshot from the relation so a rollback does not
    # lose assignments made after the upgrade. Parties without rows keep theirs.
    op.execute(
        """
        UPDATE business_parties AS bp
        SET roles = sub.roles
        FROM (
            SELECT bpr.business_party_id AS party_id,
                   jsonb_agg(pr.name ORDER BY pr.name) AS roles
            FROM business_party_roles AS bpr
            JOIN party_roles AS pr ON pr.id = bpr.party_role_id
            GROUP BY bpr.business_party_id
        ) AS sub
        WHERE bp.id = sub.party_id
        """
    )

    op.drop_index(op.f("ix_business_party_roles_party_role_id"), table_name="business_party_roles")
    op.drop_index(op.f("ix_business_party_roles_business_party_id"), table_name="business_party_roles")
    op.drop_table("business_party_roles")

    op.drop_index(op.f("ix_party_roles_deleted_by_user_id"), table_name="party_roles")
    op.drop_index(op.f("ix_party_roles_deleted_at"), table_name="party_roles")
    op.drop_index("uq_party_roles_name_active", table_name="party_roles")
    op.drop_index("uq_party_roles_code_active", table_name="party_roles")
    op.drop_table("party_roles")
