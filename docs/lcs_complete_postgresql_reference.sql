-- LCS FREIGHT FORWARDING | extended 47-table PostgreSQL REFERENCE SCHEMA
-- DESIGN FOR NEW/EMPTY DATABASE ONLY. NEVER run against existing production tables.
-- Original baseline: optimized 44-table proposal; 3 added tables: currency_rates, backup_states, backup_records.
-- Persistent business data must be migrated from the 59-table legacy system through reviewed Alembic revisions.
-- This SQL adds DB-level protections; API authentication, RBAC, posting engine, form validation and real backups remain required.
-- WARNING: This is not evidence of production readiness.

-- roles: One role per user; permissions JSONB stores a validated list of permission codes.
CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    permissions JSONB NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    code VARCHAR(64) UNIQUE
);

-- users: User identity and account settings. Each user references one role.
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    role_id BIGINT NOT NULL,
    username VARCHAR(80) NOT NULL UNIQUE,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles (id)
);

-- business_parties: Optimized domain table retained for essential LCS workflow.
CREATE TABLE business_parties (
    id BIGSERIAL PRIMARY KEY,
    party_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    party_roles JSONB NOT NULL,
    tax_number VARCHAR(100) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    address TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    description TEXT,
    created_by BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- places: Optimized domain table retained for essential LCS workflow.
CREATE TABLE places (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    place_type VARCHAR(50) NOT NULL,
    address TEXT NOT NULL,
    description TEXT,
    created_by BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- currencies: Optimized domain table retained for essential LCS workflow.
CREATE TABLE currencies (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(3) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(10),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- container_types: Optimized domain table retained for essential LCS workflow.
CREATE TABLE container_types (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- transport_types: Optimized domain table retained for essential LCS workflow.
CREATE TABLE transport_types (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- transport_assets: Optimized domain table retained for essential LCS workflow.
CREATE TABLE transport_assets (
    id BIGSERIAL PRIMARY KEY,
    transport_type_id BIGINT,
    owner_party_id BIGINT,
    asset_code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    status VARCHAR(30) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transport_type_id) REFERENCES transport_types (id),
    FOREIGN KEY (owner_party_id) REFERENCES business_parties (id)
);

-- fee_types: Optimized domain table retained for essential LCS workflow.
CREATE TABLE fee_types (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- trade_directions: Optimized domain table retained for essential LCS workflow.
CREATE TABLE trade_directions (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- quotations: Stable quotation identity across all versions.
CREATE TABLE quotations (
    id BIGSERIAL PRIMARY KEY,
    quotation_no VARCHAR(60) NOT NULL UNIQUE,
    customer_id BIGINT NOT NULL REFERENCES business_parties(id),
    created_by BIGINT REFERENCES users(id),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
    current_version_id BIGINT
);

-- quotation_versions: Revision-specific commercial terms. Approved versions are immutable in application logic.
CREATE TABLE quotation_versions (
    id BIGSERIAL PRIMARY KEY,
    quotation_id BIGINT NOT NULL REFERENCES quotations(id),
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    currency_id BIGINT NOT NULL REFERENCES currencies(id),
    origin_place_id BIGINT REFERENCES places(id),
    destination_place_id BIGINT REFERENCES places(id),
    trade_direction_id BIGINT REFERENCES trade_directions(id),
    quotation_date DATE NOT NULL,
    valid_until DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    notes TEXT,
    change_note TEXT,
    created_by BIGINT REFERENCES users(id),
    approved_by BIGINT REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_quotation_versions_no UNIQUE (quotation_id, version_no),
    CONSTRAINT ck_quotation_versions_status CHECK (status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','SUPERSEDED')),
    CONSTRAINT ck_quotation_versions_dates CHECK (valid_until IS NULL OR valid_until >= quotation_date)
);

-- quotation_lines: Detailed price lines belonging to an exact quotation version.
CREATE TABLE quotation_lines (
    id BIGSERIAL PRIMARY KEY,
    quotation_version_id BIGINT NOT NULL REFERENCES quotation_versions(id),
    fee_type_id BIGINT REFERENCES fee_types(id),
    description TEXT NOT NULL,
    quantity NUMERIC(18,3) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(19,4) NOT NULL CHECK (unit_price >= 0),
    amount NUMERIC(19,4) NOT NULL CHECK (amount >= 0),
    sort_order INTEGER NOT NULL DEFAULT 1 CHECK (sort_order > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_quotation_lines_order UNIQUE (quotation_version_id, sort_order)
);

-- service_orders: Operational shipment/job header including trade direction and approved quotation version.
CREATE TABLE service_orders (
    id BIGSERIAL PRIMARY KEY,
    service_order_no VARCHAR(60) NOT NULL UNIQUE,
    trade_direction_id BIGINT NOT NULL REFERENCES trade_directions(id),
    quotation_version_id BIGINT,
    customer_id BIGINT NOT NULL,
    origin_place_id BIGINT,
    destination_place_id BIGINT,
    transport_type_id BIGINT,
    transport_asset_id BIGINT,
    service_date DATE,
    status VARCHAR(30) NOT NULL,
    reference_no VARCHAR(100),
    notes TEXT,
    created_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quotation_version_id) REFERENCES quotation_versions (id),
    FOREIGN KEY (customer_id) REFERENCES business_parties (id),
    FOREIGN KEY (origin_place_id) REFERENCES places (id),
    FOREIGN KEY (destination_place_id) REFERENCES places (id),
    FOREIGN KEY (transport_type_id) REFERENCES transport_types (id),
    FOREIGN KEY (transport_asset_id) REFERENCES transport_assets (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    configuration_version_id BIGINT
);

-- service_order_containers: Optimized domain table retained for essential LCS workflow.
CREATE TABLE service_order_containers (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL,
    container_type_id BIGINT,
    container_no VARCHAR(30) NOT NULL,
    seal_no VARCHAR(50),
    weight_kg NUMERIC(16,3),
    status VARCHAR(30),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (service_order_id) REFERENCES service_orders (id),
    FOREIGN KEY (container_type_id) REFERENCES container_types (id)
);

-- service_order_charges: Actual revenue and cost records for profitability tracking.
CREATE TABLE service_order_charges (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL,
    fee_type_id BIGINT,
    party_id BIGINT,
    currency_id BIGINT NOT NULL,
    charge_type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    quantity NUMERIC(18,3) NOT NULL,
    unit_price NUMERIC(19,4) NOT NULL,
    amount NUMERIC(19,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (service_order_id) REFERENCES service_orders (id),
    FOREIGN KEY (fee_type_id) REFERENCES fee_types (id),
    FOREIGN KEY (party_id) REFERENCES business_parties (id),
    FOREIGN KEY (currency_id) REFERENCES currencies (id),
    source_quotation_line_id BIGINT REFERENCES quotation_lines(id)
);

-- financial_accounts: Optimized domain table retained for essential LCS workflow.
CREATE TABLE financial_accounts (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    account_type VARCHAR(30) NOT NULL,
    currency_id BIGINT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (currency_id) REFERENCES currencies (id),
    ledger_account_id BIGINT
);

-- chart_of_accounts: Optimized domain table retained for essential LCS workflow.
CREATE TABLE chart_of_accounts (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT,
    account_code VARCHAR(40) NOT NULL UNIQUE,
    account_name VARCHAR(150) NOT NULL,
    account_type VARCHAR(30) NOT NULL,
    normal_balance VARCHAR(10) NOT NULL,
    is_postable BOOLEAN NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES chart_of_accounts (id)
);

-- accounting_periods: Optimized domain table retained for essential LCS workflow.
CREATE TABLE accounting_periods (
    id BIGSERIAL PRIMARY KEY,
    period_code VARCHAR(30) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    closed_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (closed_by) REFERENCES users (id)
);

-- financial_documents: Optimized domain table retained for essential LCS workflow.
CREATE TABLE financial_documents (
    id BIGSERIAL PRIMARY KEY,
    document_no VARCHAR(60) NOT NULL UNIQUE,
    document_type VARCHAR(30) NOT NULL,
    service_order_id BIGINT,
    party_id BIGINT NOT NULL,
    currency_id BIGINT NOT NULL,
    document_date DATE NOT NULL,
    due_date DATE,
    status VARCHAR(30) NOT NULL,
    total_amount NUMERIC(19,4) NOT NULL,
    notes TEXT,
    created_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (service_order_id) REFERENCES service_orders (id),
    FOREIGN KEY (party_id) REFERENCES business_parties (id),
    FOREIGN KEY (currency_id) REFERENCES currencies (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- financial_document_lines: Optimized domain table retained for essential LCS workflow.
CREATE TABLE financial_document_lines (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    service_charge_id BIGINT,
    account_id BIGINT,
    description TEXT NOT NULL,
    quantity NUMERIC(18,3) NOT NULL,
    unit_price NUMERIC(19,4) NOT NULL,
    amount NUMERIC(19,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES financial_documents (id),
    FOREIGN KEY (service_charge_id) REFERENCES service_order_charges (id),
    FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
);

-- payments: Optimized domain table retained for essential LCS workflow.
CREATE TABLE payments (
    id BIGSERIAL PRIMARY KEY,
    payment_no VARCHAR(60) NOT NULL UNIQUE,
    party_id BIGINT NOT NULL,
    financial_account_id BIGINT NOT NULL,
    currency_id BIGINT NOT NULL,
    payment_direction VARCHAR(20) NOT NULL,
    payment_date DATE NOT NULL,
    amount NUMERIC(19,4) NOT NULL,
    status VARCHAR(30) NOT NULL,
    reference_no VARCHAR(100),
    created_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (party_id) REFERENCES business_parties (id),
    FOREIGN KEY (financial_account_id) REFERENCES financial_accounts (id),
    FOREIGN KEY (currency_id) REFERENCES currencies (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- payment_allocations: How cash payments are applied to specific financial documents.
CREATE TABLE payment_allocations (
    id BIGSERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL,
    financial_document_id BIGINT NOT NULL,
    allocated_amount NUMERIC(19,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_id) REFERENCES payments (id),
    FOREIGN KEY (financial_document_id) REFERENCES financial_documents (id),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- journal_entries: Accounting posting headers; posted journals should never be edited.
CREATE TABLE journal_entries (
    id BIGSERIAL PRIMARY KEY,
    journal_no VARCHAR(60) NOT NULL UNIQUE,
    period_id BIGINT NOT NULL,
    document_id BIGINT,
    payment_id BIGINT,
    entry_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL,
    description TEXT,
    created_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (period_id) REFERENCES accounting_periods (id),
    FOREIGN KEY (document_id) REFERENCES financial_documents (id),
    FOREIGN KEY (payment_id) REFERENCES payments (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

-- journal_entry_lines: Debit/credit ledger entries; enforce balance before posting.
CREATE TABLE journal_entry_lines (
    id BIGSERIAL PRIMARY KEY,
    journal_entry_id BIGINT NOT NULL,
    account_id BIGINT NOT NULL,
    debit NUMERIC(19,4) NOT NULL,
    credit NUMERIC(19,4) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id),
    FOREIGN KEY (account_id) REFERENCES chart_of_accounts (id)
);

-- app_settings: Optimized domain table retained for essential LCS workflow.
CREATE TABLE app_settings (
    id BIGSERIAL PRIMARY KEY,
    setting_key VARCHAR(120) NOT NULL UNIQUE,
    setting_group VARCHAR(60) NOT NULL,
    setting_value JSONB NOT NULL,
    description TEXT,
    updated_by BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES users (id)
);

-- component_attributes: Reusable validated dynamic fields.
CREATE TABLE component_attributes (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    label VARCHAR(200) NOT NULL,
    label_km VARCHAR(200),
    data_type VARCHAR(30) NOT NULL,
    input_type VARCHAR(30),
    reference_type VARCHAR(60),
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    options JSONB NOT NULL DEFAULT '[]',
    validation_rules JSONB NOT NULL DEFAULT '{}',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- component_groups: Reusable dynamic form or table grouping.
CREATE TABLE component_groups (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    render_mode VARCHAR(20) NOT NULL DEFAULT 'FORM',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- component_tabs: Configurable Service Order tabs filtered by trade direction.
CREATE TABLE component_tabs (
    id BIGSERIAL PRIMARY KEY,
    trade_direction_id BIGINT REFERENCES trade_directions(id),
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    config_version_id BIGINT
);

-- component_group_attributes: Optimized domain table retained for essential LCS workflow.
CREATE TABLE component_group_attributes (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES component_groups(id),
    attribute_id BIGINT NOT NULL REFERENCES component_attributes(id),
    display_order INTEGER NOT NULL DEFAULT 1,
    required_override BOOLEAN,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_component_group_attribute UNIQUE (group_id, attribute_id)
);

-- component_tab_groups: Optimized domain table retained for essential LCS workflow.
CREATE TABLE component_tab_groups (
    id BIGSERIAL PRIMARY KEY,
    tab_id BIGINT NOT NULL REFERENCES component_tabs(id),
    group_id BIGINT NOT NULL REFERENCES component_groups(id),
    display_order INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_component_tab_group UNIQUE (tab_id, group_id)
);

-- service_order_component_rows: JSONB data entered into admin-configured forms/table groups.
CREATE TABLE service_order_component_rows (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id),
    group_id BIGINT NOT NULL REFERENCES component_groups(id),
    row_no INTEGER NOT NULL DEFAULT 1,
    field_values JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_service_order_group_row UNIQUE (service_order_id, group_id, row_no),
    config_version_id BIGINT
);

-- configuration_versions: Published snapshots of dynamic UI configurations for historical reproducibility.
CREATE TABLE configuration_versions (
 id BIGSERIAL PRIMARY KEY,
 version_no INTEGER NOT NULL UNIQUE CHECK (version_no > 0),
 status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED','RETIRED')),
 change_note TEXT,
 config_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
 published_at TIMESTAMPTZ,
 published_by BIGINT REFERENCES users(id),
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- document_sequences: Race-safe per-year document numbering counters.
CREATE TABLE document_sequences (
 id BIGSERIAL PRIMARY KEY,
 document_type VARCHAR(48) NOT NULL,
 period_year INTEGER NOT NULL,
 prefix VARCHAR(20) NOT NULL,
 padding_length INTEGER NOT NULL DEFAULT 5 CHECK (padding_length BETWEEN 1 AND 15),
 last_value BIGINT NOT NULL DEFAULT 0 CHECK (last_value >= 0),
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(document_type, period_year)
);

-- posting_rules: Mapping from financial document / fee type to debit/credit GL accounts.
CREATE TABLE posting_rules (
 id BIGSERIAL PRIMARY KEY,
 document_type VARCHAR(32) NOT NULL,
 fee_type_id BIGINT REFERENCES fee_types(id),
 debit_account_id BIGINT NOT NULL REFERENCES chart_of_accounts(id),
 credit_account_id BIGINT NOT NULL REFERENCES chart_of_accounts(id),
 tax_account_id BIGINT REFERENCES chart_of_accounts(id),
 description TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK (debit_account_id <> credit_account_id)
);

-- service_order_movements: Optimized domain table retained for essential LCS workflow.
CREATE TABLE service_order_movements (
 id BIGSERIAL PRIMARY KEY,
 service_order_id BIGINT NOT NULL REFERENCES service_orders(id),
 sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
 transport_type_id BIGINT REFERENCES transport_types(id),
 transport_asset_id BIGINT REFERENCES transport_assets(id),
 origin_place_id BIGINT REFERENCES places(id),
 destination_place_id BIGINT REFERENCES places(id),
 planned_departure TIMESTAMPTZ,
 actual_departure TIMESTAMPTZ,
 planned_arrival TIMESTAMPTZ,
 actual_arrival TIMESTAMPTZ,
 status VARCHAR(30) NOT NULL DEFAULT 'PLANNED',
 notes TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(service_order_id, sequence_no)
);

-- service_order_milestones: Optimized domain table retained for essential LCS workflow.
CREATE TABLE service_order_milestones (
 id BIGSERIAL PRIMARY KEY,
 service_order_id BIGINT NOT NULL REFERENCES service_orders(id),
 milestone_code VARCHAR(64) NOT NULL,
 milestone_name VARCHAR(200) NOT NULL,
 sequence_no INTEGER NOT NULL DEFAULT 1,
 planned_at TIMESTAMPTZ,
 actual_at TIMESTAMPTZ,
 status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
 notes TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(service_order_id, milestone_code)
);

-- service_order_pricing_lines: Customer-agreed revenue pricing per job, independent of actual costs.
CREATE TABLE service_order_pricing_lines (
 id BIGSERIAL PRIMARY KEY,
 service_order_id BIGINT NOT NULL REFERENCES service_orders(id),
 source_quotation_line_id BIGINT REFERENCES quotation_lines(id),
 fee_type_id BIGINT REFERENCES fee_types(id),
 currency_id BIGINT NOT NULL REFERENCES currencies(id),
 line_no INTEGER NOT NULL CHECK(line_no > 0),
 description TEXT NOT NULL,
 quantity NUMERIC(18,3) NOT NULL CHECK(quantity > 0),
 unit_price NUMERIC(19,4) NOT NULL CHECK(unit_price >= 0),
 discount_amount NUMERIC(19,4) NOT NULL DEFAULT 0,
 tax_amount NUMERIC(19,4) NOT NULL DEFAULT 0,
 line_total NUMERIC(19,4) NOT NULL DEFAULT 0,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(service_order_id, line_no)
);

-- audit_events: Append-only security and business event history; avoid PII in snapshots.
CREATE TABLE audit_events (
 id BIGSERIAL PRIMARY KEY,
 actor_user_id BIGINT REFERENCES users(id),
 event_type VARCHAR(64) NOT NULL,
 entity_type VARCHAR(64) NOT NULL,
 entity_id BIGINT,
 action VARCHAR(64) NOT NULL,
 result VARCHAR(20) NOT NULL,
 request_id VARCHAR(80),
 ip_address VARCHAR(64),
 before_json JSONB,
 after_json JSONB,
 metadata_json JSONB,
 occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- archive_records: Archive snapshots and restoration references.
CREATE TABLE archive_records (
 id BIGSERIAL PRIMARY KEY,
 entity_type VARCHAR(64) NOT NULL,
 entity_id BIGINT NOT NULL,
 record_reference VARCHAR(150),
 snapshot_json JSONB NOT NULL,
 archived_by BIGINT REFERENCES users(id),
 archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 restored_by BIGINT REFERENCES users(id),
 restored_at TIMESTAMPTZ,
 description TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- attachments: Secure object-storage metadata, not file bytes.
CREATE TABLE attachments (
 id BIGSERIAL PRIMARY KEY,
 file_name VARCHAR(512) NOT NULL,
 storage_key VARCHAR(512) NOT NULL UNIQUE,
 mime_type VARCHAR(128) NOT NULL,
 file_size_bytes BIGINT NOT NULL CHECK(file_size_bytes >= 0),
 checksum VARCHAR(128),
 document_version INTEGER NOT NULL DEFAULT 1,
 uploaded_by BIGINT REFERENCES users(id),
 description TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- attachment_links: Links stored files to business entities; targets validated in service layer.
CREATE TABLE attachment_links (
 id BIGSERIAL PRIMARY KEY,
 attachment_id BIGINT NOT NULL REFERENCES attachments(id),
 entity_type VARCHAR(64) NOT NULL,
 entity_id BIGINT NOT NULL,
 attachment_role VARCHAR(64) NOT NULL DEFAULT 'ATTACHMENT',
 is_primary BOOLEAN NOT NULL DEFAULT FALSE,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(attachment_id, entity_type, entity_id, attachment_role)
);

-- user_sessions: Optimized domain table retained for essential LCS workflow.
CREATE TABLE user_sessions (
 id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL REFERENCES users(id),
 refresh_token_hash VARCHAR(128) NOT NULL UNIQUE,
 expires_at TIMESTAMPTZ NOT NULL,
 revoked_at TIMESTAMPTZ,
 last_used_at TIMESTAMPTZ,
 ip_address VARCHAR(64),
 device_name VARCHAR(255),
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- backup_runs: Backup run monitoring only; the backup files live in external storage.
CREATE TABLE backup_runs (
 id BIGSERIAL PRIMARY KEY,
 triggered_by BIGINT REFERENCES users(id),
 provider VARCHAR(40) NOT NULL DEFAULT 'EXTERNAL',
 destination_reference VARCHAR(300),
 status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
 started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 finished_at TIMESTAMPTZ,
 tables_processed INTEGER NOT NULL DEFAULT 0,
 rows_processed BIGINT NOT NULL DEFAULT 0,
 detail JSONB NOT NULL DEFAULT '{}'::jsonb,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE quotations ADD CONSTRAINT fk_quotations_current_version FOREIGN KEY (current_version_id) REFERENCES quotation_versions(id);
ALTER TABLE service_orders ADD CONSTRAINT fk_service_orders_config_version FOREIGN KEY (configuration_version_id) REFERENCES configuration_versions(id);
ALTER TABLE component_tabs ADD CONSTRAINT fk_component_tabs_config_version FOREIGN KEY (config_version_id) REFERENCES configuration_versions(id);
ALTER TABLE service_order_component_rows ADD CONSTRAINT fk_so_rows_config_version FOREIGN KEY (config_version_id) REFERENCES configuration_versions(id);
ALTER TABLE financial_accounts ADD CONSTRAINT fk_financial_accounts_ledger FOREIGN KEY (ledger_account_id) REFERENCES chart_of_accounts(id);


-- Operational indexes (PostgreSQL reference only)
CREATE INDEX idx_so_customer_date ON service_orders(customer_id, service_date);
CREATE INDEX idx_so_trade_status ON service_orders(trade_direction_id, status);
CREATE INDEX idx_movements_order ON service_order_movements(service_order_id, sequence_no);
CREATE INDEX idx_milestones_order ON service_order_milestones(service_order_id, sequence_no);
CREATE INDEX idx_charges_order ON service_order_charges(service_order_id);
CREATE INDEX idx_payments_party_date ON payments(party_id, payment_date);
CREATE INDEX idx_allocations_document ON payment_allocations(financial_document_id);
CREATE INDEX idx_fin_docs_party_status ON financial_documents(party_id, status);
CREATE INDEX idx_journal_lines_account ON journal_entry_lines(account_id);
CREATE INDEX idx_audit_entity_time ON audit_events(entity_type, entity_id, occurred_at DESC);
CREATE INDEX idx_audit_actor_time ON audit_events(actor_user_id, occurred_at DESC);
CREATE INDEX idx_component_rows_order ON service_order_component_rows(service_order_id, group_id);
CREATE INDEX idx_tabs_direction ON component_tabs(trade_direction_id, display_order);
CREATE INDEX idx_quotation_version_lookup ON quotation_versions(quotation_id, version_no DESC);
CREATE INDEX idx_quotation_lines_version ON quotation_lines(quotation_version_id, sort_order);
CREATE UNIQUE INDEX uq_posting_rules_fee ON posting_rules(document_type,fee_type_id) WHERE fee_type_id IS NOT NULL AND is_active;
CREATE UNIQUE INDEX uq_posting_rules_default ON posting_rules(document_type) WHERE fee_type_id IS NULL AND is_active;
CREATE UNIQUE INDEX uq_configuration_version_published ON configuration_versions(status) WHERE status='PUBLISHED';


-- New currency conversion records, with effective-date history and explicit rate direction.
CREATE TABLE currency_rates (
 id BIGSERIAL PRIMARY KEY,
 from_currency_id BIGINT NOT NULL REFERENCES currencies(id),
 to_currency_id BIGINT NOT NULL REFERENCES currencies(id),
 effective_date DATE NOT NULL,
 rate NUMERIC(19,8) NOT NULL CHECK(rate > 0),
 source VARCHAR(80), description TEXT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_currency_rate UNIQUE(from_currency_id,to_currency_id,effective_date),
 CONSTRAINT ck_currency_rate_pair CHECK(from_currency_id <> to_currency_id)
);
COMMENT ON TABLE currency_rates IS 'Historical FX conversion rates for reporting; finance postings must snapshot their actual applied exchange rate.';
-- Incremental backup state: tracks the last backed-up hash for each row.
CREATE TABLE backup_states (
 id BIGSERIAL PRIMARY KEY,
 table_name VARCHAR(128) NOT NULL,
 record_id VARCHAR(255) NOT NULL,
 last_hash VARCHAR(128) NOT NULL,
 last_backup_version BIGINT NOT NULL CHECK(last_backup_version > 0),
 last_backup_at TIMESTAMPTZ NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_backup_state UNIQUE(table_name,record_id)
);
-- Backup snapshots, not a replacement for encrypted offsite PostgreSQL base + WAL backup.
CREATE TABLE backup_records (
 id BIGSERIAL PRIMARY KEY,
 backup_run_id BIGINT REFERENCES backup_runs(id),
 table_name VARCHAR(128) NOT NULL,
 record_id VARCHAR(255) NOT NULL,
 backup_version BIGINT NOT NULL CHECK(backup_version > 0),
 change_kind VARCHAR(16) NOT NULL CHECK(change_kind IN ('INSERT','UPDATE','DELETE')),
 row_hash VARCHAR(128) NOT NULL,
 payload JSONB NOT NULL,
 backed_up_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(table_name,record_id,backup_version)
);
CREATE INDEX idx_backup_records_lookup ON backup_records(table_name,record_id,backup_version DESC);

-- Additional domain constraints for newly-created databases. Adjust only after reviewing business rules.
ALTER TABLE quotation_lines ADD CONSTRAINT ck_quotation_line_amount_match CHECK (amount = ROUND(quantity * unit_price,4));
ALTER TABLE service_order_charges ADD CONSTRAINT ck_so_charge_type CHECK (charge_type IN ('REVENUE','COST'));
ALTER TABLE service_order_charges ADD CONSTRAINT ck_so_charge_qty CHECK(quantity > 0 AND unit_price >= 0 AND amount >= 0);
ALTER TABLE service_order_charges ADD CONSTRAINT ck_so_charge_amount_match CHECK(amount = ROUND(quantity * unit_price,4));
ALTER TABLE financial_document_lines ADD CONSTRAINT ck_fin_doc_line_positive CHECK(quantity > 0 AND unit_price >= 0 AND amount >= 0);
ALTER TABLE financial_documents ADD CONSTRAINT ck_fin_doc_total_nonnegative CHECK(total_amount >= 0);
ALTER TABLE payments ADD CONSTRAINT ck_payment_positive CHECK(amount > 0);
ALTER TABLE payment_allocations ADD CONSTRAINT ck_allocation_positive CHECK(allocated_amount > 0);
ALTER TABLE journal_entry_lines ADD CONSTRAINT ck_journal_line_nonnegative CHECK(debit >= 0 AND credit >= 0);
ALTER TABLE journal_entry_lines ADD CONSTRAINT ck_journal_line_one_side CHECK((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0));
ALTER TABLE accounting_periods ADD CONSTRAINT ck_period_dates CHECK(start_date <= end_date);
CREATE INDEX idx_fx_date ON currency_rates(from_currency_id,to_currency_id,effective_date DESC);
CREATE INDEX idx_fin_docs_due_date ON financial_documents(due_date) WHERE is_active;
CREATE INDEX idx_journal_entries_date_status ON journal_entries(entry_date,status);
CREATE INDEX idx_payments_status_date ON payments(status,payment_date);

-- Service order must use an APPROVED quotation belonging to the same customer/direction.
CREATE OR REPLACE FUNCTION fn_check_so_quotation_version() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE q_customer BIGINT; q_trade BIGINT; q_status VARCHAR(30);
BEGIN
 IF NEW.quotation_version_id IS NULL THEN RETURN NEW; END IF;
 SELECT q.customer_id, v.trade_direction_id, v.status
 INTO q_customer,q_trade,q_status FROM quotation_versions v JOIN quotations q ON q.id=v.quotation_id
 WHERE v.id=NEW.quotation_version_id;
 IF q_customer IS DISTINCT FROM NEW.customer_id OR q_trade IS DISTINCT FROM NEW.trade_direction_id OR q_status <> 'APPROVED' THEN
  RAISE EXCEPTION 'Service order requires approved quotation version for matching customer and trade direction';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trg_so_quote_validate BEFORE INSERT OR UPDATE OF quotation_version_id,customer_id,trade_direction_id ON service_orders
 FOR EACH ROW EXECUTE FUNCTION fn_check_so_quotation_version();

-- Prevent changing or removing the contents of a quotation after it leaves DRAFT.
CREATE OR REPLACE FUNCTION fn_guard_quotation_line() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_id BIGINT; v_status TEXT;
BEGIN
 v_id := CASE WHEN TG_OP='DELETE' THEN OLD.quotation_version_id ELSE NEW.quotation_version_id END;
 SELECT status INTO v_status FROM quotation_versions WHERE id=v_id FOR UPDATE;
 IF v_status IS NULL OR v_status <> 'DRAFT' THEN RAISE EXCEPTION 'Quotation lines can only change for a DRAFT version'; END IF;
 IF TG_OP='UPDATE' AND NEW.quotation_version_id<>OLD.quotation_version_id THEN
  RAISE EXCEPTION 'Moving lines between versions is not supported';
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER trg_quote_line_guard BEFORE INSERT OR UPDATE OR DELETE ON quotation_lines
 FOR EACH ROW EXECUTE FUNCTION fn_guard_quotation_line();

CREATE OR REPLACE FUNCTION fn_guard_quotation_version() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Quotation versions must not be deleted'; END IF;
 IF OLD.status <> 'DRAFT' THEN
  IF NEW.quotation_id IS DISTINCT FROM OLD.quotation_id OR NEW.version_no IS DISTINCT FROM OLD.version_no
  OR NEW.currency_id IS DISTINCT FROM OLD.currency_id OR NEW.trade_direction_id IS DISTINCT FROM OLD.trade_direction_id
  OR NEW.origin_place_id IS DISTINCT FROM OLD.origin_place_id OR NEW.destination_place_id IS DISTINCT FROM OLD.destination_place_id
  OR NEW.quotation_date IS DISTINCT FROM OLD.quotation_date OR NEW.valid_until IS DISTINCT FROM OLD.valid_until
  OR NEW.notes IS DISTINCT FROM OLD.notes OR NEW.change_note IS DISTINCT FROM OLD.change_note OR NEW.is_active IS DISTINCT FROM OLD.is_active THEN
   RAISE EXCEPTION 'Submitted or approved quotation content is immutable';
  END IF;
 END IF;
 IF OLD.status='APPROVED' AND NEW.status NOT IN ('APPROVED','SUPERSEDED') THEN
  RAISE EXCEPTION 'Approved quotation can only become SUPERSEDED';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trg_quotation_version_guard BEFORE UPDATE OR DELETE ON quotation_versions
 FOR EACH ROW EXECUTE FUNCTION fn_guard_quotation_version();

-- Generic immutable posted-journal protection, including is_active toggles.
CREATE OR REPLACE FUNCTION fn_guard_journal_entry() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' AND OLD.status='POSTED' THEN RAISE EXCEPTION 'Posted journal cannot be deleted'; END IF;
 IF TG_OP='UPDATE' AND OLD.status='POSTED' THEN
  IF NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'Posted journal is immutable; reverse instead'; END IF;
 END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER trg_journal_guard BEFORE UPDATE OR DELETE ON journal_entries
 FOR EACH ROW EXECUTE FUNCTION fn_guard_journal_entry();

CREATE OR REPLACE FUNCTION fn_guard_journal_line() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE j_status TEXT; j_id BIGINT;
BEGIN
 j_id:=CASE WHEN TG_OP='DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;
 SELECT status INTO j_status FROM journal_entries WHERE id=j_id FOR UPDATE;
 IF j_status IS NULL OR j_status='POSTED' THEN RAISE EXCEPTION 'Cannot change lines of posted/missing journal'; END IF;
 IF TG_OP='UPDATE' AND NEW.journal_entry_id<>OLD.journal_entry_id THEN RAISE EXCEPTION 'Cannot move journal lines'; END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER trg_journal_line_guard BEFORE INSERT OR UPDATE OR DELETE ON journal_entry_lines
 FOR EACH ROW EXECUTE FUNCTION fn_guard_journal_line();

-- On posting, verify balanced journal, posting period is open and entry date lies inside it.
CREATE OR REPLACE FUNCTION fn_validate_journal_post() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE deb NUMERIC(19,4); cred NUMERIC(19,4); cnt INTEGER; pstart DATE; pend DATE; pstatus TEXT;
BEGIN
 IF NEW.status='POSTED' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM 'POSTED') THEN
  SELECT start_date,end_date,status INTO pstart,pend,pstatus FROM accounting_periods WHERE id=NEW.period_id FOR UPDATE;
  IF pstatus IS DISTINCT FROM 'OPEN' OR NEW.entry_date NOT BETWEEN pstart AND pend THEN
   RAISE EXCEPTION 'Cannot post outside an open accounting period';
  END IF;
  SELECT COALESCE(SUM(debit),0),COALESCE(SUM(credit),0),COUNT(*) INTO deb,cred,cnt
  FROM journal_entry_lines WHERE journal_entry_id=NEW.id AND is_active;
  IF cnt<2 OR deb<=0 OR deb<>cred THEN RAISE EXCEPTION 'Journal must contain balanced debit and credit lines'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trg_journal_post_check BEFORE UPDATE OF status ON journal_entries
 FOR EACH ROW EXECUTE FUNCTION fn_validate_journal_post();
-- A journal must first be created DRAFT with lines, then changed to POSTED.
ALTER TABLE journal_entries ADD CONSTRAINT ck_journal_initial_status CHECK(status IN ('DRAFT','POSTED','REVERSED'));

-- Payment allocation guard serializes allocation changes per payment + invoice.
-- This simple 1:1 currency policy is deliberate; implement explicit FX allocation conversion to support cross-currency settlements.
CREATE OR REPLACE FUNCTION fn_guard_payment_allocation() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE p_amt NUMERIC(19,4); d_amt NUMERIC(19,4); p_cur BIGINT; d_cur BIGINT;
DECLARE p_party BIGINT; d_party BIGINT; p_status TEXT; d_status TEXT;
DECLARE p_used NUMERIC(19,4); d_used NUMERIC(19,4); old_id BIGINT;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Do not delete allocations; use controlled reversal'; END IF;
 IF TG_OP='UPDATE' THEN RAISE EXCEPTION 'Allocations are immutable; use a reversing record/workflow'; END IF;
 SELECT amount,currency_id,party_id,status INTO p_amt,p_cur,p_party,p_status FROM payments WHERE id=NEW.payment_id FOR UPDATE;
 SELECT total_amount,currency_id,party_id,status INTO d_amt,d_cur,d_party,d_status FROM financial_documents WHERE id=NEW.financial_document_id FOR UPDATE;
 IF p_cur IS DISTINCT FROM d_cur OR p_party IS DISTINCT FROM d_party THEN RAISE EXCEPTION 'Payment and invoice must match currency and party'; END IF;
 IF p_status NOT IN ('POSTED','CONFIRMED','COMPLETED') OR d_status IN ('DRAFT','CANCELLED','REVERSED') THEN RAISE EXCEPTION 'Payment and invoice must be eligible for allocation'; END IF;
 SELECT COALESCE(SUM(allocated_amount),0) INTO p_used FROM payment_allocations WHERE payment_id=NEW.payment_id AND is_active;
 SELECT COALESCE(SUM(allocated_amount),0) INTO d_used FROM payment_allocations WHERE financial_document_id=NEW.financial_document_id AND is_active;
 IF p_used+NEW.allocated_amount>p_amt OR d_used+NEW.allocated_amount>d_amt THEN RAISE EXCEPTION 'Allocation exceeds remaining payment or invoice balance'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trg_payment_allocation_guard BEFORE INSERT OR UPDATE OR DELETE ON payment_allocations
 FOR EACH ROW EXECUTE FUNCTION fn_guard_payment_allocation();

-- A minimal safe, append-only audit trail. DB owner/superuser can override; use restricted DB roles.
CREATE OR REPLACE FUNCTION fn_audit_append_only() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Audit events are append-only'; END $$;
CREATE TRIGGER trg_audit_append_only BEFORE UPDATE OR DELETE ON audit_events
 FOR EACH ROW EXECUTE FUNCTION fn_audit_append_only();

-- Reporting starter views: same-currency only for job-margin; FX not silently mixed.
CREATE VIEW vw_quotation_version_history AS
SELECT q.id quotation_id,q.quotation_no,v.id quotation_version_id,v.version_no,v.status,
       v.quotation_date,v.valid_until, c.code currency_code,
       COALESCE(SUM(CASE WHEN l.is_active THEN l.amount ELSE 0 END),0) amount
FROM quotations q JOIN quotation_versions v ON v.quotation_id=q.id
JOIN currencies c ON c.id=v.currency_id LEFT JOIN quotation_lines l ON l.quotation_version_id=v.id
GROUP BY q.id,q.quotation_no,v.id,v.version_no,v.status,v.quotation_date,v.valid_until,c.code;

CREATE VIEW vw_invoice_outstanding AS
SELECT d.id financial_document_id,d.document_no,d.party_id,d.currency_id,d.due_date,d.total_amount,
 COALESCE(a.allocated,0) paid_amount,
 d.total_amount-COALESCE(a.allocated,0) outstanding_amount
FROM financial_documents d
LEFT JOIN (SELECT financial_document_id,SUM(allocated_amount) allocated FROM payment_allocations
           WHERE is_active GROUP BY financial_document_id) a ON a.financial_document_id=d.id
WHERE d.document_type IN ('INVOICE','TAX_INVOICE') AND d.status NOT IN ('DRAFT','CANCELLED','REVERSED') AND d.is_active;

CREATE VIEW vw_trial_balance AS
SELECT l.account_id,a.account_code,a.account_name,
 SUM(l.debit) total_debit,SUM(l.credit) total_credit,SUM(l.debit-l.credit) net_debit_balance
FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id
JOIN chart_of_accounts a ON a.id=l.account_id
WHERE j.status='POSTED' AND j.is_active AND l.is_active
GROUP BY l.account_id,a.account_code,a.account_name;

CREATE VIEW vw_general_ledger AS
SELECT j.id journal_entry_id,j.journal_no,j.entry_date,l.id journal_line_id,
 l.account_id,a.account_code,a.account_name,l.debit,l.credit,l.description
FROM journal_entries j JOIN journal_entry_lines l ON l.journal_entry_id=j.id
JOIN chart_of_accounts a ON a.id=l.account_id
WHERE j.status='POSTED' AND j.is_active AND l.is_active;

CREATE VIEW vw_service_order_charge_summary AS
SELECT so.id service_order_id,so.service_order_no,c.currency_id,
 SUM(CASE WHEN c.charge_type='REVENUE' THEN c.amount ELSE 0 END) revenue_amount,
 SUM(CASE WHEN c.charge_type='COST' THEN c.amount ELSE 0 END) cost_amount,
 SUM(CASE WHEN c.charge_type='REVENUE' THEN c.amount ELSE -c.amount END) indicative_margin
FROM service_orders so JOIN service_order_charges c ON c.service_order_id=so.id AND c.is_active
GROUP BY so.id,so.service_order_no,c.currency_id;
COMMENT ON VIEW vw_service_order_charge_summary IS 'Indicative gross margin by service order AND currency; do not sum amounts across different currencies without FX normalization.';

CREATE VIEW vw_service_order_status AS
SELECT so.id,so.service_order_no,so.customer_id,so.trade_direction_id,so.status,so.service_date,
 COUNT(DISTINCT sc.id) AS container_count,COUNT(DISTINCT m.id) AS movement_count
FROM service_orders so
LEFT JOIN service_order_containers sc ON sc.service_order_id=so.id AND sc.is_active
LEFT JOIN service_order_movements m ON m.service_order_id=so.id AND m.is_active
WHERE so.is_active GROUP BY so.id,so.service_order_no,so.customer_id,so.trade_direction_id,so.status,so.service_date;

-- Timestamp management: all regular timestamped tables get updated_at refreshed on UPDATE.
CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at=CURRENT_TIMESTAMP; RETURN NEW; END $$;
DO $$ DECLARE rec RECORD; BEGIN
 FOR rec IN SELECT table_name FROM information_schema.columns
 WHERE table_schema='public' AND column_name='updated_at' AND table_name IN
 (SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE')
 LOOP
  EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',
                 'trg_touch_'||rec.table_name,rec.table_name);
 END LOOP;
END $$;

-- Additional details to complete in FastAPI and Alembic:
-- - Quotation version creation: SELECT FOR UPDATE on quotation header, copy lines, recompute totals.
-- - Only approved versions convert to orders; prevent later version changes from rewriting orders.
-- - JSONB dynamic fields: enforce type/required/lookup rules in backend, snapshot published config.
-- - Accounting: multi-currency/base-currency journal lines, exchange gain/loss, tax and reversals.
-- - Permissions and tenant policies, retry-safe posting and payment API, role management.
-- - Restore-tested encrypted offsite backups; these backup tables alone are NOT a backup strategy.
-- - The starter views are NOT a substitute for completed financial statement definitions.
