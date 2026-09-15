-- Freight Forwarding, Service Operations, and Double-Entry Finance
-- Consolidated PostgreSQL baseline schema.
-- This file supersedes 06_database_design.sql and the platform-core addendum.
-- It is intended as a clean baseline migration, not an online migration of an existing database.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. Shared types
-- ============================================================

CREATE TYPE record_status AS ENUM ('ACTIVE', 'INACTIVE');
CREATE TYPE user_status AS ENUM ('INVITED', 'ACTIVE', 'SUSPENDED', 'LOCKED', 'DISABLED');
CREATE TYPE quotation_status AS ENUM ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'SUPERSEDED', 'CONVERTED', 'CANCELLED');
CREATE TYPE service_order_status AS ENUM ('DRAFT', 'OPEN', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED', 'CLOSED');
CREATE TYPE component_status AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
CREATE TYPE financial_document_status AS ENUM ('DRAFT', 'POSTED', 'CANCELLED', 'REVERSED');
CREATE TYPE journal_status AS ENUM ('DRAFT', 'POSTED', 'REVERSED', 'VOIDED');
CREATE TYPE accounting_period_status AS ENUM ('OPEN', 'CLOSED', 'REOPENED');
CREATE TYPE account_type AS ENUM ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE');
CREATE TYPE normal_balance AS ENUM ('DEBIT', 'CREDIT');

-- ============================================================
-- 2. Organization and branch
-- ============================================================

CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    organization_code TEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    display_name TEXT,
    vat_tin TEXT,
    country_code CHAR(2),
    default_currency_code CHAR(3) NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE places (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    place_category TEXT NOT NULL,
    parent_place_id BIGINT REFERENCES places(id),
    address TEXT,
    country_code CHAR(2),
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE branches (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_code TEXT NOT NULL,
    name TEXT NOT NULL,
    place_id BIGINT REFERENCES places(id),
    phone TEXT,
    email TEXT,
    address TEXT,
    is_head_office BOOLEAN NOT NULL DEFAULT false,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, branch_code),
    UNIQUE (organization_id, id)
);

-- ============================================================
-- 3. Identity and authorization
-- ============================================================

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    user_code TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    phone TEXT,
    status user_status NOT NULL DEFAULT 'INVITED',
    locale TEXT NOT NULL DEFAULT 'en',
    timezone TEXT NOT NULL DEFAULT 'UTC',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_credentials (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    password_algorithm TEXT NOT NULL DEFAULT 'argon2id',
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    failed_attempt_count INT NOT NULL DEFAULT 0 CHECK (failed_attempt_count >= 0),
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT NOT NULL UNIQUE,
    device_name TEXT,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    is_system_role BOOLEAN NOT NULL DEFAULT false,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE permissions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    UNIQUE (resource, action)
);

CREATE TABLE role_permissions (
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_role_assignments (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id),
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    assigned_by_user_id BIGINT REFERENCES users(id),
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id),
    CHECK (expires_at IS NULL OR expires_at > starts_at)
);

CREATE TABLE user_branch_assignments (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT false,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, organization_id, branch_id),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id),
    CHECK (expires_at IS NULL OR expires_at > starts_at)
);

-- ============================================================
-- 4. Business master data
-- ============================================================

CREATE TABLE trade_directions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE container_types (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    container_size TEXT,
    container_kind TEXT,
    iso_code TEXT,
    length_feet NUMERIC(5, 2),
    width_millimeter NUMERIC(8, 2),
    height_millimeter NUMERIC(8, 2),
    max_gross_weight_kg NUMERIC(12, 3),
    description TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transport_types (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fee_types (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE business_parties (
    id BIGSERIAL PRIMARY KEY,
    party_code TEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    display_name TEXT,
    vat_tin TEXT UNIQUE,
    contact_person TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    country_code CHAR(2),
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE party_roles (
    party_id BIGINT NOT NULL REFERENCES business_parties(id) ON DELETE CASCADE,
    role_type TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (party_id, role_type)
);

CREATE TABLE party_places (
    party_id BIGINT NOT NULL REFERENCES business_parties(id) ON DELETE CASCADE,
    place_id BIGINT NOT NULL REFERENCES places(id),
    relationship_type TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (party_id, place_id, relationship_type)
);

CREATE TABLE transport_assets (
    id BIGSERIAL PRIMARY KEY,
    asset_code TEXT NOT NULL UNIQUE,
    transport_type_id BIGINT NOT NULL REFERENCES transport_types(id),
    identity TEXT NOT NULL,
    identity_type TEXT NOT NULL,
    registration_country_code CHAR(2),
    owner_party_id BIGINT REFERENCES business_parties(id),
    operator_party_id BIGINT REFERENCES business_parties(id),
    description TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transport_type_id, identity)
);

CREATE TABLE customer_customs_accounts (
    id BIGSERIAL PRIMARY KEY,
    party_id BIGINT NOT NULL REFERENCES business_parties(id) ON DELETE CASCADE,
    system_name TEXT NOT NULL,
    username TEXT NOT NULL,
    password_secret_reference TEXT,
    encrypted_password BYTEA,
    last_verified_at TIMESTAMPTZ,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (password_secret_reference IS NOT NULL OR encrypted_password IS NOT NULL)
);

-- ============================================================
-- 5. Dynamic component configuration
-- ============================================================

CREATE TABLE component_groups (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    display_order INT NOT NULL DEFAULT 0,
    status record_status NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE component_templates (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    version INT NOT NULL DEFAULT 1 CHECK (version > 0),
    status record_status NOT NULL DEFAULT 'ACTIVE',
    UNIQUE (code, version),
    UNIQUE (id, version)
);

CREATE TABLE template_attributes (
    id BIGSERIAL PRIMARY KEY,
    template_id BIGINT NOT NULL REFERENCES component_templates(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    data_type TEXT NOT NULL,
    input_type TEXT,
    is_required BOOLEAN NOT NULL DEFAULT false,
    is_repeatable BOOLEAN NOT NULL DEFAULT false,
    display_order INT NOT NULL DEFAULT 0,
    validation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    reference_type TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    UNIQUE (template_id, code),
    UNIQUE (id, template_id)
);

CREATE TABLE trade_direction_components (
    id BIGSERIAL PRIMARY KEY,
    trade_direction_id BIGINT NOT NULL REFERENCES trade_directions(id),
    component_group_id BIGINT NOT NULL REFERENCES component_groups(id),
    component_template_id BIGINT NOT NULL REFERENCES component_templates(id),
    display_order INT NOT NULL DEFAULT 0,
    is_required BOOLEAN NOT NULL DEFAULT false,
    is_repeatable BOOLEAN NOT NULL DEFAULT false,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    UNIQUE (trade_direction_id, component_template_id)
);

-- ============================================================
-- 6. Quotations and revisions
-- ============================================================

CREATE TABLE quotations (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT NOT NULL,
    quotation_no TEXT NOT NULL,
    customer_party_id BIGINT NOT NULL REFERENCES business_parties(id),
    trade_direction_id BIGINT NOT NULL REFERENCES trade_directions(id),
    current_revision_no INT NOT NULL DEFAULT 1 CHECK (current_revision_no > 0),
    status quotation_status NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, quotation_no),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

CREATE TABLE quotation_revisions (
    id BIGSERIAL PRIMARY KEY,
    quotation_id BIGINT NOT NULL REFERENCES quotations(id) ON DELETE CASCADE,
    revision_no INT NOT NULL CHECK (revision_no > 0),
    status quotation_status NOT NULL DEFAULT 'DRAFT',
    quotation_date DATE NOT NULL,
    valid_until DATE,
    currency_code CHAR(3) NOT NULL,
    description TEXT,
    notes TEXT,
    subtotal_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (subtotal_amount >= 0),
    discount_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    UNIQUE (quotation_id, revision_no)
);

CREATE TABLE quotation_revision_places (
    id BIGSERIAL PRIMARY KEY,
    quotation_revision_id BIGINT NOT NULL REFERENCES quotation_revisions(id) ON DELETE CASCADE,
    place_id BIGINT REFERENCES places(id),
    place_role TEXT NOT NULL,
    sequence_no INT NOT NULL DEFAULT 1 CHECK (sequence_no > 0),
    free_text TEXT,
    notes TEXT,
    CHECK (place_id IS NOT NULL OR NULLIF(btrim(free_text), '') IS NOT NULL)
);

CREATE TABLE quotation_revision_containers (
    id BIGSERIAL PRIMARY KEY,
    quotation_revision_id BIGINT NOT NULL REFERENCES quotation_revisions(id) ON DELETE CASCADE,
    container_type_id BIGINT NOT NULL REFERENCES container_types(id),
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    description TEXT
);

CREATE TABLE quotation_revision_lines (
    id BIGSERIAL PRIMARY KEY,
    quotation_revision_id BIGINT NOT NULL REFERENCES quotation_revisions(id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    fee_type_id BIGINT REFERENCES fee_types(id),
    container_requirement_id BIGINT REFERENCES quotation_revision_containers(id),
    service_description TEXT NOT NULL,
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    unit_code TEXT,
    unit_price NUMERIC(19, 4) NOT NULL CHECK (unit_price >= 0),
    discount_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (discount_rate BETWEEN 0 AND 100),
    tax_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 100),
    line_subtotal NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_subtotal >= 0),
    line_discount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_discount >= 0),
    line_tax NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_tax >= 0),
    line_total NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_total >= 0),
    UNIQUE (quotation_revision_id, line_no)
);

CREATE TABLE quotation_conversions (
    id BIGSERIAL PRIMARY KEY,
    quotation_revision_id BIGINT NOT NULL UNIQUE REFERENCES quotation_revisions(id),
    service_order_id BIGINT NOT NULL UNIQUE,
    converted_by_user_id BIGINT NOT NULL REFERENCES users(id),
    converted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

-- ============================================================
-- 7. Service orders and operations
-- ============================================================

CREATE TABLE service_orders (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT NOT NULL,
    service_order_no TEXT NOT NULL,
    quotation_revision_id BIGINT REFERENCES quotation_revisions(id),
    customer_party_id BIGINT NOT NULL REFERENCES business_parties(id),
    trade_direction_id BIGINT NOT NULL REFERENCES trade_directions(id),
    status service_order_status NOT NULL DEFAULT 'DRAFT',
    currency_code CHAR(3) NOT NULL,
    description TEXT,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, service_order_no),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

ALTER TABLE quotation_conversions
    ADD CONSTRAINT quotation_conversions_order_fk
    FOREIGN KEY (service_order_id) REFERENCES service_orders(id);

CREATE TABLE service_order_places (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    place_id BIGINT REFERENCES places(id),
    place_role TEXT NOT NULL,
    sequence_no INT NOT NULL DEFAULT 1 CHECK (sequence_no > 0),
    free_text TEXT,
    is_actual BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    CHECK (place_id IS NOT NULL OR NULLIF(btrim(free_text), '') IS NOT NULL)
);

CREATE TABLE service_order_container_requirements (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    source_quotation_container_id BIGINT REFERENCES quotation_revision_containers(id),
    container_type_id BIGINT NOT NULL REFERENCES container_types(id),
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    description TEXT
);

CREATE TABLE service_order_containers (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    container_requirement_id BIGINT REFERENCES service_order_container_requirements(id),
    container_type_id BIGINT NOT NULL REFERENCES container_types(id),
    container_number TEXT NOT NULL,
    seal_serial TEXT,
    status TEXT NOT NULL DEFAULT 'EXPECTED',
    net_weight_kg NUMERIC(12, 3),
    gross_weight_kg NUMERIC(12, 3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (container_number),
    CHECK (gross_weight_kg IS NULL OR net_weight_kg IS NULL OR gross_weight_kg >= net_weight_kg)
);

CREATE TABLE service_order_pricing (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL UNIQUE REFERENCES service_orders(id) ON DELETE CASCADE,
    subtotal_amount NUMERIC(19, 4) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(19, 4) NOT NULL DEFAULT 0,
    tax_amount NUMERIC(19, 4) NOT NULL DEFAULT 0,
    total_amount NUMERIC(19, 4) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE service_order_pricing_lines (
    id BIGSERIAL PRIMARY KEY,
    service_order_pricing_id BIGINT NOT NULL REFERENCES service_order_pricing(id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    source_quotation_line_id BIGINT REFERENCES quotation_revision_lines(id),
    fee_type_id BIGINT REFERENCES fee_types(id),
    description TEXT NOT NULL,
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    unit_code TEXT,
    unit_price NUMERIC(19, 4) NOT NULL CHECK (unit_price >= 0),
    discount_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (discount_rate BETWEEN 0 AND 100),
    tax_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 100),
    line_total NUMERIC(19, 4) NOT NULL DEFAULT 0,
    UNIQUE (service_order_pricing_id, line_no)
);

CREATE TABLE service_order_components (
    id BIGSERIAL PRIMARY KEY,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    trade_direction_component_id BIGINT NOT NULL REFERENCES trade_direction_components(id),
    component_group_id BIGINT NOT NULL REFERENCES component_groups(id),
    component_template_id BIGINT NOT NULL REFERENCES component_templates(id),
    template_version INT NOT NULL,
    component_status component_status NOT NULL DEFAULT 'PENDING',
    sequence_no INT NOT NULL DEFAULT 1 CHECK (sequence_no > 0),
    is_required BOOLEAN NOT NULL DEFAULT false,
    occurred_at TIMESTAMPTZ,
    created_by_user_id BIGINT REFERENCES users(id),
    completed_by_user_id BIGINT REFERENCES users(id),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE service_component_values (
    id BIGSERIAL PRIMARY KEY,
    component_id BIGINT NOT NULL REFERENCES service_order_components(id) ON DELETE CASCADE,
    template_attribute_id BIGINT NOT NULL REFERENCES template_attributes(id),
    value_text TEXT,
    value_number NUMERIC(19, 6),
    value_date DATE,
    value_datetime TIMESTAMPTZ,
    value_boolean BOOLEAN,
    value_reference_type TEXT,
    value_reference_id BIGINT,
    value_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (component_id, template_attribute_id),
    CHECK (num_nonnulls(value_text, value_number, value_date, value_datetime, value_boolean, value_reference_id, value_json) <= 1)
);

-- ============================================================
-- 8. Informational service-order charges
-- ============================================================

CREATE TABLE service_order_charges (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT NOT NULL,
    service_order_id BIGINT NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    charge_no TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'SERVICE_NOTE',
    document_date DATE NOT NULL,
    currency_code CHAR(3) NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    subtotal_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (subtotal_amount >= 0),
    discount_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    total_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    remark TEXT,
    created_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, charge_no),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

CREATE TABLE service_order_charge_lines (
    id BIGSERIAL PRIMARY KEY,
    service_order_charge_id BIGINT NOT NULL REFERENCES service_order_charges(id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    fee_type_id BIGINT REFERENCES fee_types(id),
    service_order_container_id BIGINT REFERENCES service_order_containers(id),
    description TEXT NOT NULL,
    quantity NUMERIC(12, 3) NOT NULL CHECK (quantity > 0),
    unit_code TEXT,
    unit_price NUMERIC(19, 4) NOT NULL CHECK (unit_price >= 0),
    discount_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 100),
    tax_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    line_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_amount >= 0),
    UNIQUE (service_order_charge_id, line_no)
);

-- ============================================================
-- 9. Accounting and finance
-- ============================================================

CREATE TABLE chart_of_accounts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    account_code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type account_type NOT NULL,
    parent_account_id BIGINT REFERENCES chart_of_accounts(id),
    normal_balance normal_balance NOT NULL,
    is_postable BOOLEAN NOT NULL DEFAULT true,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, account_code),
    UNIQUE (organization_id, id)
);

CREATE TABLE financial_accounts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    account_id BIGINT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    currency_code CHAR(3) NOT NULL,
    bank_name TEXT,
    account_number_masked TEXT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, account_id),
    FOREIGN KEY (organization_id, account_id) REFERENCES chart_of_accounts(organization_id, id)
);

CREATE TABLE accounting_periods (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    period_year INT NOT NULL,
    period_month INT NOT NULL CHECK (period_month BETWEEN 1 AND 12),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status accounting_period_status NOT NULL DEFAULT 'OPEN',
    closed_by_user_id BIGINT REFERENCES users(id),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, period_year, period_month),
    CHECK (end_date >= start_date)
);

CREATE TABLE document_sequences (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    document_type TEXT NOT NULL,
    period_year INT NOT NULL,
    prefix TEXT NOT NULL,
    last_value BIGINT NOT NULL DEFAULT 0 CHECK (last_value >= 0),
    padding_length INT NOT NULL DEFAULT 6 CHECK (padding_length > 0),
    status record_status NOT NULL DEFAULT 'ACTIVE',
    UNIQUE (organization_id, document_type, period_year)
);

CREATE TABLE financial_documents (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    document_no TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_date DATE NOT NULL,
    posting_date DATE,
    status financial_document_status NOT NULL DEFAULT 'DRAFT',
    party_id BIGINT REFERENCES business_parties(id),
    service_order_id BIGINT REFERENCES service_orders(id),
    currency_code CHAR(3) NOT NULL,
    exchange_rate NUMERIC(19, 8) NOT NULL DEFAULT 1 CHECK (exchange_rate > 0),
    description TEXT,
    reference_number TEXT,
    due_date DATE,
    payment_method_code TEXT,
    financial_account_id BIGINT,
    value_date DATE,
    total_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    created_by_user_id BIGINT REFERENCES users(id),
    posted_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    posted_at TIMESTAMPTZ,
    UNIQUE (organization_id, document_no),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id),
    FOREIGN KEY (organization_id, financial_account_id) REFERENCES financial_accounts(organization_id, id)
);

CREATE TABLE financial_document_lines (
    id BIGSERIAL PRIMARY KEY,
    financial_document_id BIGINT NOT NULL REFERENCES financial_documents(id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    description TEXT NOT NULL,
    fee_type_id BIGINT REFERENCES fee_types(id),
    quantity NUMERIC(12, 3) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_code TEXT,
    unit_price NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    discount_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    tax_rate NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (tax_rate BETWEEN 0 AND 100),
    tax_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
    line_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (line_amount >= 0),
    service_order_id BIGINT REFERENCES service_orders(id),
    service_order_container_id BIGINT REFERENCES service_order_containers(id),
    account_id BIGINT REFERENCES chart_of_accounts(id),
    UNIQUE (financial_document_id, line_no)
);

CREATE TABLE financial_document_sources (
    id BIGSERIAL PRIMARY KEY,
    financial_document_id BIGINT NOT NULL REFERENCES financial_documents(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id BIGINT NOT NULL,
    relationship_type TEXT NOT NULL DEFAULT 'GENERATED_FROM',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (financial_document_id, source_type, source_id, relationship_type)
);

CREATE TABLE financial_document_allocations (
    id BIGSERIAL PRIMARY KEY,
    payment_document_id BIGINT NOT NULL REFERENCES financial_documents(id),
    target_document_id BIGINT NOT NULL REFERENCES financial_documents(id),
    allocated_amount NUMERIC(19, 4) NOT NULL CHECK (allocated_amount > 0),
    allocated_currency_code CHAR(3) NOT NULL,
    exchange_rate NUMERIC(19, 8) NOT NULL DEFAULT 1 CHECK (exchange_rate > 0),
    allocated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_user_id BIGINT REFERENCES users(id),
    CHECK (payment_document_id <> target_document_id)
);

CREATE TABLE posting_rules (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    document_type TEXT NOT NULL,
    fee_type_id BIGINT REFERENCES fee_types(id),
    debit_account_id BIGINT NOT NULL,
    credit_account_id BIGINT NOT NULL,
    tax_account_id BIGINT,
    status record_status NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (organization_id, debit_account_id) REFERENCES chart_of_accounts(organization_id, id),
    FOREIGN KEY (organization_id, credit_account_id) REFERENCES chart_of_accounts(organization_id, id),
    FOREIGN KEY (organization_id, tax_account_id) REFERENCES chart_of_accounts(organization_id, id)
);

CREATE TABLE journal_entries (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    entry_no TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    entry_date DATE NOT NULL,
    posting_date DATE NOT NULL,
    accounting_period_id BIGINT NOT NULL REFERENCES accounting_periods(id),
    status journal_status NOT NULL DEFAULT 'DRAFT',
    description TEXT,
    source_document_id BIGINT REFERENCES financial_documents(id),
    reversal_of_journal_entry_id BIGINT REFERENCES journal_entries(id),
    created_by_user_id BIGINT REFERENCES users(id),
    posted_by_user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    posted_at TIMESTAMPTZ,
    UNIQUE (organization_id, entry_no),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

CREATE TABLE journal_entry_lines (
    id BIGSERIAL PRIMARY KEY,
    journal_entry_id BIGINT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    line_no INT NOT NULL CHECK (line_no > 0),
    account_id BIGINT NOT NULL REFERENCES chart_of_accounts(id),
    party_id BIGINT REFERENCES business_parties(id),
    service_order_id BIGINT REFERENCES service_orders(id),
    financial_document_id BIGINT REFERENCES financial_documents(id),
    branch_id BIGINT,
    description TEXT,
    debit_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (debit_amount >= 0),
    credit_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (credit_amount >= 0),
    currency_code CHAR(3) NOT NULL,
    exchange_rate NUMERIC(19, 8) NOT NULL DEFAULT 1 CHECK (exchange_rate > 0),
    base_debit_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (base_debit_amount >= 0),
    base_credit_amount NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (base_credit_amount >= 0),
    UNIQUE (journal_entry_id, line_no),
    CHECK (NOT (debit_amount > 0 AND credit_amount > 0)),
    CHECK (debit_amount > 0 OR credit_amount > 0)
);

CREATE TABLE financial_document_postings (
    id BIGSERIAL PRIMARY KEY,
    financial_document_id BIGINT NOT NULL REFERENCES financial_documents(id),
    journal_entry_id BIGINT NOT NULL REFERENCES journal_entries(id),
    posting_role TEXT NOT NULL DEFAULT 'ORIGINAL_POSTING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (financial_document_id, journal_entry_id)
);

-- ============================================================
-- 10. Files, notifications, settings, and audit
-- ============================================================

CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    file_name TEXT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    mime_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    checksum TEXT,
    storage_provider TEXT NOT NULL,
    document_version INT NOT NULL DEFAULT 1 CHECK (document_version > 0),
    uploaded_by_user_id BIGINT REFERENCES users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

CREATE TABLE attachment_links (
    id BIGSERIAL PRIMARY KEY,
    attachment_id BIGINT NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id BIGINT NOT NULL,
    attachment_role TEXT NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (attachment_id, entity_type, entity_id, attachment_role)
);

CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    entity_type TEXT,
    entity_id BIGINT,
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at TIMESTAMPTZ,
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

CREATE TABLE system_settings (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id),
    branch_id BIGINT,
    setting_key TEXT NOT NULL,
    setting_value_json JSONB NOT NULL,
    is_sensitive BOOLEAN NOT NULL DEFAULT false,
    updated_by_user_id BIGINT REFERENCES users(id),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id),
    UNIQUE (organization_id, branch_id, setting_key)
);

CREATE TABLE audit_events (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id),
    branch_id BIGINT,
    actor_user_id BIGINT REFERENCES users(id),
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id BIGINT NOT NULL,
    action TEXT NOT NULL,
    result TEXT NOT NULL,
    reason TEXT,
    request_id TEXT,
    correlation_id TEXT,
    ip_address INET,
    user_agent TEXT,
    before_json JSONB,
    after_json JSONB,
    metadata_json JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (organization_id, branch_id) REFERENCES branches(organization_id, id)
);

-- ============================================================
-- 11. Integrity and operational indexes
-- ============================================================

CREATE INDEX idx_branches_organization ON branches(organization_id);
CREATE INDEX idx_places_parent ON places(parent_place_id);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_sessions_user_active ON user_sessions(user_id, revoked_at, expires_at);
CREATE INDEX idx_assignments_user_org ON user_role_assignments(user_id, organization_id);
CREATE INDEX idx_assignments_org_branch ON user_role_assignments(organization_id, branch_id);
CREATE INDEX idx_user_branches_user_org ON user_branch_assignments(user_id, organization_id);
CREATE INDEX idx_quotations_scope_status ON quotations(organization_id, branch_id, status);
CREATE INDEX idx_orders_scope_status ON service_orders(organization_id, branch_id, status);
CREATE INDEX idx_order_components_status ON service_order_components(service_order_id, component_status);
CREATE INDEX idx_order_containers_number ON service_order_containers(container_number);
CREATE INDEX idx_charges_scope_status ON service_order_charges(organization_id, branch_id, status);
CREATE INDEX idx_financial_documents_scope_status ON financial_documents(organization_id, branch_id, status);
CREATE INDEX idx_financial_documents_party ON financial_documents(organization_id, party_id, document_date);
CREATE INDEX idx_allocations_payment ON financial_document_allocations(payment_document_id);
CREATE INDEX idx_allocations_target ON financial_document_allocations(target_document_id);
CREATE INDEX idx_journals_scope_status ON journal_entries(organization_id, branch_id, status);
CREATE INDEX idx_journal_lines_account ON journal_entry_lines(account_id);
CREATE INDEX idx_journal_lines_party ON journal_entry_lines(party_id);
CREATE INDEX idx_journal_lines_branch ON journal_entry_lines(branch_id);
CREATE INDEX idx_periods_scope_status ON accounting_periods(organization_id, status);
CREATE INDEX idx_audit_scope_time ON audit_events(organization_id, branch_id, occurred_at DESC);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);

-- The application/service layer must additionally enforce:
-- 1. Parent/child organization consistency for all cross-table references.
-- 2. Journal balance before changing journal status to POSTED.
-- 3. Accounting-period date containment and OPEN status before posting.
-- 4. Template attribute data-type correctness.
-- 5. Service-order charge lines referencing containers from the same order.
-- 6. Financial-document allocation type and currency rules.
-- 7. Immutable behavior for sent revisions and posted financial records.
