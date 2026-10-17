"""Reporting views and database-level integrity guards.

Two separate concerns, both PostgreSQL-only and both additive:

1. **Reporting views** — the proposal's starter views, redefined against this
   schema's actual columns, plus two compatibility views that expose the
   proposal's ``payments`` / ``payment_allocations`` naming over the existing
   ``financial_documents`` / ``financial_document_allocations`` structures. No
   data is duplicated.

2. **Integrity guards** — invariants the application already enforces in Python,
   restated as triggers so a privileged or out-of-band write cannot bypass them:
   posted journals and their lines are immutable, a posted journal must be
   balanced and inside an open period, audit events are append-only, and a
   payment allocation may not exceed the remaining balance of either side.

   Deliberate departures from the reference DDL are documented in
   ``docs/14_47_table_migration_analysis.md`` §5 — most importantly allocations
   stay deletable, because reversing a document legitimately unwinds them.

An administrative data reset would otherwise be blocked by the immutability
guards, so they honour a transaction-scoped escape hatch
(``SET LOCAL lcs.allow_financial_purge = 'on'``) that only the audited reset
path sets. ``docs/15_migration_and_rollback_guide.md`` documents it.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEWS: tuple[str, ...] = (
    "vw_trial_balance",
    "vw_general_ledger",
    "vw_quotation_version_history",
    "vw_invoice_outstanding",
    "vw_service_order_charge_summary",
    "vw_service_order_status",
    "vw_payments",
    "vw_payment_allocations",
)

TRIGGERS: tuple[tuple[str, str], ...] = (
    ("journal_entries", "trg_journal_guard"),
    ("journal_entries", "trg_journal_post_check"),
    ("journal_entry_lines", "trg_journal_line_guard"),
    ("audit_events", "trg_audit_append_only"),
    ("financial_document_allocations", "trg_allocation_guard"),
)

VIEW_SQL: tuple[str, ...] = (
    # Account-level totals over POSTED journals only; REVERSED documents are
    # represented by their own reversal journal, so summing POSTED entries can
    # never double-count.
    """
    CREATE VIEW vw_trial_balance AS
    SELECT l.account_id,
           a.account_code,
           a.account_name,
           a.account_type,
           SUM(l.debit_amount)  AS total_debit,
           SUM(l.credit_amount) AS total_credit,
           SUM(l.debit_amount - l.credit_amount) AS net_debit_balance
    FROM journal_entry_lines l
    JOIN journal_entries j ON j.id = l.journal_entry_id
    JOIN chart_of_accounts a ON a.id = l.account_id
    WHERE j.status = 'POSTED'
    GROUP BY l.account_id, a.account_code, a.account_name, a.account_type
    """,
    """
    CREATE VIEW vw_general_ledger AS
    SELECT j.id AS journal_entry_id,
           j.entry_no,
           j.entry_type,
           j.entry_date,
           j.posting_date,
           l.id AS journal_line_id,
           l.line_no,
           l.account_id,
           a.account_code,
           a.account_name,
           a.account_type,
           l.party_id,
           l.service_order_id,
           l.financial_document_id,
           l.description,
           l.debit_amount,
           l.credit_amount,
           l.currency_code,
           l.base_debit_amount,
           l.base_credit_amount
    FROM journal_entries j
    JOIN journal_entry_lines l ON l.journal_entry_id = j.id
    JOIN chart_of_accounts a ON a.id = l.account_id
    WHERE j.status = 'POSTED'
    """,
    """
    CREATE VIEW vw_quotation_version_history AS
    SELECT q.id AS quotation_id,
           q.quotation_no,
           v.id AS quotation_version_id,
           v.revision_no AS version_no,
           v.status,
           v.quotation_date,
           v.valid_until,
           v.currency_code,
           v.total_amount,
           v.created_by_user_id,
           v.sent_at,
           v.accepted_at,
           v.created_at
    FROM quotations q
    JOIN quotation_revisions v ON v.quotation_id = q.id
    """,
    # Same-currency only, like the allocation guard: an allocation is recorded in
    # one currency, so comparing it to a document total of another currency would
    # be meaningless. Cross-currency settlement needs its own reviewed design.
    """
    CREATE VIEW vw_invoice_outstanding AS
    SELECT d.id AS financial_document_id,
           d.document_no,
           d.document_type,
           d.party_id,
           d.currency_code,
           d.document_date,
           d.due_date,
           d.status,
           d.total_amount,
           COALESCE(a.allocated, 0) AS paid_amount,
           d.total_amount - COALESCE(a.allocated, 0) AS outstanding_amount
    FROM financial_documents d
    LEFT JOIN (
        SELECT alloc.target_document_id AS document_id,
               SUM(alloc.allocated_amount) AS allocated
        FROM financial_document_allocations alloc
        JOIN financial_documents src ON src.id = alloc.payment_document_id
        WHERE src.status NOT IN ('DRAFT', 'REVERSED', 'CANCELLED')
        GROUP BY alloc.target_document_id
    ) a ON a.document_id = d.id
    WHERE d.document_type IN ('CUSTOMER_INVOICE', 'SUPPLIER_BILL')
      AND d.status NOT IN ('DRAFT', 'REVERSED', 'CANCELLED')
    """,
    # Mirrors ReportRepository.service_order_finance_rows(): issued charges are
    # the operational view, POSTED documents are the financial view.
    """
    CREATE VIEW vw_service_order_charge_summary AS
    SELECT so.id AS service_order_id,
           so.service_order_no,
           so.currency_code,
           COALESCE(c.issued_charges, 0) AS issued_charge_amount,
           COALESCE(c.draft_charges, 0)  AS draft_charge_amount,
           COALESCE(c.charge_count, 0)   AS charge_count,
           COALESCE(f.posted_revenue, 0) AS posted_revenue,
           COALESCE(f.posted_cost, 0)    AS posted_cost,
           COALESCE(f.posted_revenue, 0) - COALESCE(f.posted_cost, 0) AS posted_margin
    FROM service_orders so
    LEFT JOIN (
        SELECT service_order_id,
               SUM(CASE WHEN status = 'ISSUED' THEN total_amount ELSE 0 END) AS issued_charges,
               SUM(CASE WHEN status = 'DRAFT'  THEN total_amount ELSE 0 END) AS draft_charges,
               COUNT(id) AS charge_count
        FROM service_order_charges
        GROUP BY service_order_id
    ) c ON c.service_order_id = so.id
    LEFT JOIN (
        SELECT service_order_id,
               SUM(CASE WHEN document_type = 'CUSTOMER_INVOICE' AND status = 'POSTED' THEN total_amount ELSE 0 END) AS posted_revenue,
               SUM(CASE WHEN document_type = 'SUPPLIER_BILL'    AND status = 'POSTED' THEN total_amount ELSE 0 END) AS posted_cost
        FROM financial_documents
        WHERE service_order_id IS NOT NULL
        GROUP BY service_order_id
    ) f ON f.service_order_id = so.id
    """,
    """
    CREATE VIEW vw_service_order_status AS
    SELECT so.id,
           so.service_order_no,
           so.customer_party_id,
           so.trade_direction_id,
           so.status,
           so.currency_code,
           so.created_at,
           (SELECT COUNT(*) FROM service_order_containers sc WHERE sc.service_order_id = so.id) AS container_count,
           (SELECT COUNT(*) FROM service_order_movements  mv WHERE mv.service_order_id = so.id) AS movement_count,
           (SELECT COUNT(*) FROM service_order_milestones ms WHERE ms.service_order_id = so.id) AS milestone_count
    FROM service_orders so
    """,
    # Compatibility naming for the proposal's `payments` table.
    """
    CREATE VIEW vw_payments AS
    SELECT d.id,
           d.document_no AS payment_no,
           d.party_id,
           d.financial_account_id,
           d.currency_code,
           CASE WHEN d.document_type = 'CUSTOMER_RECEIPT' THEN 'IN' ELSE 'OUT' END AS payment_direction,
           d.document_date AS payment_date,
           d.total_amount AS amount,
           d.status,
           d.reference_number,
           d.created_by_user_id,
           d.created_at,
           d.updated_at
    FROM financial_documents d
    WHERE d.document_type IN ('CUSTOMER_RECEIPT', 'SUPPLIER_PAYMENT')
    """,
    """
    CREATE VIEW vw_payment_allocations AS
    SELECT a.id,
           a.payment_document_id AS payment_id,
           a.target_document_id  AS financial_document_id,
           a.allocated_amount,
           a.allocated_currency_code,
           a.exchange_rate,
           a.allocated_at,
           a.created_by_user_id
    FROM financial_document_allocations a
    """,
)

FUNCTION_SQL: tuple[str, ...] = (
    # Administrative reset escape hatch. SECURITY is unchanged: any session can
    # set it, but only the audited reset endpoint does, and it is transaction
    # scoped (SET LOCAL) so it cannot leak to the next request.
    """
    CREATE OR REPLACE FUNCTION fn_financial_purge_allowed() RETURNS BOOLEAN
    LANGUAGE sql STABLE AS $$
        SELECT COALESCE(current_setting('lcs.allow_financial_purge', true), '') = 'on'
    $$;
    """,
    """
    CREATE OR REPLACE FUNCTION fn_guard_journal_entry() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        IF fn_financial_purge_allowed() THEN
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END IF;
        IF TG_OP = 'DELETE' AND OLD.status = 'POSTED' THEN
            RAISE EXCEPTION 'Posted journal % cannot be deleted; reverse it instead', OLD.entry_no;
        END IF;
        IF TG_OP = 'UPDATE' AND OLD.status = 'POSTED' AND NEW IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'Posted journal % is immutable; reverse it instead', OLD.entry_no;
        END IF;
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    """,
    """
    CREATE OR REPLACE FUNCTION fn_guard_journal_line() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    DECLARE target_id BIGINT; target_status VARCHAR(20);
    BEGIN
        IF fn_financial_purge_allowed() THEN
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END IF;
        target_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
        SELECT status INTO target_status FROM journal_entries WHERE id = target_id;
        IF target_status IS NULL THEN
            -- The parent row is being removed in the same statement.
            RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END IF;
        IF target_status = 'POSTED' THEN
            RAISE EXCEPTION 'Lines of posted journal % cannot change; reverse it instead', target_id;
        END IF;
        IF TG_OP = 'UPDATE' AND NEW.journal_entry_id <> OLD.journal_entry_id THEN
            RAISE EXCEPTION 'Journal lines cannot be moved between journals';
        END IF;
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END $$;
    """,
    # Deferred so it fires at COMMIT, after the lines of a freshly inserted
    # POSTED journal exist. post_document() inserts the entry as POSTED and adds
    # the lines afterwards in the same transaction, so an immediate trigger would
    # reject a legitimate posting.
    """
    CREATE OR REPLACE FUNCTION fn_validate_journal_post() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    DECLARE deb NUMERIC(19,4); cred NUMERIC(19,4); line_count INTEGER;
            p_start DATE; p_end DATE; p_status VARCHAR(20);
    BEGIN
        IF fn_financial_purge_allowed() THEN
            RETURN NEW;
        END IF;
        IF COALESCE(NEW.status, '') <> 'POSTED' THEN
            RETURN NEW;
        END IF;
        IF TG_OP = 'UPDATE' AND OLD.status = 'POSTED' THEN
            RETURN NEW;  -- unchanged posting; the immutability guard owns this
        END IF;
        SELECT start_date, end_date, status INTO p_start, p_end, p_status
        FROM accounting_periods WHERE id = NEW.accounting_period_id;
        IF p_status IS DISTINCT FROM 'OPEN' OR NEW.entry_date < p_start OR NEW.entry_date > p_end THEN
            RAISE EXCEPTION 'Journal % must post inside an open accounting period', NEW.entry_no;
        END IF;
        SELECT COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0), COUNT(*)
        INTO deb, cred, line_count
        FROM journal_entry_lines WHERE journal_entry_id = NEW.id;
        IF line_count < 2 OR deb <= 0 OR deb <> cred THEN
            RAISE EXCEPTION 'Journal % must contain at least two balanced lines (debit %, credit %)',
                NEW.entry_no, deb, cred;
        END IF;
        RETURN NEW;
    END $$;
    """,
    """
    CREATE OR REPLACE FUNCTION fn_audit_append_only() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        RAISE EXCEPTION 'Audit events are append-only';
    END $$;
    """,
    # One-directional over-allocation guard. DELETE is intentionally allowed:
    # reverse_document() unwinds allocations as part of an approved reversal.
    """
    CREATE OR REPLACE FUNCTION fn_guard_allocation() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    DECLARE payment_total NUMERIC(19,4); invoice_total NUMERIC(19,4);
            payment_used NUMERIC(19,4); invoice_used NUMERIC(19,4);
    BEGIN
        IF fn_financial_purge_allowed() THEN
            RETURN NEW;
        END IF;
        SELECT total_amount INTO payment_total
        FROM financial_documents WHERE id = NEW.payment_document_id FOR UPDATE;
        SELECT total_amount INTO invoice_total
        FROM financial_documents WHERE id = NEW.target_document_id FOR UPDATE;
        IF payment_total IS NULL OR invoice_total IS NULL THEN
            RAISE EXCEPTION 'Allocation must reference existing financial documents';
        END IF;
        SELECT COALESCE(SUM(allocated_amount), 0) INTO payment_used
        FROM financial_document_allocations
        WHERE payment_document_id = NEW.payment_document_id AND id <> NEW.id;
        SELECT COALESCE(SUM(allocated_amount), 0) INTO invoice_used
        FROM financial_document_allocations
        WHERE target_document_id = NEW.target_document_id AND id <> NEW.id;
        IF payment_used + NEW.allocated_amount > payment_total THEN
            RAISE EXCEPTION 'Allocation exceeds the remaining balance of payment document %',
                NEW.payment_document_id;
        END IF;
        IF invoice_used + NEW.allocated_amount > invoice_total THEN
            RAISE EXCEPTION 'Allocation exceeds the remaining balance of document %',
                NEW.target_document_id;
        END IF;
        RETURN NEW;
    END $$;
    """,
    """
    CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END $$;
    """,
)

CREATE_TRIGGER_SQL: tuple[str, ...] = (
    """
    CREATE TRIGGER trg_journal_guard
    BEFORE UPDATE OR DELETE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION fn_guard_journal_entry();
    """,
    """
    CREATE CONSTRAINT TRIGGER trg_journal_post_check
    AFTER INSERT OR UPDATE OF status ON journal_entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION fn_validate_journal_post();
    """,
    """
    CREATE TRIGGER trg_journal_line_guard
    BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_lines
    FOR EACH ROW EXECUTE FUNCTION fn_guard_journal_line();
    """,
    """
    CREATE TRIGGER trg_audit_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION fn_audit_append_only();
    """,
    """
    CREATE TRIGGER trg_allocation_guard
    BEFORE INSERT OR UPDATE ON financial_document_allocations
    FOR EACH ROW EXECUTE FUNCTION fn_guard_allocation();
    """,
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # Triggers and views are PostgreSQL features; the schema itself is
        # created from the models on other dialects.
        return

    for statement in FUNCTION_SQL:
        op.execute(statement)
    for statement in CREATE_TRIGGER_SQL:
        op.execute(statement)

    # Keep updated_at honest for writes that bypass the ORM.
    op.execute(
        """
        DO $$
        DECLARE target RECORD;
        BEGIN
            FOR target IN
                SELECT c.table_name
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                WHERE c.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                  AND c.column_name = 'updated_at'
            LOOP
                EXECUTE format(
                    'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',
                    'trg_touch_' || target.table_name, target.table_name
                );
            END LOOP;
        END $$;
        """
    )

    for statement in VIEW_SQL:
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for view in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    op.execute(
        """
        DO $$
        DECLARE target RECORD;
        BEGIN
            FOR target IN
                SELECT tgname, relname
                FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND tgname LIKE 'trg_touch_%'
            LOOP
                EXECUTE format('DROP TRIGGER %I ON %I', target.tgname, target.relname);
            END LOOP;
        END $$;
        """
    )

    for table, trigger in TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")

    for function in (
        "fn_guard_journal_entry",
        "fn_guard_journal_line",
        "fn_validate_journal_post",
        "fn_audit_append_only",
        "fn_guard_allocation",
        "fn_touch_updated_at",
        "fn_financial_purge_allowed",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
