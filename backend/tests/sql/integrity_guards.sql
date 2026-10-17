-- Manual validation of the PostgreSQL integrity guards added by
-- migration e6f7a8b9c0d1_reporting_views_and_integrity.py.
--
-- Run against a DISPOSABLE database only (all tables are truncated first):
--   psql -v ON_ERROR_STOP=0 -d lcs_scratch -f backend/tests/sql/integrity_guards.sql
--
-- Each step states what it expects. The interesting assertions are the ones
-- annotated "must FAIL <expected message>": if such a step prints no ERROR, the
-- guard is missing. Detail lines, sequence numbers and NOTICE output are noise.
\set ON_ERROR_STOP off
\pset pager off

TRUNCATE journal_entry_lines, journal_entries, financial_document_allocations,
         financial_documents, accounting_periods, chart_of_accounts, business_parties,
         service_orders, currency_rates, audit_events, configuration_versions,
         component_tab_groups, component_groups, component_tabs, component_group_attributes,
         component_attributes, trade_directions, currencies, users, roles
    RESTART IDENTITY CASCADE;

INSERT INTO roles (code, name, is_system_role, status) VALUES ('TEST_ROLE', 'Test Role', FALSE, 'ACTIVE');
INSERT INTO users (user_code, username, email, display_name, status, locale, timezone, token_version)
    VALUES ('T1', 'tester', 'tester@example.test', 'Tester', 'ACTIVE', 'en', 'UTC', 0);
INSERT INTO business_parties (party_code, legal_name, roles, status)
    VALUES ('C1', 'Customer One', '["CUSTOMER"]', 'ACTIVE'), ('S1', 'Supplier One', '["SUPPLIER"]', 'ACTIVE');
INSERT INTO chart_of_accounts (account_code, account_name, account_type, normal_balance, is_postable, status) VALUES
    ('1100', 'Accounts Receivable', 'ASSET', 'DEBIT', TRUE, 'ACTIVE'),
    ('4010', 'Freight Revenue', 'REVENUE', 'CREDIT', TRUE, 'ACTIVE'),
    ('1020', 'Cash and Bank', 'ASSET', 'DEBIT', TRUE, 'ACTIVE');
INSERT INTO accounting_periods (period_year, period_month, start_date, end_date, status)
    VALUES (2026, 1, '2026-01-01', '2026-01-31', 'OPEN'),
           (2026, 2, '2026-02-01', '2026-02-28', 'CLOSED');
INSERT INTO currencies (code, name, status) VALUES ('USD', 'US Dollar', 'ACTIVE'), ('KHR', 'Cambodian Riel', 'ACTIVE');
INSERT INTO trade_directions (code, name, status) VALUES ('IMPORT', 'Import', 'ACTIVE');
INSERT INTO component_attributes (code, label, data_type, is_required, options, validation_rules, status)
    VALUES ('ref_no', 'Reference No.', 'text', FALSE, '[]', '{}', 'ACTIVE');
INSERT INTO component_groups (code, name, render_mode, display_order, is_active, is_archived)
    VALUES ('main', 'Main', 'form', 10, TRUE, FALSE);
INSERT INTO component_group_attributes (group_id, attribute_id, display_order, status)
    VALUES (1, 1, 10, 'ACTIVE');
INSERT INTO component_tabs (code, name, display_order, is_active, is_archived, trade_direction_id)
    VALUES ('general', 'General', 10, TRUE, FALSE, 1);
INSERT INTO component_tab_groups (tab_id, group_id, display_order, status) VALUES (1, 1, 10, 'ACTIVE');

\echo ''
\echo '=== G1: balanced DRAFT -> POSTED journal  (must SUCCEED) ==='
BEGIN;
INSERT INTO journal_entries (entry_no, entry_type, entry_date, posting_date, accounting_period_id, status,
                             debit_total, credit_total, data)
    VALUES ('JE-OK', 'MANUAL', '2026-01-15', '2026-01-15', 1, 'DRAFT', 0, 0, '{}');
INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, debit_amount, credit_amount, currency_code,
                                 exchange_rate, base_debit_amount, base_credit_amount)
    VALUES (currval('journal_entries_id_seq'), 1, 1, 100, 0, 'USD', 1, 100, 0),
           (currval('journal_entries_id_seq'), 2, 2, 0, 100, 'USD', 1, 0, 100);
UPDATE journal_entries SET status = 'POSTED', debit_total = 100, credit_total = 100
    WHERE id = currval('journal_entries_id_seq');
COMMIT;
\echo '    expected: COMMIT, no ERROR above'

\echo ''
\echo '=== G2: promoting an UNBALANCED draft to POSTED  (must FAIL: balanced lines) ==='
BEGIN;
INSERT INTO journal_entries (entry_no, entry_type, entry_date, posting_date, accounting_period_id, status,
                             debit_total, credit_total, data)
    VALUES ('JE-BAD', 'MANUAL', '2026-01-15', '2026-01-15', 1, 'DRAFT', 0, 0, '{}');
INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, debit_amount, credit_amount, currency_code,
                                 exchange_rate, base_debit_amount, base_credit_amount)
    VALUES (currval('journal_entries_id_seq'), 1, 1, 100, 0, 'USD', 1, 100, 0),
           (currval('journal_entries_id_seq'), 2, 2, 0, 40, 'USD', 1, 0, 40);
UPDATE journal_entries SET status = 'POSTED', debit_total = 100, credit_total = 40
    WHERE id = currval('journal_entries_id_seq');
COMMIT;

\echo ''
\echo '=== G3: posting a balanced journal into a CLOSED period  (must FAIL: open period) ==='
BEGIN;
INSERT INTO journal_entries (entry_no, entry_type, entry_date, posting_date, accounting_period_id, status,
                             debit_total, credit_total, data)
    VALUES ('JE-CLOSED', 'MANUAL', '2026-02-10', '2026-02-10', 2, 'DRAFT', 0, 0, '{}');
INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, debit_amount, credit_amount, currency_code,
                                 exchange_rate, base_debit_amount, base_credit_amount)
    VALUES (currval('journal_entries_id_seq'), 1, 1, 50, 0, 'USD', 1, 50, 0),
           (currval('journal_entries_id_seq'), 2, 2, 0, 50, 'USD', 1, 0, 50);
UPDATE journal_entries SET status = 'POSTED', debit_total = 50, credit_total = 50
    WHERE id = currval('journal_entries_id_seq');
COMMIT;

\echo ''
\echo '=== G4: a single-line journal is not postable  (must FAIL: at least two lines) ==='
BEGIN;
INSERT INTO journal_entries (entry_no, entry_type, entry_date, posting_date, accounting_period_id, status,
                             debit_total, credit_total, data)
    VALUES ('JE-ONE', 'MANUAL', '2026-01-15', '2026-01-15', 1, 'DRAFT', 0, 0, '{}');
INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, debit_amount, credit_amount, currency_code,
                                 exchange_rate, base_debit_amount, base_credit_amount)
    VALUES (currval('journal_entries_id_seq'), 1, 1, 100, 0, 'USD', 1, 100, 0);
UPDATE journal_entries SET status = 'POSTED', debit_total = 100, credit_total = 100
    WHERE id = currval('journal_entries_id_seq');
COMMIT;

\echo ''
\echo '=== G5: updating a POSTED journal  (must FAIL: immutable) ==='
UPDATE journal_entries SET description = 'tampered' WHERE entry_no = 'JE-OK';

\echo ''
\echo '=== G6: inserting a line into a POSTED journal  (must FAIL: lines cannot change) ==='
INSERT INTO journal_entry_lines (journal_entry_id, line_no, account_id, debit_amount, credit_amount, currency_code,
                                 exchange_rate, base_debit_amount, base_credit_amount)
    SELECT id, 3, 3, 5, 0, 'USD', 1, 5, 0 FROM journal_entries WHERE entry_no = 'JE-OK';

\echo ''
\echo '=== G7: deleting a POSTED journal  (must FAIL: cannot be deleted) ==='
DELETE FROM journal_entries WHERE entry_no = 'JE-OK';

\echo ''
\echo '=== G8: audit events are append-only  (must FAIL twice) ==='
INSERT INTO audit_events (event_type, entity_type, entity_id, action, result)
    VALUES ('TEST', 'service_order', 1, 'CREATE', 'SUCCESS');
UPDATE audit_events SET action = 'TAMPER' WHERE event_type = 'TEST';
DELETE FROM audit_events WHERE event_type = 'TEST';

\echo ''
\echo '=== G9: over-allocating a payment  (must FAIL: exceeds remaining balance) ==='
INSERT INTO financial_documents (document_no, document_type, document_date, status, party_id, currency_code,
                                 exchange_rate, subtotal_amount, discount_amount, tax_amount, total_amount,
                                 paid_amount, data)
    VALUES ('PAY-1', 'CUSTOMER_RECEIPT', '2026-01-10', 'POSTED', 1, 'USD', 1, 100, 0, 0, 100, 0, '{}'),
           ('INV-1', 'CUSTOMER_INVOICE', '2026-01-05', 'POSTED', 1, 'USD', 1, 500, 0, 0, 500, 0, '{}');
INSERT INTO financial_document_allocations (payment_document_id, target_document_id, allocated_amount,
                                            allocated_currency_code, exchange_rate)
    VALUES (1, 2, 100, 'USD', 1);
INSERT INTO financial_document_allocations (payment_document_id, target_document_id, allocated_amount,
                                            allocated_currency_code, exchange_rate)
    VALUES (1, 2, 1, 'USD', 1);

\echo ''
\echo '=== G10: deleting an allocation  (must SUCCEED: reversal unwinds them) ==='
DELETE FROM financial_document_allocations WHERE payment_document_id = 1;
\echo '    expected: DELETE 1'

\echo ''
\echo '=== G11: self-converting currency rate  (must FAIL: distinct_pair check) ==='
INSERT INTO currency_rates (from_currency_id, to_currency_id, effective_date, rate, status)
    VALUES (1, 1, '2026-01-01', 1, 'ACTIVE');

\echo ''
\echo '=== G12: a zero or negative rate  (must FAIL: rate_positive check) ==='
INSERT INTO currency_rates (from_currency_id, to_currency_id, effective_date, rate, status)
    VALUES (1, 2, '2026-01-01', 0, 'ACTIVE');

\echo ''
\echo '=== G13: only ONE configuration version may be PUBLISHED  (must FAIL on the second) ==='
INSERT INTO configuration_versions (version_no, status, config_snapshot) VALUES (1, 'PUBLISHED', '{"tabs":[]}');
INSERT INTO configuration_versions (version_no, status, config_snapshot) VALUES (2, 'PUBLISHED', '{"tabs":[]}');
INSERT INTO configuration_versions (version_no, status, config_snapshot) VALUES (3, 'RETIRED', '{"tabs":[]}');
\echo '    expected: one ERROR (uq_configuration_versions_published on version 2); version 3 must insert'

\echo ''
\echo '=== G14: a duplicate currency code among active rows  (must FAIL) ==='
INSERT INTO currencies (code, name, status) VALUES ('USD', 'Duplicate Dollar', 'ACTIVE');

\echo ''
\echo '=== G15: reporting views ==='
SELECT 'vw_trial_balance' AS view_name, count(*) AS rows FROM vw_trial_balance
UNION ALL SELECT 'vw_general_ledger', count(*) FROM vw_general_ledger
UNION ALL SELECT 'vw_invoice_outstanding', count(*) FROM vw_invoice_outstanding
UNION ALL SELECT 'vw_payments', count(*) FROM vw_payments
UNION ALL SELECT 'vw_payment_allocations', count(*) FROM vw_payment_allocations
UNION ALL SELECT 'vw_service_order_status', count(*) FROM vw_service_order_status
UNION ALL SELECT 'vw_service_order_charge_summary', count(*) FROM vw_service_order_charge_summary
UNION ALL SELECT 'vw_quotation_version_history', count(*) FROM vw_quotation_version_history
ORDER BY 1;
\echo '    expected: trial_balance 2, general_ledger 2, invoice_outstanding 1, payments 1'

\echo ''
\echo '    expected: 1100 debit 100, 4010 credit 100 (balanced ledger)'
SELECT account_code, total_debit, total_credit, net_debit_balance FROM vw_trial_balance ORDER BY account_code;

\echo ''
\echo '=== G16: the administrative reset escape hatch unblocks the guards ==='
BEGIN;
SET LOCAL lcs.allow_financial_purge = 'on';
DELETE FROM journal_entries WHERE entry_no = 'JE-OK';
COMMIT;
\echo '    expected: DELETE 1 then COMMIT, no ERROR'

\echo ''
\echo '=== FINAL STATE ==='
\echo '    expected: JE-OK gone; only the audit row remains, unmodified'
SELECT entry_no, status FROM journal_entries ORDER BY id;
SELECT event_type, action FROM audit_events;
