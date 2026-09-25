"""remove organization and branch (single-tenant)

Revision ID: b7f1c2a9d4e0
Revises: 6e862ce04e46
Create Date: 2026-09-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "b7f1c2a9d4e0"
down_revision: str | None = "6e862ce04e46"
branch_labels: str | None = None
depends_on: str | None = None


# (table, old unique constraint names to drop)
DROP_UNIQUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("accounting_periods", ("uq_periods_org_year_month",)),
    ("chart_of_accounts", ("uq_coa_org_code",)),
    ("document_sequences", ("uq_sequences_org_type_year",)),
    ("quotations", ("uq_quotations_org_no",)),
    ("service_orders", ("uq_service_orders_org_no",)),
    ("financial_accounts", ("uq_financial_accounts_org_account",)),
    ("financial_documents", ("uq_financial_documents_org_no",)),
    ("service_order_charges", ("uq_service_order_charges_org_no",)),
    ("journal_entries", ("uq_journal_entries_org_no",)),
    ("service_order_tab_configs", ("uq_so_tab_configs_org_code",)),
)

# (table, columns to drop)
DROP_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("accounting_periods", ("organization_id",)),
    ("attachments", ("organization_id", "branch_id")),
    ("audit_events", ("organization_id", "branch_id")),
    ("chart_of_accounts", ("organization_id",)),
    ("document_sequences", ("organization_id",)),
    ("module_records", ("organization_id", "branch_id")),
    ("quotations", ("organization_id", "branch_id")),
    ("service_orders", ("organization_id", "branch_id")),
    ("financial_accounts", ("organization_id",)),
    ("posting_rules", ("organization_id",)),
    ("financial_documents", ("organization_id", "branch_id")),
    ("service_order_charges", ("organization_id", "branch_id")),
    ("journal_entries", ("organization_id", "branch_id")),
    ("journal_entry_lines", ("branch_id",)),
    ("user_role_assignments", ("organization_id", "branch_id")),
    ("service_order_tab_configs", ("organization_id",)),
)

# (table, new unique constraint name, columns)
ADD_UNIQUES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("accounting_periods", "uq_periods_year_month", ("period_year", "period_month")),
    ("chart_of_accounts", "uq_coa_code", ("account_code",)),
    ("document_sequences", "uq_sequences_type_year", ("document_type", "period_year")),
    ("quotations", "uq_quotations_no", ("quotation_no",)),
    ("service_orders", "uq_service_orders_no", ("service_order_no",)),
    ("financial_accounts", "uq_financial_accounts_account", ("account_id",)),
    ("financial_documents", "uq_financial_documents_no", ("document_no",)),
    ("service_order_charges", "uq_service_order_charges_no", ("charge_no",)),
    ("journal_entries", "uq_journal_entries_no", ("entry_no",)),
    ("service_order_tab_configs", "uq_so_tab_configs_code", ("code",)),
)


def upgrade() -> None:
    for table, constraints in DROP_UNIQUES:
        for name in constraints:
            op.drop_constraint(name, table, type_="unique")

    for table, columns in DROP_COLUMNS:
        for column in columns:
            op.drop_column(table, column)

    op.drop_table("user_branch_assignments")
    op.drop_table("branches")
    op.drop_table("organizations")

    for table, name, columns in ADD_UNIQUES:
        op.create_unique_constraint(name, table, list(columns))


def downgrade() -> None:
    for table, name, _columns in ADD_UNIQUES:
        op.drop_constraint(name, table, type_="unique")

    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("organization_code", sa.String(length=50), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("vat_tin", sa.String(length=64), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("default_currency_code", sa.String(length=3), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("organization_code", name=op.f("uq_organizations_organization_code")),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("place_id", sa.BigInteger(), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_head_office", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_branches_organization_id_organizations")),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], name=op.f("fk_branches_place_id_places")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branches")),
        sa.UniqueConstraint("organization_id", "branch_code", name="uq_branches_org_code"),
    )
    op.create_table(
        "user_branch_assignments",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name=op.f("fk_user_branch_assignments_organization_id_organizations")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_branch_assignments_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "organization_id", "branch_id", name=op.f("pk_user_branch_assignments")),
    )

    for table, columns in DROP_COLUMNS:
        for column in columns:
            op.add_column(table, sa.Column(column, sa.BigInteger(), nullable=True))

    for table, constraints in DROP_UNIQUES:
        for name in constraints:
            # Best-effort restore of the original per-organization constraints.
            if name == "uq_periods_org_year_month":
                op.create_unique_constraint(name, table, ["organization_id", "period_year", "period_month"])
            elif name == "uq_coa_org_code":
                op.create_unique_constraint(name, table, ["organization_id", "account_code"])
            elif name == "uq_sequences_org_type_year":
                op.create_unique_constraint(name, table, ["organization_id", "document_type", "period_year"])
            elif name == "uq_quotations_org_no":
                op.create_unique_constraint(name, table, ["organization_id", "quotation_no"])
            elif name == "uq_service_orders_org_no":
                op.create_unique_constraint(name, table, ["organization_id", "service_order_no"])
            elif name == "uq_financial_accounts_org_account":
                op.create_unique_constraint(name, table, ["organization_id", "account_id"])
            elif name == "uq_financial_documents_org_no":
                op.create_unique_constraint(name, table, ["organization_id", "document_no"])
            elif name == "uq_service_order_charges_org_no":
                op.create_unique_constraint(name, table, ["organization_id", "charge_no"])
            elif name == "uq_journal_entries_org_no":
                op.create_unique_constraint(name, table, ["organization_id", "entry_no"])
            elif name == "uq_so_tab_configs_org_code":
                op.create_unique_constraint(name, table, ["organization_id", "code"])
