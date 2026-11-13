"""Retain allocation history and guard active balances in their own currencies.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
"""
from pathlib import Path
from runpy import run_path

import sqlalchemy as sa

from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financial_document_allocations", sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("financial_document_allocations", sa.Column("reversed_by_document_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_allocation_reversed_document", "financial_document_allocations", "financial_documents", ["reversed_by_document_id"], ["id"])
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
    CREATE OR REPLACE FUNCTION fn_guard_allocation() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    DECLARE payment_total NUMERIC(19,4); invoice_total NUMERIC(19,4);
            payment_used NUMERIC(19,4); invoice_used NUMERIC(19,4);
    BEGIN
        IF fn_financial_purge_allowed() THEN RETURN NEW; END IF;
        IF TG_OP = 'UPDATE' THEN
            IF ROW(NEW.payment_document_id, NEW.target_document_id, NEW.allocated_amount,
                   NEW.target_amount, NEW.allocated_currency_code, NEW.exchange_rate, NEW.idempotency_key)
               IS DISTINCT FROM
               ROW(OLD.payment_document_id, OLD.target_document_id, OLD.allocated_amount,
                   OLD.target_amount, OLD.allocated_currency_code, OLD.exchange_rate, OLD.idempotency_key)
               OR (OLD.reversed_at IS NOT NULL AND NEW.reversed_at IS DISTINCT FROM OLD.reversed_at) THEN
                RAISE EXCEPTION 'An allocation keeps its original amounts and source links';
            END IF;
        END IF;
        IF NEW.reversed_at IS NOT NULL THEN RETURN NEW; END IF;
        SELECT total_amount INTO payment_total FROM financial_documents WHERE id=NEW.payment_document_id FOR UPDATE;
        SELECT total_amount INTO invoice_total FROM financial_documents WHERE id=NEW.target_document_id FOR UPDATE;
        IF payment_total IS NULL OR invoice_total IS NULL OR NEW.allocated_amount <= 0 OR NEW.target_amount <= 0 THEN
            RAISE EXCEPTION 'Allocation requires existing documents and positive amounts';
        END IF;
        SELECT COALESCE(SUM(allocated_amount),0) INTO payment_used FROM financial_document_allocations
        WHERE payment_document_id=NEW.payment_document_id AND id<>NEW.id AND reversed_at IS NULL;
        SELECT COALESCE(SUM(target_amount),0) INTO invoice_used FROM financial_document_allocations
        WHERE target_document_id=NEW.target_document_id AND id<>NEW.id AND reversed_at IS NULL;
        IF payment_used+NEW.allocated_amount>payment_total OR invoice_used+NEW.target_amount>invoice_total THEN
            RAISE EXCEPTION 'Allocation exceeds the remaining document balance';
        END IF;
        RETURN NEW;
    END $$;
    """)
    old = run_path(str(Path(__file__).with_name("e6f7a8b9c0d1_reporting_views_and_integrity.py")))
    # Keep the historical view columns/contracts, changing only their active-set
    # and invoice-currency arithmetic. The old revision is never edited.
    for sql in old["VIEW_SQL"]:
        if "CREATE VIEW vw_invoice_outstanding AS" in sql:
            op.execute(sql.replace("CREATE VIEW", "CREATE OR REPLACE VIEW")
                .replace("SUM(alloc.allocated_amount)", "SUM(alloc.target_amount)")
                .replace("WHERE src.status", "WHERE alloc.reversed_at IS NULL AND src.status"))
        elif "CREATE VIEW vw_payment_allocations AS" in sql:
            op.execute(sql.replace("CREATE VIEW", "CREATE OR REPLACE VIEW") + " WHERE a.reversed_at IS NULL")


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM financial_document_allocations WHERE reversed_at IS NOT NULL")):
        raise RuntimeError("Cannot remove allocation reversal history. Retain this schema and use a reviewed forward migration.")
    if op.get_bind().dialect.name == "postgresql":
        old = run_path(str(Path(__file__).with_name("e6f7a8b9c0d1_reporting_views_and_integrity.py")))
        for sql in old["VIEW_SQL"]:
            if "CREATE VIEW vw_invoice_outstanding AS" in sql or "CREATE VIEW vw_payment_allocations AS" in sql:
                op.execute(sql.replace("CREATE VIEW", "CREATE OR REPLACE VIEW"))
        for sql in old["FUNCTION_SQL"]:
            if "FUNCTION fn_guard_allocation()" in sql:
                op.execute(sql)
        op.execute("ALTER TABLE financial_document_allocations DROP CONSTRAINT IF EXISTS fk_allocation_reversed_document")
    else:
        op.drop_constraint("fk_allocation_reversed_document", "financial_document_allocations", type_="foreignkey")
    op.drop_column("financial_document_allocations", "reversed_by_document_id")
    op.drop_column("financial_document_allocations", "reversed_at")
