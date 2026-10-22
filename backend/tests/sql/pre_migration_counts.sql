-- Row-count and financial reconciliation for the 47-table migration.
--
-- Run BEFORE and AFTER applying the additive revisions and diff the two outputs:
--   psql "$DATABASE_URL" -f backend/tests/sql/pre_migration_counts.sql > pre.txt
--   ... apply migrations ...
--   psql "$DATABASE_URL" -f backend/tests/sql/pre_migration_counts.sql > post.txt
--   diff pre.txt post.txt
--
-- docs/11_deployment_and_security.md §8 and §12 list the only rows that may differ.
-- Read-only: this script never writes.
\pset pager off
\pset footer off

\echo '--- row counts (exact) --------------------------------------------------'
-- count(*) via query_to_xml rather than pg_class.reltuples, which reports -1 for
-- tables that have never been analysed and would make the diff meaningless.
SELECT table_name, row_count
FROM (
    SELECT table_name,
           (xpath('/row/c/text()',
                  query_to_xml('SELECT count(*) AS c FROM public.' || quote_ident(table_name),
                               false, true, '')))[1]::text::bigint AS row_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
) AS counts
WHERE table_name <> 'alembic_version'
ORDER BY table_name;

\echo ''
\echo '--- exact counts for tables where precision matters ---------------------'
SELECT 'journal_entry_lines' AS table_name, count(*) AS row_count FROM journal_entry_lines
UNION ALL SELECT 'journal_entries', count(*) FROM journal_entries
UNION ALL SELECT 'financial_document_lines', count(*) FROM financial_document_lines
UNION ALL SELECT 'financial_documents', count(*) FROM financial_documents
UNION ALL SELECT 'financial_document_allocations', count(*) FROM financial_document_allocations
UNION ALL SELECT 'posting_rules', count(*) FROM posting_rules
UNION ALL SELECT 'quotations', count(*) FROM quotations
UNION ALL SELECT 'quotation_revisions', count(*) FROM quotation_revisions
UNION ALL SELECT 'quotation_revision_lines', count(*) FROM quotation_revision_lines
UNION ALL SELECT 'service_orders', count(*) FROM service_orders
UNION ALL SELECT 'service_order_component_rows', count(*) FROM service_order_component_rows
UNION ALL SELECT 'component_tabs', count(*) FROM component_tabs
UNION ALL SELECT 'business_parties', count(*) FROM business_parties
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'role_permissions', count(*) FROM role_permissions
UNION ALL SELECT 'permissions', count(*) FROM permissions
UNION ALL SELECT 'audit_events', count(*) FROM audit_events
UNION ALL SELECT 'archive_records', count(*) FROM archive_records
UNION ALL SELECT 'attachments', count(*) FROM attachments
ORDER BY table_name;

\echo ''
\echo '--- financial control totals (must be unchanged by any migration) -------'
SELECT 'posted debit total'  AS metric, COALESCE(SUM(l.debit_amount), 0)  AS amount
FROM journal_entry_lines l JOIN journal_entries j ON j.id = l.journal_entry_id
WHERE j.status = 'POSTED'
UNION ALL
SELECT 'posted credit total', COALESCE(SUM(l.credit_amount), 0)
FROM journal_entry_lines l JOIN journal_entries j ON j.id = l.journal_entry_id
WHERE j.status = 'POSTED'
UNION ALL
SELECT 'posted base debit total', COALESCE(SUM(l.base_debit_amount), 0)
FROM journal_entry_lines l JOIN journal_entries j ON j.id = l.journal_entry_id
WHERE j.status = 'POSTED'
UNION ALL
SELECT 'posted base credit total', COALESCE(SUM(l.base_credit_amount), 0)
FROM journal_entry_lines l JOIN journal_entries j ON j.id = l.journal_entry_id
WHERE j.status = 'POSTED'
UNION ALL
SELECT 'allocated amount total', COALESCE(SUM(allocated_amount), 0) FROM financial_document_allocations
UNION ALL
SELECT 'document total (non-draft/reversed)', COALESCE(SUM(total_amount), 0)
FROM financial_documents WHERE status NOT IN ('DRAFT', 'REVERSED', 'CANCELLED')
ORDER BY metric;

\echo ''
\echo '--- integrity: these must all be 0 -------------------------------------'
SELECT 'unbalanced posted journals' AS check_name, count(*) AS offenders FROM (
    SELECT j.id FROM journal_entries j
    JOIN journal_entry_lines l ON l.journal_entry_id = j.id
    WHERE j.status = 'POSTED'
    GROUP BY j.id
    HAVING COALESCE(SUM(l.debit_amount), 0) <> COALESCE(SUM(l.credit_amount), 0)
) AS unbalanced
UNION ALL
SELECT 'duplicate quotation revision numbers', count(*) FROM (
    SELECT quotation_id, revision_no FROM quotation_revisions
    GROUP BY quotation_id, revision_no HAVING count(*) > 1
) AS duplicates
UNION ALL
SELECT 'service orders without a customer', count(*) FROM service_orders so
    LEFT JOIN business_parties bp ON bp.id = so.customer_party_id WHERE bp.id IS NULL
UNION ALL
SELECT 'service orders without a trade direction', count(*) FROM service_orders so
    LEFT JOIN trade_directions td ON td.id = so.trade_direction_id WHERE td.id IS NULL
UNION ALL
SELECT 'quotation revisions without a quotation', count(*) FROM quotation_revisions r
    LEFT JOIN quotations q ON q.id = r.quotation_id WHERE q.id IS NULL
UNION ALL
SELECT 'journal lines without a journal', count(*) FROM journal_entry_lines l
    LEFT JOIN journal_entries j ON j.id = l.journal_entry_id WHERE j.id IS NULL
UNION ALL
SELECT 'journal lines without an account', count(*) FROM journal_entry_lines l
    LEFT JOIN chart_of_accounts a ON a.id = l.account_id WHERE a.id IS NULL
UNION ALL
SELECT 'component rows without a group', count(*) FROM service_order_component_rows r
    LEFT JOIN component_groups g ON g.id = r.group_id WHERE g.id IS NULL
UNION ALL
SELECT 'component rows without a service order', count(*) FROM service_order_component_rows r
    LEFT JOIN service_orders so ON so.id = r.service_order_id WHERE so.id IS NULL
ORDER BY check_name;

\echo ''
\echo '--- schema shape --------------------------------------------------------'
SELECT
    (SELECT count(*) FROM information_schema.tables
      WHERE table_schema = 'public' AND table_type = 'BASE TABLE') AS tables,
    (SELECT count(*) FROM information_schema.views WHERE table_schema = 'public') AS views,
    (SELECT count(*) FROM pg_constraint
      WHERE contype = 'f' AND connamespace = 'public'::regnamespace AND NOT convalidated) AS unvalidated_fks,
    (SELECT version_num FROM alembic_version) AS revision;
