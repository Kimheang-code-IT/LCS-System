-- Development seed data for the consolidated v2 schema.
-- Never include production secrets or real customer credentials.

BEGIN;

INSERT INTO organizations (organization_code, legal_name, display_name, country_code, default_currency_code, timezone)
VALUES ('DEMO', 'Demo Freight Forwarding Co., Ltd.', 'Demo Freight', 'KH', 'USD', 'Asia/Phnom_Penh')
ON CONFLICT (organization_code) DO NOTHING;

INSERT INTO places (code, name, place_category, country_code)
VALUES
  ('PP', 'Phnom Penh', 'ADMINISTRATIVE', 'KH'),
  ('BV', 'Bavet', 'BORDER_CHECKPOINT', 'KH'),
  ('PP_PORT', 'Phnom Penh Port', 'PORT', 'KH'),
  ('SEZ_DEMO', 'Demo Special Economic Zone', 'SEZ', 'KH')
ON CONFLICT (code) DO NOTHING;

INSERT INTO branches (organization_id, branch_code, name, place_id, address, is_head_office)
SELECT o.id, x.branch_code, x.name, p.id, x.address, x.is_head_office
FROM organizations o
JOIN (VALUES
  ('PP', 'Phnom Penh Branch', 'Phnom Penh', true),
  ('BV', 'Bavet Branch', 'Bavet', false)
) AS x(branch_code, name, place_name, is_head_office) ON true
JOIN places p ON p.name = x.place_name
WHERE o.organization_code = 'DEMO'
ON CONFLICT (organization_id, branch_code) DO NOTHING;

INSERT INTO trade_directions (code, name, description)
VALUES
  ('IMPORT', 'Import', 'Goods enter the country'),
  ('EXPORT', 'Export', 'Goods leave the country'),
  ('TRANSIT', 'Transit', 'Goods pass through the country'),
  ('RE_EXPORT', 'Re-export', 'Previously imported goods leave the country')
ON CONFLICT (code) DO NOTHING;

INSERT INTO transport_types (code, name)
VALUES ('TRUCK', 'Truck'), ('VESSEL', 'Vessel'), ('AIR', 'Air'), ('RAIL', 'Rail'), ('MULTIMODAL', 'Multimodal')
ON CONFLICT (code) DO NOTHING;

INSERT INTO container_types (code, name, container_size, container_kind, iso_code, length_feet)
VALUES
  ('20DV', '20-foot Dry Van', '20FT', 'DRY', '22G1', 20),
  ('40DV', '40-foot Dry Van', '40FT', 'DRY', '42G1', 40),
  ('40HC', '40-foot High Cube', '40FT', 'HIGH_CUBE', '45G1', 40),
  ('40RF', '40-foot Reefer', '40FT', 'REEFER', '45R1', 40)
ON CONFLICT (code) DO NOTHING;

INSERT INTO fee_types (code, name)
VALUES
  ('CUSTOMS_CLEARANCE', 'Customs Clearance'),
  ('INLAND_TRANSPORT', 'Inland Transport'),
  ('BORDER_HANDLING', 'Border Handling'),
  ('DOCUMENTATION', 'Documentation'),
  ('STORAGE', 'Storage'),
  ('PORT_HANDLING', 'Port Handling'),
  ('OTHER', 'Other')
ON CONFLICT (code) DO NOTHING;

INSERT INTO component_groups (code, name, display_order)
VALUES
  ('CARGO', 'Cargo', 10),
  ('TRANSPORT', 'Transport', 20),
  ('CUSTOMS', 'Customs', 30),
  ('SHIPPING_DOCUMENTS', 'Shipping Documents', 40),
  ('MILESTONES', 'Milestones', 50),
  ('FINANCE', 'Finance', 60)
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (user_code, username, email, display_name, status)
VALUES
  ('ADMIN-001', 'admin', 'admin@example.test', 'Demo Administrator', 'ACTIVE'),
  ('OPS-PP-001', 'ops.pp', 'ops.pp@example.test', 'Phnom Penh Operations', 'ACTIVE'),
  ('FIN-001', 'finance', 'finance@example.test', 'Finance Officer', 'ACTIVE')
ON CONFLICT (username) DO NOTHING;

-- Replace these development-only hashes before use. They are intentionally placeholders.
INSERT INTO user_credentials (user_id, password_hash, password_algorithm)
SELECT id, '$argon2id$REPLACE_WITH_DEV_ONLY_HASH', 'argon2id'
FROM users
WHERE username IN ('admin', 'ops.pp', 'finance')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO roles (code, name, description, is_system_role)
VALUES
  ('PLATFORM_ADMIN', 'Platform Administrator', 'Full platform administration', true),
  ('ORGANIZATION_ADMIN', 'Organization Administrator', 'Organization and branch administration', true),
  ('BRANCH_MANAGER', 'Branch Manager', 'Branch operations and review', true),
  ('SALES_OFFICER', 'Sales Officer', 'Quotation and commercial work', true),
  ('OPERATIONS_OFFICER', 'Operations Officer', 'Service-order operations', true),
  ('FINANCE_OFFICER', 'Finance Officer', 'Financial drafts, payments, and allocations', true),
  ('FINANCE_MANAGER', 'Finance Manager', 'Posting, periods, journals, and reversals', true),
  ('AUDITOR', 'Auditor', 'Read-only review', true)
ON CONFLICT (code) DO NOTHING;

INSERT INTO permissions (code, name, resource, action)
VALUES
  ('organization.read', 'Read organization', 'organization', 'read'),
  ('organization.update', 'Update organization', 'organization', 'update'),
  ('branch.read', 'Read branch', 'branch', 'read'),
  ('branch.manage', 'Manage branch', 'branch', 'manage'),
  ('user.read', 'Read users', 'user', 'read'),
  ('user.manage', 'Manage users', 'user', 'manage'),
  ('role.read', 'Read roles', 'role', 'read'),
  ('role.manage', 'Manage roles', 'role', 'manage'),
  ('quotation.read', 'Read quotations', 'quotation', 'read'),
  ('quotation.create', 'Create quotation', 'quotation', 'create'),
  ('quotation.update_draft', 'Update quotation draft', 'quotation', 'update_draft'),
  ('quotation.send', 'Send quotation', 'quotation', 'send'),
  ('quotation.accept', 'Accept quotation', 'quotation', 'accept'),
  ('quotation.convert', 'Convert quotation', 'quotation', 'convert'),
  ('service_order.read', 'Read service orders', 'service_order', 'read'),
  ('service_order.create', 'Create service order', 'service_order', 'create'),
  ('service_order.update', 'Update service order', 'service_order', 'update'),
  ('service_order.complete', 'Complete service order', 'service_order', 'complete'),
  ('service_charge.create', 'Create service charge', 'service_charge', 'create'),
  ('service_charge.issue', 'Issue service charge', 'service_charge', 'issue'),
  ('service_charge.convert_to_invoice', 'Convert charge to invoice', 'service_charge', 'convert_to_invoice'),
  ('financial_document.read', 'Read financial document', 'financial_document', 'read'),
  ('financial_document.create', 'Create financial document', 'financial_document', 'create'),
  ('financial_document.update_draft', 'Update financial draft', 'financial_document', 'update_draft'),
  ('financial_document.post', 'Post financial document', 'financial_document', 'post'),
  ('financial_document.reverse', 'Reverse financial document', 'financial_document', 'reverse'),
  ('financial_document.allocate', 'Allocate payment', 'financial_document', 'allocate'),
  ('journal_entry.read', 'Read journal entry', 'journal_entry', 'read'),
  ('journal_entry.create', 'Create journal entry', 'journal_entry', 'create'),
  ('journal_entry.post', 'Post journal entry', 'journal_entry', 'post'),
  ('accounting_period.read', 'Read accounting period', 'accounting_period', 'read'),
  ('accounting_period.close', 'Close accounting period', 'accounting_period', 'close'),
  ('chart_of_accounts.manage', 'Manage chart of accounts', 'chart_of_accounts', 'manage'),
  ('customs_credential.retrieve', 'Retrieve customs credential', 'customs_credential', 'retrieve'),
  ('attachment.read', 'Read attachment', 'attachment', 'read'),
  ('attachment.upload', 'Upload attachment', 'attachment', 'upload'),
  ('attachment.delete', 'Delete attachment', 'attachment', 'delete'),
  ('audit_log.read', 'Read audit log', 'audit_log', 'read'),
  ('report.read', 'Read reports', 'report', 'read')
ON CONFLICT (code) DO NOTHING;

-- Platform administrator receives all seeded permissions.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r CROSS JOIN permissions p
WHERE r.code = 'PLATFORM_ADMIN'
ON CONFLICT DO NOTHING;

-- Finance officer permissions.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code IN (
  'organization.read', 'branch.read', 'service_order.read', 'service_charge.create', 'service_charge.issue',
  'service_charge.convert_to_invoice', 'financial_document.read', 'financial_document.create', 'financial_document.update_draft',
  'financial_document.post', 'financial_document.allocate', 'journal_entry.read', 'journal_entry.create', 'journal_entry.post',
  'accounting_period.read', 'attachment.read', 'attachment.upload', 'report.read'
)
WHERE r.code = 'FINANCE_OFFICER'
ON CONFLICT DO NOTHING;

-- Operations officer permissions.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code IN (
  'organization.read', 'branch.read', 'quotation.read', 'quotation.convert', 'service_order.read',
  'service_order.create', 'service_order.update', 'service_order.complete', 'service_charge.create', 'service_charge.issue',
  'attachment.read', 'attachment.upload', 'report.read'
)
WHERE r.code = 'OPERATIONS_OFFICER'
ON CONFLICT DO NOTHING;

-- Finance manager receives finance administration permissions.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r JOIN permissions p ON p.code IN (
  'organization.read', 'branch.read', 'financial_document.read', 'financial_document.create', 'financial_document.update_draft',
  'financial_document.post', 'financial_document.reverse', 'financial_document.allocate', 'journal_entry.read',
  'journal_entry.create', 'journal_entry.post', 'accounting_period.read', 'accounting_period.close',
  'chart_of_accounts.manage', 'audit_log.read', 'attachment.read', 'report.read'
)
WHERE r.code = 'FINANCE_MANAGER'
ON CONFLICT DO NOTHING;

-- Assign demo users. Branch IDs are resolved by organization and code.
INSERT INTO user_role_assignments (user_id, role_id, organization_id, branch_id)
SELECT u.id, r.id, o.id, b.id
FROM users u
JOIN roles r ON r.code = 'PLATFORM_ADMIN'
JOIN organizations o ON o.organization_code = 'DEMO'
JOIN branches b ON b.organization_id = o.id AND b.branch_code = 'PP'
WHERE u.username = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO user_role_assignments (user_id, role_id, organization_id, branch_id)
SELECT u.id, r.id, o.id, b.id
FROM users u
JOIN roles r ON r.code = 'OPERATIONS_OFFICER'
JOIN organizations o ON o.organization_code = 'DEMO'
JOIN branches b ON b.organization_id = o.id AND b.branch_code = 'PP'
WHERE u.username = 'ops.pp'
ON CONFLICT DO NOTHING;

INSERT INTO user_role_assignments (user_id, role_id, organization_id, branch_id)
SELECT u.id, r.id, o.id, NULL
FROM users u
JOIN roles r ON r.code = 'FINANCE_OFFICER'
JOIN organizations o ON o.organization_code = 'DEMO'
WHERE u.username = 'finance'
ON CONFLICT DO NOTHING;

INSERT INTO user_branch_assignments (user_id, organization_id, branch_id, is_default)
SELECT u.id, o.id, b.id, true
FROM users u
JOIN organizations o ON o.organization_code = 'DEMO'
JOIN branches b ON b.organization_id = o.id AND b.branch_code = 'PP'
WHERE u.username IN ('admin', 'ops.pp', 'finance')
ON CONFLICT DO NOTHING;

-- Create the current development accounting period.
INSERT INTO accounting_periods (organization_id, period_year, period_month, start_date, end_date)
SELECT id, 2026, 8, DATE '2026-08-01', DATE '2026-08-31'
FROM organizations WHERE organization_code = 'DEMO'
ON CONFLICT (organization_id, period_year, period_month) DO NOTHING;

-- Create organization-wide sequences.
INSERT INTO document_sequences (organization_id, document_type, period_year, prefix, padding_length)
SELECT id, x.document_type, 2026, x.prefix, 6
FROM organizations o
CROSS JOIN (VALUES
  ('QUOTATION', 'Q'), ('SERVICE_ORDER', 'SO'), ('SERVICE_CHARGE', 'SC'), ('CUSTOMER_INVOICE', 'INV'),
  ('SUPPLIER_BILL', 'BILL'), ('CUSTOMER_RECEIPT', 'REC'), ('SUPPLIER_PAYMENT', 'PAY'), ('JOURNAL', 'JE')
) AS x(document_type, prefix)
WHERE o.organization_code = 'DEMO'
ON CONFLICT (organization_id, document_type, period_year) DO NOTHING;

-- Seed organization chart of accounts.
INSERT INTO chart_of_accounts (organization_id, account_code, account_name, account_type, normal_balance, is_postable)
SELECT o.id, x.account_code, x.account_name, x.account_type::account_type, x.normal_balance::normal_balance, true
FROM organizations o
CROSS JOIN (VALUES
  ('1010', 'Cash on Hand', 'ASSET', 'DEBIT'),
  ('1020', 'Bank Account', 'ASSET', 'DEBIT'),
  ('1100', 'Accounts Receivable', 'ASSET', 'DEBIT'),
  ('1200', 'Prepayments', 'ASSET', 'DEBIT'),
  ('2010', 'Accounts Payable', 'LIABILITY', 'CREDIT'),
  ('3010', 'Owner Equity', 'EQUITY', 'CREDIT'),
  ('4010', 'Service Revenue', 'REVENUE', 'CREDIT'),
  ('4020', 'Other Income', 'REVENUE', 'CREDIT'),
  ('5010', 'Transport Expense', 'EXPENSE', 'DEBIT'),
  ('5020', 'Customs Expense', 'EXPENSE', 'DEBIT'),
  ('5030', 'Office Expense', 'EXPENSE', 'DEBIT'),
  ('5040', 'Bank Charges', 'EXPENSE', 'DEBIT')
) AS x(account_code, account_name, account_type, normal_balance)
WHERE o.organization_code = 'DEMO'
ON CONFLICT (organization_id, account_code) DO NOTHING;

INSERT INTO financial_accounts (organization_id, account_id, account_name, account_type, currency_code, bank_name, account_number_masked)
SELECT o.id, coa.id, x.account_name, x.account_type, 'USD', x.bank_name, x.masked
FROM organizations o
JOIN (VALUES
  ('Bank Account', 'BANK', 'ABA Bank', '****1234'),
  ('Cash on Hand', 'CASH', NULL, NULL)
) AS x(account_name, account_type, bank_name, masked) ON true
JOIN chart_of_accounts coa ON coa.organization_id = o.id AND coa.account_name = x.account_name
WHERE o.organization_code = 'DEMO'
ON CONFLICT (organization_id, account_id) DO NOTHING;

-- Seed standard posting rules.
INSERT INTO posting_rules (organization_id, document_type, debit_account_id, credit_account_id)
SELECT o.id, x.document_type, dr.id, cr.id
FROM organizations o
JOIN (VALUES
  ('CUSTOMER_INVOICE', '1100', '4010'),
  ('SUPPLIER_BILL', '5010', '2010'),
  ('CUSTOMER_RECEIPT', '1020', '1100'),
  ('SUPPLIER_PAYMENT', '2010', '1020'),
  ('OTHER_INCOME', '1020', '4020'),
  ('OTHER_EXPENSE', '5030', '1020')
) AS x(document_type, debit_code, credit_code) ON true
JOIN chart_of_accounts dr ON dr.organization_id = o.id AND dr.account_code = x.debit_code
JOIN chart_of_accounts cr ON cr.organization_id = o.id AND cr.account_code = x.credit_code
WHERE o.organization_code = 'DEMO'
AND NOT EXISTS (
  SELECT 1 FROM posting_rules pr
  WHERE pr.organization_id = o.id AND pr.document_type = x.document_type AND pr.fee_type_id IS NULL
);

COMMIT;
