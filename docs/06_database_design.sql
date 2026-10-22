-- Freight Forwarding, Service Operations, and Double-Entry Finance
-- PostgreSQL schema reference.
--
-- GENERATED FILE - DO NOT EDIT BY HAND.
-- Regenerate from backend/ with:
--     cd backend && uv run python scripts/generate_schema_docs.py
-- Check that it is up to date (used by CI and tests/test_schema_docs.py) with:
--     cd backend && uv run python scripts/generate_schema_docs.py --check
--
-- DDL is compiled from the live SQLAlchemy models (the same import list as
-- backend/alembic/env.py) against the PostgreSQL dialect, so it always reflects
-- the current schema. Alembic remains the migration source of truth; this file is
-- documentation only. It is a reference schema, not an automatic production
-- migration: do not run it against an existing database.
--
-- Every table and column carries its meaning twice: once as an inline `--`
-- comment for readers of this file, and once as an executable `COMMENT ON`
-- statement. The latter means the descriptions live in the database and can be
-- read back with:
--
--     SELECT c.relname AS table_name, a.attname AS column_name,
--            col_description(c.oid, a.attnum) AS description
--     FROM pg_class c
--     JOIN pg_namespace n ON n.oid = c.relnamespace
--     JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
--     WHERE n.nspname = 'public'
--     ORDER BY c.relname, a.attnum;
--
-- Applying the file to an empty database creates the schema together with all
-- descriptions. Applying the COMMENT ON section to an existing database refreshes
-- the prose without touching data:
--
--     psql -d "$DATABASE_URL" -f docs/06_database_design.sql
--
-- ---------------------------------------------------------------------------
-- Conventions
-- ---------------------------------------------------------------------------
-- * Tables are emitted in foreign-key dependency order, so the file can be run
--   top to bottom without deferring constraints.
-- * There is no multi-tenancy. Organizations and branches were removed
--   (migration b7f1c2a9d4e0_remove_organization_and_branch); access is governed
--   by users, roles and permissions only.
-- * No SQL enum types. Status-like columns are plain VARCHAR so new values do not
--   require a migration; the permitted values are listed in each description.
-- * PKMixin supplies `id BIGSERIAL`; TimestampMixin supplies `created_at` and
--   `updated_at`. Because the mixins are applied last they appear after the
--   table's own columns below.
-- * SoftDeleteMixin (on master-data tables) supplies `deleted_at` and
--   `deleted_by_user_id`. A non-NULL `deleted_at` archives the row: it leaves
--   listings and uniqueness checks but stays in place so historic documents keep
--   resolving. This is why those tables use partial unique indexes
--   (`... _active`) instead of plain UNIQUE constraints.
-- * JSONB columns hold module-specific payloads for collections that are driven
--   by the frontend schema rather than dedicated relational columns.
-- * Money is NUMERIC(19,4) in the document currency. Exchange rates are
--   NUMERIC(19,8). Journal lines also carry base-currency amounts so the ledger
--   balances across currencies.
-- * All timestamps are `TIMESTAMP WITH TIME ZONE` and are stored in UTC.
-- * The database ships empty. First-run provisioning (`/auth/setup`) seeds only
--   the permission catalog, the built-in
--   Platform Administrator role, the current-year document sequences and the
--   default app info/config — no finance or business data.
--
-- ---------------------------------------------------------------------------
-- Known divergences from the migrations (verified against PostgreSQL 16)
-- ---------------------------------------------------------------------------
-- This file mirrors the SQLAlchemy models. Building a database from these
-- statements and building one with `alembic upgrade head` currently differ in
-- exactly two places, both pre-existing model/migration drift:
--
--   1. archive_records.snapshot_json — migration e3f4a5b6c7d8 created this with
--      sa.JSON(), so the migrated column is `json`. The model uses JSONType, which
--      is JSONB on PostgreSQL, so this file emits `jsonb`.
--   2. business_parties.roles — migration a5b6c7d8e9f0 added
--      server_default `'[]'::jsonb`. The model declares only a Python-side
--      `default=list`, so this file emits no server default.
--
-- Every other table, column, constraint and index is identical between the two.

-- --------------------------------------------------------------------------
-- Table: backup_states
-- Module: Google Sheets Backup  [app.modules.backup.models]
-- Latest known hash per row, letting the backup job skip unchanged rows
-- without reading the whole table.
-- --------------------------------------------------------------------------
CREATE TABLE backup_states (
    -- Source table the row belongs to. Indexed so the run can skip whole
    -- tables.
    table_name VARCHAR(128) NOT NULL,
    -- Primary key of the source row, stored as text.
    record_id VARCHAR(255) NOT NULL,
    -- Hash of the row as last backed up. Compared against the live row to
    -- decide whether a new version is needed.
    row_hash VARCHAR(64) NOT NULL,
    -- Version number the row had when it was last backed up.
    backup_version BIGINT NOT NULL,
    -- Timestamp this row was last backed up.
    last_backup_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_backup_states PRIMARY KEY (id),
    CONSTRAINT uq_backup_states_record UNIQUE (table_name, record_id)
);
CREATE INDEX ix_backup_states_table_name ON backup_states (table_name);

COMMENT ON TABLE backup_states IS 'Latest known hash per row, letting the backup job skip unchanged rows without reading the whole table.';
COMMENT ON COLUMN backup_states.table_name IS 'Source table the row belongs to. Indexed so the run can skip whole tables.';
COMMENT ON COLUMN backup_states.record_id IS 'Primary key of the source row, stored as text.';
COMMENT ON COLUMN backup_states.row_hash IS 'Hash of the row as last backed up. Compared against the live row to decide whether a new version is needed.';
COMMENT ON COLUMN backup_states.backup_version IS 'Version number the row had when it was last backed up.';
COMMENT ON COLUMN backup_states.last_backup_at IS 'Timestamp this row was last backed up.';
COMMENT ON COLUMN backup_states.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN backup_states.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN backup_states.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: chart_of_accounts
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Chart of accounts. A self-referencing tree of general-ledger accounts;
-- is_postable marks the leaf accounts that journal lines may actually
-- reference.
-- --------------------------------------------------------------------------
CREATE TABLE chart_of_accounts (
    -- Account number as printed in the trial balance. Unique.
    account_code VARCHAR(32) NOT NULL,
    -- Name of the account.
    account_name VARCHAR(255) NOT NULL,
    -- Top-level classification: ASSET, LIABILITY, EQUITY, REVENUE or EXPENSE.
    account_type VARCHAR(20) NOT NULL,
    -- Parent account in the hierarchy. NULL for a top-level account.
    parent_account_id BIGINT,
    -- DEBIT or CREDIT — the side on which the account normally increases.
    normal_balance VARCHAR(10) NOT NULL,
    -- TRUE when journal lines may post to this account. FALSE for headers and
    -- roll-up accounts.
    is_postable BOOLEAN NOT NULL,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_chart_of_accounts PRIMARY KEY (id),
    CONSTRAINT uq_coa_code UNIQUE (account_code),
    CONSTRAINT fk_chart_of_accounts_parent_account_id_chart_of_accounts FOREIGN KEY(parent_account_id) REFERENCES chart_of_accounts (id)
);

COMMENT ON TABLE chart_of_accounts IS 'Chart of accounts. A self-referencing tree of general-ledger accounts; is_postable marks the leaf accounts that journal lines may actually reference.';
COMMENT ON COLUMN chart_of_accounts.account_code IS 'Account number as printed in the trial balance. Unique.';
COMMENT ON COLUMN chart_of_accounts.account_name IS 'Name of the account.';
COMMENT ON COLUMN chart_of_accounts.account_type IS 'Top-level classification: ASSET, LIABILITY, EQUITY, REVENUE or EXPENSE.';
COMMENT ON COLUMN chart_of_accounts.parent_account_id IS 'Parent account in the hierarchy. NULL for a top-level account.';
COMMENT ON COLUMN chart_of_accounts.normal_balance IS 'DEBIT or CREDIT — the side on which the account normally increases.';
COMMENT ON COLUMN chart_of_accounts.is_postable IS 'TRUE when journal lines may post to this account. FALSE for headers and roll-up accounts.';
COMMENT ON COLUMN chart_of_accounts.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN chart_of_accounts.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN chart_of_accounts.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN chart_of_accounts.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: component_attributes
-- Module: Master Data  [app.modules.master_data.models]
-- Reusable dynamic-form attribute (field) in the global catalog. Attributes
-- are defined once and then referenced by one or more component groups, so a
-- field such as "Container No." can be reused everywhere.
-- --------------------------------------------------------------------------
CREATE TABLE component_attributes (
    -- Attribute code. Also the JSON key under which the value is stored in
    -- service_order_component_rows.values, so changing it orphans existing
    -- values.
    code VARCHAR(64) NOT NULL,
    -- English label rendered in the UI.
    label VARCHAR(255) NOT NULL,
    -- Admin-managed Khmer label. This is user-defined data, not a parallel
    -- copy of label — copy shipped in code is resolved through the i18n
    -- bundles instead.
    label_km VARCHAR(255),
    -- Storage and logic type: text, number, date, boolean, select, reference.
    data_type VARCHAR(32) NOT NULL,
    -- UI widget override, used when it differs from the widget implied by
    -- data_type.
    input_type VARCHAR(32),
    -- Master-data collection a reference-type attribute points at, for
    -- example business_parties or container_types.
    reference_type VARCHAR(32),
    -- Default required flag. An individual component group may override it.
    is_required BOOLEAN NOT NULL,
    -- Value pre-filled when a new row is created.
    default_value VARCHAR(255),
    -- Hint shown inside the empty input.
    placeholder VARCHAR(255),
    -- Rendered column width hint for table-mode groups.
    width VARCHAR(16),
    -- JSON array of selectable values for a select-type attribute.
    options JSONB NOT NULL,
    -- JSON object of validation rules (min, max, pattern, required, ...).
    validation_rules JSONB NOT NULL,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_component_attributes PRIMARY KEY (id),
    CONSTRAINT uq_component_attributes_code UNIQUE (code)
);

COMMENT ON TABLE component_attributes IS 'Reusable dynamic-form attribute (field) in the global catalog. Attributes are defined once and then referenced by one or more component groups, so a field such as "Container No." can be reused everywhere.';
COMMENT ON COLUMN component_attributes.code IS 'Attribute code. Also the JSON key under which the value is stored in service_order_component_rows.values, so changing it orphans existing values.';
COMMENT ON COLUMN component_attributes.label IS 'English label rendered in the UI.';
COMMENT ON COLUMN component_attributes.label_km IS 'Admin-managed Khmer label. This is user-defined data, not a parallel copy of label — copy shipped in code is resolved through the i18n bundles instead.';
COMMENT ON COLUMN component_attributes.data_type IS 'Storage and logic type: text, number, date, boolean, select, reference.';
COMMENT ON COLUMN component_attributes.input_type IS 'UI widget override, used when it differs from the widget implied by data_type.';
COMMENT ON COLUMN component_attributes.reference_type IS 'Master-data collection a reference-type attribute points at, for example business_parties or container_types.';
COMMENT ON COLUMN component_attributes.is_required IS 'Default required flag. An individual component group may override it.';
COMMENT ON COLUMN component_attributes.default_value IS 'Value pre-filled when a new row is created.';
COMMENT ON COLUMN component_attributes.placeholder IS 'Hint shown inside the empty input.';
COMMENT ON COLUMN component_attributes.width IS 'Rendered column width hint for table-mode groups.';
COMMENT ON COLUMN component_attributes.options IS 'JSON array of selectable values for a select-type attribute.';
COMMENT ON COLUMN component_attributes.validation_rules IS 'JSON object of validation rules (min, max, pattern, required, ...).';
COMMENT ON COLUMN component_attributes.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN component_attributes.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN component_attributes.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN component_attributes.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: component_groups
-- Module: Master Data  [app.modules.master_data.models]
-- A reusable group of attributes. render_mode is the legacy default; the
-- effective layout (form_only, table_only or form_and_table) is configured
-- per tab assignment on component_tab_groups, so the same group can render
-- differently in different tabs.
-- --------------------------------------------------------------------------
CREATE TABLE component_groups (
    -- Group code. Unique and referenced by component_tab_groups.
    code VARCHAR(64) NOT NULL,
    -- Display name of the group.
    name VARCHAR(255) NOT NULL,
    -- Admin-managed Khmer name.
    name_km VARCHAR(255),
    -- Free-text explanation of what the group collects.
    description TEXT,
    -- Legacy default only: 'table' or 'form'. The effective layout is
    -- component_tab_groups.display_mode; NULL there inherits this value.
    render_mode VARCHAR(16) NOT NULL,
    -- Sort position within its group or list. Lower values are rendered
    -- first; ties are broken by code.
    display_order INTEGER NOT NULL,
    -- TRUE when the group is enabled for new service orders.
    is_active BOOLEAN NOT NULL,
    -- TRUE when the record has been withdrawn. Archived records are hidden
    -- from pickers but retained so historical documents still resolve.
    is_archived BOOLEAN NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_component_groups PRIMARY KEY (id),
    CONSTRAINT uq_component_groups_code UNIQUE (code)
);

COMMENT ON TABLE component_groups IS 'A reusable group of attributes. render_mode is the legacy default; the effective layout (form_only, table_only or form_and_table) is configured per tab assignment on component_tab_groups, so the same group can render differently in different tabs.';
COMMENT ON COLUMN component_groups.code IS 'Group code. Unique and referenced by component_tab_groups.';
COMMENT ON COLUMN component_groups.name IS 'Display name of the group.';
COMMENT ON COLUMN component_groups.name_km IS 'Admin-managed Khmer name.';
COMMENT ON COLUMN component_groups.description IS 'Free-text explanation of what the group collects.';
COMMENT ON COLUMN component_groups.render_mode IS 'Legacy default only: ''table'' or ''form''. The effective layout is component_tab_groups.display_mode; NULL there inherits this value.';
COMMENT ON COLUMN component_groups.display_order IS 'Sort position within its group or list. Lower values are rendered first; ties are broken by code.';
COMMENT ON COLUMN component_groups.is_active IS 'TRUE when the group is enabled for new service orders.';
COMMENT ON COLUMN component_groups.is_archived IS 'TRUE when the record has been withdrawn. Archived records are hidden from pickers but retained so historical documents still resolve.';
COMMENT ON COLUMN component_groups.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN component_groups.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN component_groups.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: document_sequences
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Per-type, per-year counter behind every human-facing document number
-- (SO-000123, INV-000045). Provisioned for the current year during first-run
-- setup.
-- --------------------------------------------------------------------------
CREATE TABLE document_sequences (
    -- Document family the counter serves, for example SERVICE_ORDER or
    -- TAX_INVOICE.
    document_type VARCHAR(64) NOT NULL,
    -- Calendar year the counter belongs to. Sequences restart each year, and
    -- the unique constraint on (document_type, period_year) is what keeps
    -- them independent.
    period_year INTEGER NOT NULL,
    -- Literal prefix emitted before the number, for example 'SO-'.
    prefix VARCHAR(16) NOT NULL,
    -- Highest number already issued. Incremented while holding a row lock so
    -- concurrent requests cannot produce duplicates or reuse a number.
    last_value BIGINT NOT NULL,
    -- Zero-padding width of the numeric part, so numbers sort lexically.
    padding_length INTEGER NOT NULL,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_document_sequences PRIMARY KEY (id),
    CONSTRAINT uq_sequences_type_year UNIQUE (document_type, period_year)
);

COMMENT ON TABLE document_sequences IS 'Per-type, per-year counter behind every human-facing document number (SO-000123, INV-000045). Provisioned for the current year during first-run setup.';
COMMENT ON COLUMN document_sequences.document_type IS 'Document family the counter serves, for example SERVICE_ORDER or TAX_INVOICE.';
COMMENT ON COLUMN document_sequences.period_year IS 'Calendar year the counter belongs to. Sequences restart each year, and the unique constraint on (document_type, period_year) is what keeps them independent.';
COMMENT ON COLUMN document_sequences.prefix IS 'Literal prefix emitted before the number, for example ''SO-''.';
COMMENT ON COLUMN document_sequences.last_value IS 'Highest number already issued. Incremented while holding a row lock so concurrent requests cannot produce duplicates or reuse a number.';
COMMENT ON COLUMN document_sequences.padding_length IS 'Zero-padding width of the numeric part, so numbers sort lexically.';
COMMENT ON COLUMN document_sequences.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN document_sequences.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN document_sequences.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN document_sequences.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: permissions
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Atomic capability in the code-defined permission catalog (for example
-- service_orders.create), synchronised on startup. Rows are never edited by
-- hand.
-- --------------------------------------------------------------------------
CREATE TABLE permissions (
    -- Fully-qualified permission code in the form <resource>.<action> (for
    -- example service_orders.create). This is the value every authorization
    -- check matches on.
    code VARCHAR(128) NOT NULL,
    -- Display name for the permission.
    name VARCHAR(255) NOT NULL,
    -- Resource segment of the code — the page or entity the action applies
    -- to.
    resource VARCHAR(64) NOT NULL,
    -- Action segment of the code (create, read, update, delete, approve,
    -- export, print, reset, restore, manage...).
    action VARCHAR(64) NOT NULL,
    -- Explanation of what the action allows.
    description TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_permissions PRIMARY KEY (id),
    CONSTRAINT uq_permissions_code UNIQUE (code)
);

COMMENT ON TABLE permissions IS 'Atomic capability in the code-defined permission catalog (for example service_orders.create), synchronised on startup. Rows are never edited by hand.';
COMMENT ON COLUMN permissions.code IS 'Fully-qualified permission code in the form <resource>.<action> (for example service_orders.create). This is the value every authorization check matches on.';
COMMENT ON COLUMN permissions.name IS 'Display name for the permission.';
COMMENT ON COLUMN permissions.resource IS 'Resource segment of the code — the page or entity the action applies to.';
COMMENT ON COLUMN permissions.action IS 'Action segment of the code (create, read, update, delete, approve, export, print, reset, restore, manage...).';
COMMENT ON COLUMN permissions.description IS 'Explanation of what the action allows.';
COMMENT ON COLUMN permissions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: roles
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Named role bundling a set of permissions. The catalog is code-defined in
-- app/core/permissions.py and synchronised on startup; administrators grant
-- these roles through the Roles & Permissions screen.
-- --------------------------------------------------------------------------
CREATE TABLE roles (
    -- Stable machine code for the role (e.g. FINANCE_MANAGER). Unique.
    code VARCHAR(64) NOT NULL,
    -- Display name shown in the Roles & Permissions matrix.
    name VARCHAR(255) NOT NULL,
    -- Human-readable explanation of what the role is allowed to do.
    description TEXT,
    -- TRUE for built-in roles that must not be renamed or deleted (for
    -- example the Platform Administrator and the zero-permission
    -- migrated-users role).
    is_system_role BOOLEAN NOT NULL,
    -- Role lifecycle state (ACTIVE, INACTIVE). An inactive role grants
    -- nothing.
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_roles PRIMARY KEY (id),
    CONSTRAINT uq_roles_code UNIQUE (code)
);

COMMENT ON TABLE roles IS 'Named role bundling a set of permissions. The catalog is code-defined in app/core/permissions.py and synchronised on startup; administrators grant these roles through the Roles & Permissions screen.';
COMMENT ON COLUMN roles.code IS 'Stable machine code for the role (e.g. FINANCE_MANAGER). Unique.';
COMMENT ON COLUMN roles.name IS 'Display name shown in the Roles & Permissions matrix.';
COMMENT ON COLUMN roles.description IS 'Human-readable explanation of what the role is allowed to do.';
COMMENT ON COLUMN roles.is_system_role IS 'TRUE for built-in roles that must not be renamed or deleted (for example the Platform Administrator and the zero-permission migrated-users role).';
COMMENT ON COLUMN roles.status IS 'Role lifecycle state (ACTIVE, INACTIVE). An inactive role grants nothing.';
COMMENT ON COLUMN roles.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN roles.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN roles.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: users
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Application user account — one row per person who can sign in.
-- Authorization is granted through user_role_assignments (at most one active
-- role) and the permissions that role carries.
-- --------------------------------------------------------------------------
CREATE TABLE users (
    -- Stable business identifier for the user (e.g. EMP-0001). Unique and
    -- never reused.
    user_code VARCHAR(50) NOT NULL,
    -- Login name used to sign in. Unique across all users.
    username VARCHAR(100) NOT NULL,
    -- Primary email address. Unique, and the delivery target for password
    -- reset codes and notifications.
    email VARCHAR(255) NOT NULL,
    -- Human-readable name shown in the UI, the audit trail and on printed
    -- documents.
    display_name VARCHAR(255) NOT NULL,
    -- Account lifecycle state (ACTIVE, INACTIVE, LOCKED). A non-ACTIVE user
    -- cannot authenticate.
    status VARCHAR(20) NOT NULL,
    -- Default UI language for this user (en, km, zh). A user may override it
    -- per session.
    locale VARCHAR(10) NOT NULL,
    -- IANA timezone name used to render dates and times for this user.
    timezone VARCHAR(64) NOT NULL,
    -- Immutable machine identity for built-in accounts (e.g.
    -- DEFAULT_SYSTEM_ADMIN). Never accepted from an API payload and never
    -- changed by user management.
    system_identity VARCHAR(64),
    -- Timestamp of the most recent successful authentication.
    last_login_at TIMESTAMP WITH TIME ZONE,
    -- Counter embedded in issued access tokens. Incrementing it invalidates
    -- every outstanding token for the user, making revocation immediate
    -- despite stateless JWTs.
    token_version INTEGER DEFAULT '0' NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_user_code UNIQUE (user_code),
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT uq_users_system_identity UNIQUE (system_identity)
);

COMMENT ON TABLE users IS 'Application user account — one row per person who can sign in. Authorization is granted through user_role_assignments (at most one active role) and the permissions that role carries.';
COMMENT ON COLUMN users.user_code IS 'Stable business identifier for the user (e.g. EMP-0001). Unique and never reused.';
COMMENT ON COLUMN users.username IS 'Login name used to sign in. Unique across all users.';
COMMENT ON COLUMN users.email IS 'Primary email address. Unique, and the delivery target for password reset codes and notifications.';
COMMENT ON COLUMN users.display_name IS 'Human-readable name shown in the UI, the audit trail and on printed documents.';
COMMENT ON COLUMN users.status IS 'Account lifecycle state (ACTIVE, INACTIVE, LOCKED). A non-ACTIVE user cannot authenticate.';
COMMENT ON COLUMN users.locale IS 'Default UI language for this user (en, km, zh). A user may override it per session.';
COMMENT ON COLUMN users.timezone IS 'IANA timezone name used to render dates and times for this user.';
COMMENT ON COLUMN users.system_identity IS 'Immutable machine identity for built-in accounts (e.g. DEFAULT_SYSTEM_ADMIN). Never accepted from an API payload and never changed by user management.';
COMMENT ON COLUMN users.last_login_at IS 'Timestamp of the most recent successful authentication.';
COMMENT ON COLUMN users.token_version IS 'Counter embedded in issued access tokens. Incrementing it invalidates every outstanding token for the user, making revocation immediate despite stateless JWTs.';
COMMENT ON COLUMN users.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN users.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN users.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: accounting_periods
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Accounting month used to close the books. Posting is refused into a CLOSED
-- period.
-- --------------------------------------------------------------------------
CREATE TABLE accounting_periods (
    -- Calendar year of the accounting month.
    period_year INTEGER NOT NULL,
    -- Month number, 1 to 12.
    period_month INTEGER NOT NULL,
    -- First day of the accounting month.
    start_date DATE NOT NULL,
    -- Last day of the accounting month.
    end_date DATE NOT NULL,
    -- Period state (OPEN, CLOSING, CLOSED). Indexed because every posting
    -- resolves the period by status.
    status VARCHAR(20) NOT NULL,
    -- Identifier of the user who closed the accounting period for this
    -- record. NULL when the action was performed by the system, or set to
    -- NULL by ON DELETE SET NULL once the user is removed.
    closed_by_user_id BIGINT,
    -- Timestamp the period was closed. NULL while it is still open.
    closed_at TIMESTAMP WITH TIME ZONE,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_accounting_periods PRIMARY KEY (id),
    CONSTRAINT uq_periods_year_month UNIQUE (period_year, period_month),
    CONSTRAINT fk_accounting_periods_closed_by_user_id_users FOREIGN KEY(closed_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_accounting_periods_status ON accounting_periods (status);

COMMENT ON TABLE accounting_periods IS 'Accounting month used to close the books. Posting is refused into a CLOSED period.';
COMMENT ON COLUMN accounting_periods.period_year IS 'Calendar year of the accounting month.';
COMMENT ON COLUMN accounting_periods.period_month IS 'Month number, 1 to 12.';
COMMENT ON COLUMN accounting_periods.start_date IS 'First day of the accounting month.';
COMMENT ON COLUMN accounting_periods.end_date IS 'Last day of the accounting month.';
COMMENT ON COLUMN accounting_periods.status IS 'Period state (OPEN, CLOSING, CLOSED). Indexed because every posting resolves the period by status.';
COMMENT ON COLUMN accounting_periods.closed_by_user_id IS 'Identifier of the user who closed the accounting period for this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN accounting_periods.closed_at IS 'Timestamp the period was closed. NULL while it is still open.';
COMMENT ON COLUMN accounting_periods.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN accounting_periods.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN accounting_periods.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: app_settings
-- Module: Application Settings  [app.modules.settings.models]
-- One keyed application-configuration document per setting group. Settings
-- used to live as a single JSON blob in module_records; a keyed table lets
-- one group be read, validated and written without rewriting the whole
-- document, and lets each row carry its own description and last writer.
-- Payload shape and validation stay in code.
-- --------------------------------------------------------------------------
CREATE TABLE app_settings (
    -- Stable identifier the settings API addresses ('app_info', 'general',
    -- 'localization', 'email', 'telegram', 'notifications', 'security',
    -- 'system', 'backup'). Unique.
    setting_key VARCHAR(120) NOT NULL,
    -- Grouping used to load the whole configuration; equals setting_key for
    -- configuration groups and 'app' for the app-info document.
    setting_group VARCHAR(60) NOT NULL,
    -- JSONB payload for the group. Shape and validation live in code; the
    -- table stores values and never defines or executes behaviour.
    setting_value JSONB NOT NULL,
    -- What the group configures, shown in administration tooling.
    description TEXT,
    -- User who last wrote this group.
    updated_by_user_id BIGINT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_app_settings PRIMARY KEY (id),
    CONSTRAINT uq_app_settings_key UNIQUE (setting_key),
    CONSTRAINT fk_app_settings_updated_by_user_id_users FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_app_settings_group ON app_settings (setting_group);

COMMENT ON TABLE app_settings IS 'One keyed application-configuration document per setting group. Settings used to live as a single JSON blob in module_records; a keyed table lets one group be read, validated and written without rewriting the whole document, and lets each row carry its own description and last writer. Payload shape and validation stay in code.';
COMMENT ON COLUMN app_settings.setting_key IS 'Stable identifier the settings API addresses (''app_info'', ''general'', ''localization'', ''email'', ''telegram'', ''notifications'', ''security'', ''system'', ''backup''). Unique.';
COMMENT ON COLUMN app_settings.setting_group IS 'Grouping used to load the whole configuration; equals setting_key for configuration groups and ''app'' for the app-info document.';
COMMENT ON COLUMN app_settings.setting_value IS 'JSONB payload for the group. Shape and validation live in code; the table stores values and never defines or executes behaviour.';
COMMENT ON COLUMN app_settings.description IS 'What the group configures, shown in administration tooling.';
COMMENT ON COLUMN app_settings.updated_by_user_id IS 'User who last wrote this group.';
COMMENT ON COLUMN app_settings.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN app_settings.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN app_settings.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: archive_records
-- Module: Archive & Retention  [app.modules.archive.models]
-- Archive/restore journal for soft-deleted business records. The row outlives
-- a hard deletion, so a removed record stays traceable and — where a snapshot
-- exists — recoverable.
-- --------------------------------------------------------------------------
CREATE TABLE archive_records (
    -- Table name of the archived record, for example 'service_orders'.
    entity_type VARCHAR(64) NOT NULL,
    -- Primary key the archived record had in its own table.
    entity_id BIGINT NOT NULL,
    -- Human-facing reference captured at archive time (for example
    -- SO-000123). Kept so the record is still identifiable after the source
    -- row is gone.
    record_reference VARCHAR(255) NOT NULL,
    -- Lifecycle of the archived row: ARCHIVED, RESTORED or HARD_DELETED.
    status VARCHAR(20) NOT NULL,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    -- Owner recorded at archive time, so ownership can be reinstated if the
    -- row is restored.
    original_owner_user_id BIGINT,
    -- Timestamp the record was archived. Indexed for retention sweeps.
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Identifier of the user who restored this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    restored_by_user_id BIGINT,
    -- Timestamp the record was restored. NULL while it remains archived.
    restored_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who permanently deleted this record. NULL when
    -- the action was performed by the system, or set to NULL by ON DELETE SET
    -- NULL once the user is removed.
    hard_deleted_by_user_id BIGINT,
    -- Timestamp the record was permanently purged. NULL while it is
    -- recoverable.
    hard_deleted_at TIMESTAMP WITH TIME ZONE,
    -- JSONB copy of the row taken when it was archived. This is what makes
    -- review and restoration possible after the source row is gone.
    snapshot_json JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_archive_records PRIMARY KEY (id),
    CONSTRAINT uq_archive_records_entity UNIQUE (entity_type, entity_id),
    CONSTRAINT fk_archive_records_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_original_owner_user_id_users FOREIGN KEY(original_owner_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_restored_by_user_id_users FOREIGN KEY(restored_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_hard_deleted_by_user_id_users FOREIGN KEY(hard_deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_archive_records_deleted_at ON archive_records (deleted_at);
CREATE INDEX ix_archive_records_deleted_by_user_id ON archive_records (deleted_by_user_id);
CREATE INDEX ix_archive_records_entity_id ON archive_records (entity_id);
CREATE INDEX ix_archive_records_entity_type ON archive_records (entity_type);
CREATE INDEX ix_archive_records_status ON archive_records (status);

COMMENT ON TABLE archive_records IS 'Archive/restore journal for soft-deleted business records. The row outlives a hard deletion, so a removed record stays traceable and — where a snapshot exists — recoverable.';
COMMENT ON COLUMN archive_records.entity_type IS 'Table name of the archived record, for example ''service_orders''.';
COMMENT ON COLUMN archive_records.entity_id IS 'Primary key the archived record had in its own table.';
COMMENT ON COLUMN archive_records.record_reference IS 'Human-facing reference captured at archive time (for example SO-000123). Kept so the record is still identifiable after the source row is gone.';
COMMENT ON COLUMN archive_records.status IS 'Lifecycle of the archived row: ARCHIVED, RESTORED or HARD_DELETED.';
COMMENT ON COLUMN archive_records.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN archive_records.original_owner_user_id IS 'Owner recorded at archive time, so ownership can be reinstated if the row is restored.';
COMMENT ON COLUMN archive_records.deleted_at IS 'Timestamp the record was archived. Indexed for retention sweeps.';
COMMENT ON COLUMN archive_records.restored_by_user_id IS 'Identifier of the user who restored this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN archive_records.restored_at IS 'Timestamp the record was restored. NULL while it remains archived.';
COMMENT ON COLUMN archive_records.hard_deleted_by_user_id IS 'Identifier of the user who permanently deleted this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN archive_records.hard_deleted_at IS 'Timestamp the record was permanently purged. NULL while it is recoverable.';
COMMENT ON COLUMN archive_records.snapshot_json IS 'JSONB copy of the row taken when it was archived. This is what makes review and restoration possible after the source row is gone.';
COMMENT ON COLUMN archive_records.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: attachments
-- Module: Service Operations  [app.modules.operations.models]
-- Metadata for a file held in object storage (MinIO/S3). File bytes never
-- live in PostgreSQL.
-- --------------------------------------------------------------------------
CREATE TABLE attachments (
    -- Original file name as uploaded.
    file_name VARCHAR(512) NOT NULL,
    -- Object key inside the storage bucket. UNIQUE and the canonical
    -- identifier of the stored blob.
    storage_key VARCHAR(512) NOT NULL,
    -- MIME type detected at upload time.
    mime_type VARCHAR(128) NOT NULL,
    -- Size of the stored object in bytes.
    file_size_bytes BIGINT NOT NULL,
    -- Digest used to detect duplicates and corruption.
    checksum VARCHAR(128),
    -- Storage backend holding the object: local or minio.
    storage_provider VARCHAR(32) NOT NULL,
    -- Version number, incremented when several revisions of one document are
    -- stored.
    document_version INTEGER NOT NULL,
    -- Identifier of the user who uploaded this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    uploaded_by_user_id BIGINT,
    -- Timestamp the object was written to storage.
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-delete marker for this metadata row. The stored object is removed
    -- separately, so the row remains as a tombstone.
    is_deleted BOOLEAN NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_attachments PRIMARY KEY (id),
    CONSTRAINT uq_attachments_storage_key UNIQUE (storage_key),
    CONSTRAINT fk_attachments_uploaded_by_user_id_users FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id)
);

COMMENT ON TABLE attachments IS 'Metadata for a file held in object storage (MinIO/S3). File bytes never live in PostgreSQL.';
COMMENT ON COLUMN attachments.file_name IS 'Original file name as uploaded.';
COMMENT ON COLUMN attachments.storage_key IS 'Object key inside the storage bucket. UNIQUE and the canonical identifier of the stored blob.';
COMMENT ON COLUMN attachments.mime_type IS 'MIME type detected at upload time.';
COMMENT ON COLUMN attachments.file_size_bytes IS 'Size of the stored object in bytes.';
COMMENT ON COLUMN attachments.checksum IS 'Digest used to detect duplicates and corruption.';
COMMENT ON COLUMN attachments.storage_provider IS 'Storage backend holding the object: local or minio.';
COMMENT ON COLUMN attachments.document_version IS 'Version number, incremented when several revisions of one document are stored.';
COMMENT ON COLUMN attachments.uploaded_by_user_id IS 'Identifier of the user who uploaded this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN attachments.uploaded_at IS 'Timestamp the object was written to storage.';
COMMENT ON COLUMN attachments.is_deleted IS 'Soft-delete marker for this metadata row. The stored object is removed separately, so the row remains as a tombstone.';
COMMENT ON COLUMN attachments.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: audit_events
-- Module: Audit Trail  [app.modules.audit.models]
-- Append-only audit trail of security- and money-relevant actions.
-- Application code never updates or deletes these rows.
-- --------------------------------------------------------------------------
CREATE TABLE audit_events (
    -- User responsible for the action. NULL for system-initiated events.
    actor_user_id BIGINT,
    -- Event category, for example AUTH, RBAC or POSTING.
    event_type VARCHAR(64) NOT NULL,
    -- Table name of the affected record.
    entity_type VARCHAR(64) NOT NULL,
    -- Primary key of the affected record.
    entity_id BIGINT NOT NULL,
    -- Action performed, for example LOGIN, UPDATE or POST.
    action VARCHAR(64) NOT NULL,
    -- SUCCESS or FAILURE.
    result VARCHAR(32) NOT NULL,
    -- Explanation recorded for failures and permission denials.
    reason TEXT,
    -- Request id from the API error envelope. Ties the event to the
    -- application logs.
    request_id VARCHAR(64),
    -- Correlation id shared by every event belonging to one logical
    -- operation.
    correlation_id VARCHAR(64),
    -- Client IP address the action came from.
    ip_address VARCHAR(64),
    -- Client User-Agent header.
    user_agent TEXT,
    -- JSON snapshot of the record before the change.
    before_json JSONB,
    -- JSON snapshot of the record after the change.
    after_json JSONB,
    -- Additional structured context for the event.
    metadata_json JSONB,
    -- Monetary amount involved, recorded on financial events.
    amount NUMERIC(19, 4),
    -- Timestamp the event occurred (UTC, timezone-aware).
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_audit_events PRIMARY KEY (id),
    CONSTRAINT fk_audit_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id)
);
CREATE INDEX ix_audit_events_entity_id ON audit_events (entity_id);
CREATE INDEX ix_audit_events_entity_type ON audit_events (entity_type);
CREATE INDEX ix_audit_events_event_type ON audit_events (event_type);

COMMENT ON TABLE audit_events IS 'Append-only audit trail of security- and money-relevant actions. Application code never updates or deletes these rows.';
COMMENT ON COLUMN audit_events.actor_user_id IS 'User responsible for the action. NULL for system-initiated events.';
COMMENT ON COLUMN audit_events.event_type IS 'Event category, for example AUTH, RBAC or POSTING.';
COMMENT ON COLUMN audit_events.entity_type IS 'Table name of the affected record.';
COMMENT ON COLUMN audit_events.entity_id IS 'Primary key of the affected record.';
COMMENT ON COLUMN audit_events.action IS 'Action performed, for example LOGIN, UPDATE or POST.';
COMMENT ON COLUMN audit_events.result IS 'SUCCESS or FAILURE.';
COMMENT ON COLUMN audit_events.reason IS 'Explanation recorded for failures and permission denials.';
COMMENT ON COLUMN audit_events.request_id IS 'Request id from the API error envelope. Ties the event to the application logs.';
COMMENT ON COLUMN audit_events.correlation_id IS 'Correlation id shared by every event belonging to one logical operation.';
COMMENT ON COLUMN audit_events.ip_address IS 'Client IP address the action came from.';
COMMENT ON COLUMN audit_events.user_agent IS 'Client User-Agent header.';
COMMENT ON COLUMN audit_events.before_json IS 'JSON snapshot of the record before the change.';
COMMENT ON COLUMN audit_events.after_json IS 'JSON snapshot of the record after the change.';
COMMENT ON COLUMN audit_events.metadata_json IS 'Additional structured context for the event.';
COMMENT ON COLUMN audit_events.amount IS 'Monetary amount involved, recorded on financial events.';
COMMENT ON COLUMN audit_events.occurred_at IS 'Timestamp the event occurred (UTC, timezone-aware).';
COMMENT ON COLUMN audit_events.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: backup_runs
-- Module: Google Sheets Backup  [app.modules.backup.models]
-- One execution of the Google Sheets backup job (manual or scheduled) with
-- its counters and outcome. Runs are kept for operational history.
-- --------------------------------------------------------------------------
CREATE TABLE backup_runs (
    -- What started the run: scheduled or manual.
    trigger VARCHAR(16) NOT NULL,
    -- Run outcome (running, success, partial, failed). Indexed for the runs
    -- list.
    status VARCHAR(16) NOT NULL,
    -- Timestamp the run started.
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Timestamp the run completed. NULL while the run is still running.
    finished_at TIMESTAMP WITH TIME ZONE,
    -- Wall-clock runtime in milliseconds.
    duration_ms INTEGER,
    -- Number of tables the job planned to process.
    tables_total INTEGER NOT NULL,
    -- Tables actually finished before the run ended.
    tables_processed INTEGER NOT NULL,
    -- Rows examined during the run.
    rows_scanned INTEGER NOT NULL,
    -- New versions written to the spreadsheet.
    rows_inserted INTEGER NOT NULL,
    -- Changed rows pushed to the spreadsheet.
    rows_updated INTEGER NOT NULL,
    -- Rows unchanged since the last backup and therefore skipped.
    rows_skipped INTEGER NOT NULL,
    -- Rows that could not be backed up.
    rows_failed INTEGER NOT NULL,
    -- Google Sheets spreadsheet that received the data.
    spreadsheet_id VARCHAR(255),
    -- Identifier of the user who triggered this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    triggered_by_user_id BIGINT,
    -- Human-readable summary of the run outcome.
    message TEXT,
    -- JSONB payload with structured run diagnostics.
    detail JSONB,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_backup_runs PRIMARY KEY (id),
    CONSTRAINT fk_backup_runs_triggered_by_user_id_users FOREIGN KEY(triggered_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_backup_runs_status ON backup_runs (status);

COMMENT ON TABLE backup_runs IS 'One execution of the Google Sheets backup job (manual or scheduled) with its counters and outcome. Runs are kept for operational history.';
COMMENT ON COLUMN backup_runs.trigger IS 'What started the run: scheduled or manual.';
COMMENT ON COLUMN backup_runs.status IS 'Run outcome (running, success, partial, failed). Indexed for the runs list.';
COMMENT ON COLUMN backup_runs.started_at IS 'Timestamp the run started.';
COMMENT ON COLUMN backup_runs.finished_at IS 'Timestamp the run completed. NULL while the run is still running.';
COMMENT ON COLUMN backup_runs.duration_ms IS 'Wall-clock runtime in milliseconds.';
COMMENT ON COLUMN backup_runs.tables_total IS 'Number of tables the job planned to process.';
COMMENT ON COLUMN backup_runs.tables_processed IS 'Tables actually finished before the run ended.';
COMMENT ON COLUMN backup_runs.rows_scanned IS 'Rows examined during the run.';
COMMENT ON COLUMN backup_runs.rows_inserted IS 'New versions written to the spreadsheet.';
COMMENT ON COLUMN backup_runs.rows_updated IS 'Changed rows pushed to the spreadsheet.';
COMMENT ON COLUMN backup_runs.rows_skipped IS 'Rows unchanged since the last backup and therefore skipped.';
COMMENT ON COLUMN backup_runs.rows_failed IS 'Rows that could not be backed up.';
COMMENT ON COLUMN backup_runs.spreadsheet_id IS 'Google Sheets spreadsheet that received the data.';
COMMENT ON COLUMN backup_runs.triggered_by_user_id IS 'Identifier of the user who triggered this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN backup_runs.message IS 'Human-readable summary of the run outcome.';
COMMENT ON COLUMN backup_runs.detail IS 'JSONB payload with structured run diagnostics.';
COMMENT ON COLUMN backup_runs.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN backup_runs.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN backup_runs.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: business_parties
-- Module: Master Data  [app.modules.master_data.models]
-- Counterparty master record for any legal entity the platform trades with —
-- customer, supplier, carrier or agent. One row may carry several roles.
-- --------------------------------------------------------------------------
CREATE TABLE business_parties (
    -- Stable business identifier for the party (e.g. CUST-0001).
    party_code VARCHAR(50) NOT NULL,
    -- Registered legal name. Printed on tax invoices.
    legal_name VARCHAR(255) NOT NULL,
    -- Short name used in lists and dropdowns when it differs from the legal
    -- name.
    display_name VARCHAR(255),
    -- VAT / tax identification number. Unique among non-archived rows so a
    -- party cannot be duplicated by re-entering the same tax number.
    vat_tin VARCHAR(64),
    -- Primary contact name.
    contact_person VARCHAR(255),
    -- Primary contact phone number.
    phone VARCHAR(64),
    -- Primary contact email address.
    email VARCHAR(255),
    -- Registered or operating address.
    address TEXT,
    -- Legacy JSON snapshot of the party's role names. Assignments are read
    -- from business_party_roles, so a role rename is reflected without
    -- rewriting this column.
    roles JSONB NOT NULL,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_business_parties PRIMARY KEY (id),
    CONSTRAINT fk_business_parties_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_business_parties_deleted_at ON business_parties (deleted_at);
CREATE INDEX ix_business_parties_deleted_by_user_id ON business_parties (deleted_by_user_id);
CREATE UNIQUE INDEX uq_business_parties_party_code_active ON business_parties (party_code) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_business_parties_vat_tin_active ON business_parties (vat_tin) WHERE deleted_at IS NULL;

COMMENT ON TABLE business_parties IS 'Counterparty master record for any legal entity the platform trades with — customer, supplier, carrier or agent. One row may carry several roles.';
COMMENT ON COLUMN business_parties.party_code IS 'Stable business identifier for the party (e.g. CUST-0001).';
COMMENT ON COLUMN business_parties.legal_name IS 'Registered legal name. Printed on tax invoices.';
COMMENT ON COLUMN business_parties.display_name IS 'Short name used in lists and dropdowns when it differs from the legal name.';
COMMENT ON COLUMN business_parties.vat_tin IS 'VAT / tax identification number. Unique among non-archived rows so a party cannot be duplicated by re-entering the same tax number.';
COMMENT ON COLUMN business_parties.contact_person IS 'Primary contact name.';
COMMENT ON COLUMN business_parties.phone IS 'Primary contact phone number.';
COMMENT ON COLUMN business_parties.email IS 'Primary contact email address.';
COMMENT ON COLUMN business_parties.address IS 'Registered or operating address.';
COMMENT ON COLUMN business_parties.roles IS 'Legacy JSON snapshot of the party''s role names. Assignments are read from business_party_roles, so a role rename is reflected without rewriting this column.';
COMMENT ON COLUMN business_parties.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN business_parties.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN business_parties.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN business_parties.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN business_parties.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN business_parties.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: component_group_attributes
-- Module: Master Data  [app.modules.master_data.models]
-- Membership of a reusable attribute in a component group, with per-group
-- overrides of the required flag and width.
-- --------------------------------------------------------------------------
CREATE TABLE component_group_attributes (
    -- Component group the attribute belongs to. CASCADE on group deletion.
    group_id BIGINT NOT NULL,
    -- Attribute catalog entry being included. CASCADE on attribute deletion.
    attribute_id BIGINT NOT NULL,
    -- Group-level override of the required flag. NULL inherits the attribute
    -- default.
    is_required BOOLEAN,
    -- Group-level width override. NULL inherits the attribute default.
    width VARCHAR(16),
    -- Sort position within its group or list. Lower values are rendered
    -- first; ties are broken by code.
    display_order INTEGER NOT NULL,
    -- FALSE hides the field in every tab that uses this group. Values already
    -- saved are kept.
    is_visible BOOLEAN DEFAULT 'true' NOT NULL,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_component_group_attributes PRIMARY KEY (id),
    CONSTRAINT uq_component_group_attributes_group_attr UNIQUE (group_id, attribute_id),
    CONSTRAINT fk_component_group_attributes_group_id_component_groups FOREIGN KEY(group_id) REFERENCES component_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_component_group_attributes_attribute_id_component_attributes FOREIGN KEY(attribute_id) REFERENCES component_attributes (id) ON DELETE CASCADE
);
CREATE INDEX ix_component_group_attributes_attribute_id ON component_group_attributes (attribute_id);
CREATE INDEX ix_component_group_attributes_group_id ON component_group_attributes (group_id);

COMMENT ON TABLE component_group_attributes IS 'Membership of a reusable attribute in a component group, with per-group overrides of the required flag and width.';
COMMENT ON COLUMN component_group_attributes.group_id IS 'Component group the attribute belongs to. CASCADE on group deletion.';
COMMENT ON COLUMN component_group_attributes.attribute_id IS 'Attribute catalog entry being included. CASCADE on attribute deletion.';
COMMENT ON COLUMN component_group_attributes.is_required IS 'Group-level override of the required flag. NULL inherits the attribute default.';
COMMENT ON COLUMN component_group_attributes.width IS 'Group-level width override. NULL inherits the attribute default.';
COMMENT ON COLUMN component_group_attributes.display_order IS 'Sort position within its group or list. Lower values are rendered first; ties are broken by code.';
COMMENT ON COLUMN component_group_attributes.is_visible IS 'FALSE hides the field in every tab that uses this group. Values already saved are kept.';
COMMENT ON COLUMN component_group_attributes.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN component_group_attributes.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN component_group_attributes.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN component_group_attributes.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: configuration_versions
-- Module: Master Data  [app.modules.master_data.models]
-- A published snapshot of the dynamic Service Order configuration. Tabs,
-- groups and attributes are edited in place, so without a snapshot a
-- historical Service Order could no longer be rendered the way it was filled
-- in. Exactly one version may be PUBLISHED at a time; RETIRED keeps a
-- snapshot readable after it stops being current. The snapshot is data only -
-- nothing in it is executed.
-- --------------------------------------------------------------------------
CREATE TABLE configuration_versions (
    -- Sequential version number across the installation, starting at 1.
    version_no INTEGER NOT NULL,
    -- Scope this version freezes. GLOBAL today; direction-specific publishing
    -- can use the same column without a second version table.
    scope VARCHAR(32) DEFAULT 'GLOBAL' NOT NULL,
    -- DRAFT (never published), PUBLISHED (the live configuration) or RETIRED
    -- (superseded). A partial unique index allows only one PUBLISHED row.
    status VARCHAR(20) NOT NULL,
    -- PUBLISH for a new live configuration, ROLLBACK when the snapshot copies
    -- an older version.
    origin VARCHAR(20) DEFAULT 'PUBLISH' NOT NULL,
    -- Why the configuration changed; shown in the version history.
    change_note TEXT,
    -- JSONB capture of the tabs, groups and attributes in force at publish
    -- time. Read-only historical reference: nothing in it is executed and
    -- every submitted value is still validated against the live rules.
    config_snapshot JSONB NOT NULL,
    -- Shape version of config_snapshot, so a reader can detect a snapshot
    -- written by an older builder.
    snapshot_schema_version INTEGER DEFAULT '1' NOT NULL,
    -- Hash of the normalised snapshot, used to compare versions without
    -- trusting JSON key order.
    content_hash VARCHAR(64),
    -- Version a ROLLBACK copied; NULL for an ordinary publish.
    source_version_id BIGINT,
    -- Timestamp the version became the live configuration.
    published_at TIMESTAMP WITH TIME ZONE,
    -- User who published this version.
    published_by_user_id BIGINT,
    -- When this version was last made active. The published_* fields stay the
    -- original event.
    activated_at TIMESTAMP WITH TIME ZONE,
    -- User who last activated this version.
    activated_by_user_id BIGINT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_configuration_versions PRIMARY KEY (id),
    CONSTRAINT uq_configuration_versions_no UNIQUE (version_no),
    CONSTRAINT fk_configuration_versions_source_version_id_configurati_2cf3 FOREIGN KEY(source_version_id) REFERENCES configuration_versions (id) ON DELETE SET NULL,
    CONSTRAINT fk_configuration_versions_published_by_user_id_users FOREIGN KEY(published_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_configuration_versions_activated_by_user_id_users FOREIGN KEY(activated_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_configuration_versions_source_version_id ON configuration_versions (source_version_id);
CREATE INDEX ix_configuration_versions_status ON configuration_versions (status);
CREATE UNIQUE INDEX uq_configuration_versions_published ON configuration_versions (status) WHERE status = 'PUBLISHED';

COMMENT ON TABLE configuration_versions IS 'A published snapshot of the dynamic Service Order configuration. Tabs, groups and attributes are edited in place, so without a snapshot a historical Service Order could no longer be rendered the way it was filled in. Exactly one version may be PUBLISHED at a time; RETIRED keeps a snapshot readable after it stops being current. The snapshot is data only - nothing in it is executed.';
COMMENT ON COLUMN configuration_versions.version_no IS 'Sequential version number across the installation, starting at 1.';
COMMENT ON COLUMN configuration_versions.scope IS 'Scope this version freezes. GLOBAL today; direction-specific publishing can use the same column without a second version table.';
COMMENT ON COLUMN configuration_versions.status IS 'DRAFT (never published), PUBLISHED (the live configuration) or RETIRED (superseded). A partial unique index allows only one PUBLISHED row.';
COMMENT ON COLUMN configuration_versions.origin IS 'PUBLISH for a new live configuration, ROLLBACK when the snapshot copies an older version.';
COMMENT ON COLUMN configuration_versions.change_note IS 'Why the configuration changed; shown in the version history.';
COMMENT ON COLUMN configuration_versions.config_snapshot IS 'JSONB capture of the tabs, groups and attributes in force at publish time. Read-only historical reference: nothing in it is executed and every submitted value is still validated against the live rules.';
COMMENT ON COLUMN configuration_versions.snapshot_schema_version IS 'Shape version of config_snapshot, so a reader can detect a snapshot written by an older builder.';
COMMENT ON COLUMN configuration_versions.content_hash IS 'Hash of the normalised snapshot, used to compare versions without trusting JSON key order.';
COMMENT ON COLUMN configuration_versions.source_version_id IS 'Version a ROLLBACK copied; NULL for an ordinary publish.';
COMMENT ON COLUMN configuration_versions.published_at IS 'Timestamp the version became the live configuration.';
COMMENT ON COLUMN configuration_versions.published_by_user_id IS 'User who published this version.';
COMMENT ON COLUMN configuration_versions.activated_at IS 'When this version was last made active. The published_* fields stay the original event.';
COMMENT ON COLUMN configuration_versions.activated_by_user_id IS 'User who last activated this version.';
COMMENT ON COLUMN configuration_versions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN configuration_versions.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN configuration_versions.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: container_types
-- Module: Master Data  [app.modules.master_data.models]
-- Shipping container type and its ISO 6346 physical dimensions, referenced by
-- quotation container requirements and by actual containers on a service
-- order.
-- --------------------------------------------------------------------------
CREATE TABLE container_types (
    -- Container type code (e.g. 20GP, 40HC). Unique among non-archived rows.
    code VARCHAR(50) NOT NULL,
    -- Display name of the container type.
    name VARCHAR(255) NOT NULL,
    -- Nominal size class, for example 20GP, 40HC or 45HC.
    container_size VARCHAR(32),
    -- Equipment kind: general purpose, reefer, open top, flat rack, tank.
    container_kind VARCHAR(32),
    -- ISO 6346 size and type code, for example 22G1 for a 20-foot general
    -- purpose box.
    iso_code VARCHAR(16),
    -- External length in feet (NUMERIC(6,2)).
    length_feet NUMERIC(6, 2),
    -- External width in millimetres (NUMERIC(8,2)).
    width_millimeter NUMERIC(8, 2),
    -- External height in millimetres (NUMERIC(8,2)).
    height_millimeter NUMERIC(8, 2),
    -- Maximum gross weight in kilograms (NUMERIC(12,3)).
    max_gross_weight_kg NUMERIC(12, 3),
    -- Free-text notes about the container type.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_container_types PRIMARY KEY (id),
    CONSTRAINT fk_container_types_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_container_types_deleted_at ON container_types (deleted_at);
CREATE INDEX ix_container_types_deleted_by_user_id ON container_types (deleted_by_user_id);
CREATE UNIQUE INDEX uq_container_types_code_active ON container_types (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE container_types IS 'Shipping container type and its ISO 6346 physical dimensions, referenced by quotation container requirements and by actual containers on a service order.';
COMMENT ON COLUMN container_types.code IS 'Container type code (e.g. 20GP, 40HC). Unique among non-archived rows.';
COMMENT ON COLUMN container_types.name IS 'Display name of the container type.';
COMMENT ON COLUMN container_types.container_size IS 'Nominal size class, for example 20GP, 40HC or 45HC.';
COMMENT ON COLUMN container_types.container_kind IS 'Equipment kind: general purpose, reefer, open top, flat rack, tank.';
COMMENT ON COLUMN container_types.iso_code IS 'ISO 6346 size and type code, for example 22G1 for a 20-foot general purpose box.';
COMMENT ON COLUMN container_types.length_feet IS 'External length in feet (NUMERIC(6,2)).';
COMMENT ON COLUMN container_types.width_millimeter IS 'External width in millimetres (NUMERIC(8,2)).';
COMMENT ON COLUMN container_types.height_millimeter IS 'External height in millimetres (NUMERIC(8,2)).';
COMMENT ON COLUMN container_types.max_gross_weight_kg IS 'Maximum gross weight in kilograms (NUMERIC(12,3)).';
COMMENT ON COLUMN container_types.description IS 'Free-text notes about the container type.';
COMMENT ON COLUMN container_types.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN container_types.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN container_types.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN container_types.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN container_types.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN container_types.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: currencies
-- Module: Master Data  [app.modules.master_data.models]
-- Currency master data. Monetary columns keep their ISO code string for
-- backward compatibility, but every configured code resolves to a row here,
-- so a typo can no longer create a currency nobody can report on.
-- decimal_places is the currency's own precision, used to round every
-- converted (base-currency) amount.
-- --------------------------------------------------------------------------
CREATE TABLE currencies (
    -- ISO 4217 alphabetic code, stored upper-case. Unique among non-archived
    -- rows, so a deleted currency's code can be reused.
    code VARCHAR(3) NOT NULL,
    -- Human-readable currency name (e.g. 'US Dollar').
    name VARCHAR(100) NOT NULL,
    -- Display symbol (e.g. '$', 'KHR'). Optional; used on printed documents.
    symbol VARCHAR(10),
    -- ISO 4217 numeric code. Optional; kept for external-system interchange.
    numeric_code VARCHAR(3),
    -- Number of decimal places this currency is denominated in (0-6, default
    -- 2). Used to round every converted base-currency amount, so a whole-unit
    -- currency such as KHR is not given cents it does not have.
    decimal_places INTEGER NOT NULL,
    -- Free-text notes about where and how this currency is used.
    description TEXT,
    -- Lifecycle state. ACTIVE currencies may be selected on new documents.
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_currencies PRIMARY KEY (id),
    CONSTRAINT fk_currencies_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_currencies_deleted_at ON currencies (deleted_at);
CREATE INDEX ix_currencies_deleted_by_user_id ON currencies (deleted_by_user_id);
CREATE UNIQUE INDEX uq_currencies_code_active ON currencies (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE currencies IS 'Currency master data. Monetary columns keep their ISO code string for backward compatibility, but every configured code resolves to a row here, so a typo can no longer create a currency nobody can report on. decimal_places is the currency''s own precision, used to round every converted (base-currency) amount.';
COMMENT ON COLUMN currencies.code IS 'ISO 4217 alphabetic code, stored upper-case. Unique among non-archived rows, so a deleted currency''s code can be reused.';
COMMENT ON COLUMN currencies.name IS 'Human-readable currency name (e.g. ''US Dollar'').';
COMMENT ON COLUMN currencies.symbol IS 'Display symbol (e.g. ''$'', ''KHR''). Optional; used on printed documents.';
COMMENT ON COLUMN currencies.numeric_code IS 'ISO 4217 numeric code. Optional; kept for external-system interchange.';
COMMENT ON COLUMN currencies.decimal_places IS 'Number of decimal places this currency is denominated in (0-6, default 2). Used to round every converted base-currency amount, so a whole-unit currency such as KHR is not given cents it does not have.';
COMMENT ON COLUMN currencies.description IS 'Free-text notes about where and how this currency is used.';
COMMENT ON COLUMN currencies.status IS 'Lifecycle state. ACTIVE currencies may be selected on new documents.';
COMMENT ON COLUMN currencies.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN currencies.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN currencies.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN currencies.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN currencies.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: currency_rates
-- Module: Master Data  [app.modules.master_data.models]
-- Approved currency conversion rates, versioned by effective date. A document
-- in another currency resolves its rate from the newest APPROVED row for the
-- pair (in either direction) and copies it onto the document, so a later rate
-- change can never move an amount that was already posted.
-- --------------------------------------------------------------------------
CREATE TABLE currency_rates (
    -- Currency converted away from. With to_currency_code and effective_date
    -- it is unique among non-archived rows.
    from_currency_code VARCHAR(3) NOT NULL,
    -- Currency converted into: the row reads '1 FROM = rate TO'.
    to_currency_code VARCHAR(3) NOT NULL,
    -- Date this rate starts applying. A document resolves the newest APPROVED
    -- row whose effective date is on or before the document's own date.
    effective_date DATE NOT NULL,
    -- How many TO units one FROM unit is worth (NUMERIC(19,8)); CHECK rate >
    -- 0. A document stores the inverse when it is denominated in FROM,
    -- because the ledger computes base = amount * exchange_rate.
    rate NUMERIC(19, 8) NOT NULL,
    -- PENDING while an operator enters it, APPROVED once it may be applied to
    -- documents, INACTIVE to retire it without deleting the row.
    status VARCHAR(20) NOT NULL,
    -- Where the rate came from, for example the bank or central-bank
    -- reference.
    source VARCHAR(80),
    -- Free-text note explaining the rate, kept with the row as its audit
    -- context.
    description TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_currency_rates PRIMARY KEY (id),
    CONSTRAINT fk_currency_rates_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_currency_rates_deleted_at ON currency_rates (deleted_at);
CREATE INDEX ix_currency_rates_deleted_by_user_id ON currency_rates (deleted_by_user_id);
CREATE INDEX ix_currency_rates_lookup ON currency_rates (from_currency_code, to_currency_code, effective_date, status);
CREATE UNIQUE INDEX uq_currency_rates_pair_date ON currency_rates (from_currency_code, to_currency_code, effective_date) WHERE deleted_at IS NULL;

COMMENT ON TABLE currency_rates IS 'Approved currency conversion rates, versioned by effective date. A document in another currency resolves its rate from the newest APPROVED row for the pair (in either direction) and copies it onto the document, so a later rate change can never move an amount that was already posted.';
COMMENT ON COLUMN currency_rates.from_currency_code IS 'Currency converted away from. With to_currency_code and effective_date it is unique among non-archived rows.';
COMMENT ON COLUMN currency_rates.to_currency_code IS 'Currency converted into: the row reads ''1 FROM = rate TO''.';
COMMENT ON COLUMN currency_rates.effective_date IS 'Date this rate starts applying. A document resolves the newest APPROVED row whose effective date is on or before the document''s own date.';
COMMENT ON COLUMN currency_rates.rate IS 'How many TO units one FROM unit is worth (NUMERIC(19,8)); CHECK rate > 0. A document stores the inverse when it is denominated in FROM, because the ledger computes base = amount * exchange_rate.';
COMMENT ON COLUMN currency_rates.status IS 'PENDING while an operator enters it, APPROVED once it may be applied to documents, INACTIVE to retire it without deleting the row.';
COMMENT ON COLUMN currency_rates.source IS 'Where the rate came from, for example the bank or central-bank reference.';
COMMENT ON COLUMN currency_rates.description IS 'Free-text note explaining the rate, kept with the row as its audit context.';
COMMENT ON COLUMN currency_rates.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN currency_rates.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN currency_rates.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN currency_rates.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN currency_rates.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: fee_types
-- Module: Master Data  [app.modules.master_data.models]
-- Catalogue of chargeable services (freight, handling, THC, duty, delivery)
-- used to classify every priced line in quotations, service-order pricing and
-- charges.
-- --------------------------------------------------------------------------
CREATE TABLE fee_types (
    -- Short fee code (e.g. THC). Unique among non-archived rows.
    code VARCHAR(50) NOT NULL,
    -- Display name of the chargeable service.
    name VARCHAR(255) NOT NULL,
    -- Free-text notes about the fee.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_fee_types PRIMARY KEY (id),
    CONSTRAINT fk_fee_types_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_fee_types_deleted_at ON fee_types (deleted_at);
CREATE INDEX ix_fee_types_deleted_by_user_id ON fee_types (deleted_by_user_id);
CREATE UNIQUE INDEX uq_fee_types_code_active ON fee_types (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE fee_types IS 'Catalogue of chargeable services (freight, handling, THC, duty, delivery) used to classify every priced line in quotations, service-order pricing and charges.';
COMMENT ON COLUMN fee_types.code IS 'Short fee code (e.g. THC). Unique among non-archived rows.';
COMMENT ON COLUMN fee_types.name IS 'Display name of the chargeable service.';
COMMENT ON COLUMN fee_types.description IS 'Free-text notes about the fee.';
COMMENT ON COLUMN fee_types.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN fee_types.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN fee_types.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN fee_types.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN fee_types.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN fee_types.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: financial_accounts
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Bank or cash account used for settlement, linked to the general-ledger
-- account that carries its balance.
-- --------------------------------------------------------------------------
CREATE TABLE financial_accounts (
    -- General-ledger account holding this bank or cash balance. UNIQUE, so
    -- one GL account maps to at most one financial account.
    account_id BIGINT NOT NULL,
    -- Display name of the bank or cash account.
    account_name VARCHAR(255) NOT NULL,
    -- Instrument type: BANK, CASH, CARD or MOBILE_WALLET.
    account_type VARCHAR(32) NOT NULL,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Name of the bank or provider.
    bank_name VARCHAR(255),
    -- Masked account number such as ****1234. The full number is never stored
    -- in the database.
    account_number_masked VARCHAR(64),
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_financial_accounts PRIMARY KEY (id),
    CONSTRAINT uq_financial_accounts_account UNIQUE (account_id),
    CONSTRAINT fk_financial_accounts_account_id_chart_of_accounts FOREIGN KEY(account_id) REFERENCES chart_of_accounts (id)
);

COMMENT ON TABLE financial_accounts IS 'Bank or cash account used for settlement, linked to the general-ledger account that carries its balance.';
COMMENT ON COLUMN financial_accounts.account_id IS 'General-ledger account holding this bank or cash balance. UNIQUE, so one GL account maps to at most one financial account.';
COMMENT ON COLUMN financial_accounts.account_name IS 'Display name of the bank or cash account.';
COMMENT ON COLUMN financial_accounts.account_type IS 'Instrument type: BANK, CASH, CARD or MOBILE_WALLET.';
COMMENT ON COLUMN financial_accounts.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN financial_accounts.bank_name IS 'Name of the bank or provider.';
COMMENT ON COLUMN financial_accounts.account_number_masked IS 'Masked account number such as ****1234. The full number is never stored in the database.';
COMMENT ON COLUMN financial_accounts.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN financial_accounts.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN financial_accounts.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN financial_accounts.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: module_records
-- Module: Master Data  [app.modules.master_data.models]
-- Generic record store backing metadata-driven frontend collections. Used for
-- secondary/legacy collections that the frontend renders from its module
-- schema (for example companies, shipments, customs and documents) without a
-- dedicated relational table. The full configured payload lives in data; the
-- key columns support scoping, listing and filtering.
-- --------------------------------------------------------------------------
CREATE TABLE module_records (
    -- Frontend collection this record belongs to (for example 'shipments').
    -- Indexed for list filtering.
    collection VARCHAR(64) NOT NULL,
    -- Business reference number of the record within its collection.
    record_no VARCHAR(64),
    -- Workflow status of the record.
    status VARCHAR(32),
    -- JSONB payload holding every configured field of the collection.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_module_records PRIMARY KEY (id),
    CONSTRAINT fk_module_records_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_module_records_collection ON module_records (collection);
CREATE INDEX ix_module_records_deleted_at ON module_records (deleted_at);
CREATE INDEX ix_module_records_deleted_by_user_id ON module_records (deleted_by_user_id);

COMMENT ON TABLE module_records IS 'Generic record store backing metadata-driven frontend collections. Used for secondary/legacy collections that the frontend renders from its module schema (for example companies, shipments, customs and documents) without a dedicated relational table. The full configured payload lives in data; the key columns support scoping, listing and filtering.';
COMMENT ON COLUMN module_records.collection IS 'Frontend collection this record belongs to (for example ''shipments''). Indexed for list filtering.';
COMMENT ON COLUMN module_records.record_no IS 'Business reference number of the record within its collection.';
COMMENT ON COLUMN module_records.status IS 'Workflow status of the record.';
COMMENT ON COLUMN module_records.data IS 'JSONB payload holding every configured field of the collection.';
COMMENT ON COLUMN module_records.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN module_records.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN module_records.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN module_records.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN module_records.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: party_roles
-- Module: Master Data  [app.modules.master_data.models]
-- Administrator-managed vocabulary of roles a business party can hold
-- (Customer, Supplier, Company, or any role the organisation adds). Replaces
-- the hardcoded dropdown; a role still assigned to a party is deactivated
-- instead of deleted.
-- --------------------------------------------------------------------------
CREATE TABLE party_roles (
    -- Stable role code (e.g. CUSTOMER). Unique among non-archived rows.
    code VARCHAR(50) NOT NULL,
    -- Display name shown in the Business Parties form and in lists.
    name VARCHAR(255) NOT NULL,
    -- Free-text explanation of when the role applies.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE). Only an ACTIVE role is offered on a
    -- new assignment.
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_party_roles PRIMARY KEY (id),
    CONSTRAINT fk_party_roles_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_party_roles_deleted_at ON party_roles (deleted_at);
CREATE INDEX ix_party_roles_deleted_by_user_id ON party_roles (deleted_by_user_id);
CREATE UNIQUE INDEX uq_party_roles_code_active ON party_roles (code) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_party_roles_name_active ON party_roles (name) WHERE deleted_at IS NULL;

COMMENT ON TABLE party_roles IS 'Administrator-managed vocabulary of roles a business party can hold (Customer, Supplier, Company, or any role the organisation adds). Replaces the hardcoded dropdown; a role still assigned to a party is deactivated instead of deleted.';
COMMENT ON COLUMN party_roles.code IS 'Stable role code (e.g. CUSTOMER). Unique among non-archived rows.';
COMMENT ON COLUMN party_roles.name IS 'Display name shown in the Business Parties form and in lists.';
COMMENT ON COLUMN party_roles.description IS 'Free-text explanation of when the role applies.';
COMMENT ON COLUMN party_roles.status IS 'Record status (ACTIVE, INACTIVE). Only an ACTIVE role is offered on a new assignment.';
COMMENT ON COLUMN party_roles.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN party_roles.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN party_roles.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN party_roles.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN party_roles.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: password_reset_tokens
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- One-time password reset code. Only the hash of the code is stored; rows are
-- retained after use for audit purposes.
-- --------------------------------------------------------------------------
CREATE TABLE password_reset_tokens (
    -- User the reset code was issued for.
    user_id BIGINT NOT NULL,
    -- Email address the reset code was delivered to.
    email VARCHAR(255) NOT NULL,
    -- SHA-256 hash of the reset code. Only this digest is stored and
    -- compared.
    code_hash VARCHAR(128) NOT NULL,
    -- Instant after which the code is rejected.
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Set once the code has been redeemed. NULL while the code is still
    -- unused.
    used_at TIMESTAMP WITH TIME ZONE,
    -- Request timestamp for this reset code.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id),
    CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

COMMENT ON TABLE password_reset_tokens IS 'One-time password reset code. Only the hash of the code is stored; rows are retained after use for audit purposes.';
COMMENT ON COLUMN password_reset_tokens.user_id IS 'User the reset code was issued for.';
COMMENT ON COLUMN password_reset_tokens.email IS 'Email address the reset code was delivered to.';
COMMENT ON COLUMN password_reset_tokens.code_hash IS 'SHA-256 hash of the reset code. Only this digest is stored and compared.';
COMMENT ON COLUMN password_reset_tokens.expires_at IS 'Instant after which the code is rejected.';
COMMENT ON COLUMN password_reset_tokens.used_at IS 'Set once the code has been redeemed. NULL while the code is still unused.';
COMMENT ON COLUMN password_reset_tokens.created_at IS 'Request timestamp for this reset code.';
COMMENT ON COLUMN password_reset_tokens.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: place_roles
-- Module: Master Data  [app.modules.master_data.models]
-- Administrator-managed vocabulary of roles a route stop can play (Pickup,
-- Origin, Customs Clearance, ...). Configuration data, not a physical
-- location: the same place can be a loading stop on one document and a
-- destination on another. The initial rows are seeded as data, and a role in
-- use is deactivated rather than deleted so historical routes keep their
-- reference.
-- --------------------------------------------------------------------------
CREATE TABLE place_roles (
    -- Stable role code (e.g. PICKUP). Unique among non-archived rows and
    -- stored on a route stop as its printable snapshot.
    code VARCHAR(50) NOT NULL,
    -- Display name shown in the route-stop dropdown and on the document.
    name VARCHAR(255) NOT NULL,
    -- Free-text explanation of when the role applies.
    description TEXT,
    -- Administrator-controlled display order in the Place Roles page and in
    -- every route-stop dropdown; ties break by name.
    sort_order INTEGER NOT NULL,
    -- Record status (ACTIVE, INACTIVE). A new route stop may only select an
    -- ACTIVE role.
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_place_roles PRIMARY KEY (id),
    CONSTRAINT fk_place_roles_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_place_roles_deleted_at ON place_roles (deleted_at);
CREATE INDEX ix_place_roles_deleted_by_user_id ON place_roles (deleted_by_user_id);
CREATE UNIQUE INDEX uq_place_roles_code_active ON place_roles (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE place_roles IS 'Administrator-managed vocabulary of roles a route stop can play (Pickup, Origin, Customs Clearance, ...). Configuration data, not a physical location: the same place can be a loading stop on one document and a destination on another. The initial rows are seeded as data, and a role in use is deactivated rather than deleted so historical routes keep their reference.';
COMMENT ON COLUMN place_roles.code IS 'Stable role code (e.g. PICKUP). Unique among non-archived rows and stored on a route stop as its printable snapshot.';
COMMENT ON COLUMN place_roles.name IS 'Display name shown in the route-stop dropdown and on the document.';
COMMENT ON COLUMN place_roles.description IS 'Free-text explanation of when the role applies.';
COMMENT ON COLUMN place_roles.sort_order IS 'Administrator-controlled display order in the Place Roles page and in every route-stop dropdown; ties break by name.';
COMMENT ON COLUMN place_roles.status IS 'Record status (ACTIVE, INACTIVE). A new route stop may only select an ACTIVE role.';
COMMENT ON COLUMN place_roles.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN place_roles.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN place_roles.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN place_roles.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN place_roles.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: places
-- Module: Master Data  [app.modules.master_data.models]
-- Legacy location master retained for historical route and movement
-- references. Places are no longer exposed as an editable collection, but the
-- rows and the route-stop foreign keys are kept: dropping the table would
-- destroy operator-entered codes, names and addresses and break historical
-- documents.
-- --------------------------------------------------------------------------
CREATE TABLE places (
    -- Optional operator-entered location code. Unique among non-archived
    -- rows.
    code VARCHAR(50),
    -- Location name shown on historical route stops and movement legs.
    name VARCHAR(255) NOT NULL,
    -- Free-text description of the location.
    description TEXT,
    -- Printable address of the location.
    address TEXT,
    -- Record status (ACTIVE, INACTIVE). Historical rows are retained as-is.
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_places PRIMARY KEY (id),
    CONSTRAINT fk_places_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_places_deleted_at ON places (deleted_at);
CREATE INDEX ix_places_deleted_by_user_id ON places (deleted_by_user_id);
CREATE UNIQUE INDEX uq_places_code_active ON places (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE places IS 'Legacy location master retained for historical route and movement references. Places are no longer exposed as an editable collection, but the rows and the route-stop foreign keys are kept: dropping the table would destroy operator-entered codes, names and addresses and break historical documents.';
COMMENT ON COLUMN places.code IS 'Optional operator-entered location code. Unique among non-archived rows.';
COMMENT ON COLUMN places.name IS 'Location name shown on historical route stops and movement legs.';
COMMENT ON COLUMN places.description IS 'Free-text description of the location.';
COMMENT ON COLUMN places.address IS 'Printable address of the location.';
COMMENT ON COLUMN places.status IS 'Record status (ACTIVE, INACTIVE). Historical rows are retained as-is.';
COMMENT ON COLUMN places.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN places.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN places.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN places.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN places.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: role_permissions
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Join row granting one permission to one role. The composite primary key
-- makes a duplicate grant impossible.
-- --------------------------------------------------------------------------
CREATE TABLE role_permissions (
    -- Role that receives the grant.
    role_id BIGINT NOT NULL,
    -- Permission being granted to the role.
    permission_id BIGINT NOT NULL,
    CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

COMMENT ON TABLE role_permissions IS 'Join row granting one permission to one role. The composite primary key makes a duplicate grant impossible.';
COMMENT ON COLUMN role_permissions.role_id IS 'Role that receives the grant.';
COMMENT ON COLUMN role_permissions.permission_id IS 'Permission being granted to the role.';

-- --------------------------------------------------------------------------
-- Table: trade_directions
-- Module: Master Data  [app.modules.master_data.models]
-- Direction of trade (import, export, domestic). Scopes service-order
-- workflows and decides which component tabs are shown.
-- --------------------------------------------------------------------------
CREATE TABLE trade_directions (
    -- Short direction code (e.g. EXPORT). Unique among non-archived rows.
    code VARCHAR(50) NOT NULL,
    -- Display name of the trade direction.
    name VARCHAR(255) NOT NULL,
    -- Free-text notes about the trade direction.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_trade_directions PRIMARY KEY (id),
    CONSTRAINT fk_trade_directions_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_trade_directions_deleted_at ON trade_directions (deleted_at);
CREATE INDEX ix_trade_directions_deleted_by_user_id ON trade_directions (deleted_by_user_id);
CREATE UNIQUE INDEX uq_trade_directions_code_active ON trade_directions (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE trade_directions IS 'Direction of trade (import, export, domestic). Scopes service-order workflows and decides which component tabs are shown.';
COMMENT ON COLUMN trade_directions.code IS 'Short direction code (e.g. EXPORT). Unique among non-archived rows.';
COMMENT ON COLUMN trade_directions.name IS 'Display name of the trade direction.';
COMMENT ON COLUMN trade_directions.description IS 'Free-text notes about the trade direction.';
COMMENT ON COLUMN trade_directions.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN trade_directions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN trade_directions.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN trade_directions.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN trade_directions.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN trade_directions.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: transport_types
-- Module: Master Data  [app.modules.master_data.models]
-- Mode of transport (sea, air, road, rail, multimodal).
-- --------------------------------------------------------------------------
CREATE TABLE transport_types (
    -- Short transport-mode code (e.g. SEA). Unique among non-archived rows.
    code VARCHAR(50) NOT NULL,
    -- Display name of the transport mode.
    name VARCHAR(255) NOT NULL,
    -- Free-text notes about the transport mode.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_transport_types PRIMARY KEY (id),
    CONSTRAINT fk_transport_types_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_transport_types_deleted_at ON transport_types (deleted_at);
CREATE INDEX ix_transport_types_deleted_by_user_id ON transport_types (deleted_by_user_id);
CREATE UNIQUE INDEX uq_transport_types_code_active ON transport_types (code) WHERE deleted_at IS NULL;

COMMENT ON TABLE transport_types IS 'Mode of transport (sea, air, road, rail, multimodal).';
COMMENT ON COLUMN transport_types.code IS 'Short transport-mode code (e.g. SEA). Unique among non-archived rows.';
COMMENT ON COLUMN transport_types.name IS 'Display name of the transport mode.';
COMMENT ON COLUMN transport_types.description IS 'Free-text notes about the transport mode.';
COMMENT ON COLUMN transport_types.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN transport_types.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN transport_types.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN transport_types.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN transport_types.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN transport_types.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: user_credentials
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Password material for a user, split from users so credential attributes can
-- be locked down independently. user_id is both the primary key and the
-- foreign key, so there is at most one credential row per user.
-- --------------------------------------------------------------------------
CREATE TABLE user_credentials (
    -- Owning user. Primary key and foreign key to users.id, so at most one
    -- credential row exists per user.
    user_id BIGINT NOT NULL,
    -- Argon2id password digest. The plaintext password is never stored or
    -- logged.
    password_hash TEXT NOT NULL,
    -- Hashing algorithm that produced password_hash (argon2id). Kept explicit
    -- so the algorithm can be upgraded without invalidating existing hashes.
    password_algorithm VARCHAR(32) NOT NULL,
    -- Timestamp of the last successful password change.
    password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- True when the password was chosen by somebody other than its owner.
    -- While set, every API route except changing the password answers 403, so
    -- a temporary password cannot be kept in use indefinitely. Cleared by
    -- change_password.
    must_change_password BOOLEAN DEFAULT false NOT NULL,
    -- Consecutive failed sign-in attempts since the last success. Reset to
    -- zero on a successful authentication.
    failed_attempt_count INTEGER NOT NULL,
    -- Instant until which sign-in is refused after too many failed attempts.
    -- NULL when the account is not locked.
    locked_until TIMESTAMP WITH TIME ZONE,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_user_credentials PRIMARY KEY (user_id),
    CONSTRAINT fk_user_credentials_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

COMMENT ON TABLE user_credentials IS 'Password material for a user, split from users so credential attributes can be locked down independently. user_id is both the primary key and the foreign key, so there is at most one credential row per user.';
COMMENT ON COLUMN user_credentials.user_id IS 'Owning user. Primary key and foreign key to users.id, so at most one credential row exists per user.';
COMMENT ON COLUMN user_credentials.password_hash IS 'Argon2id password digest. The plaintext password is never stored or logged.';
COMMENT ON COLUMN user_credentials.password_algorithm IS 'Hashing algorithm that produced password_hash (argon2id). Kept explicit so the algorithm can be upgraded without invalidating existing hashes.';
COMMENT ON COLUMN user_credentials.password_changed_at IS 'Timestamp of the last successful password change.';
COMMENT ON COLUMN user_credentials.must_change_password IS 'True when the password was chosen by somebody other than its owner. While set, every API route except changing the password answers 403, so a temporary password cannot be kept in use indefinitely. Cleared by change_password.';
COMMENT ON COLUMN user_credentials.failed_attempt_count IS 'Consecutive failed sign-in attempts since the last success. Reset to zero on a successful authentication.';
COMMENT ON COLUMN user_credentials.locked_until IS 'Instant until which sign-in is refused after too many failed attempts. NULL when the account is not locked.';
COMMENT ON COLUMN user_credentials.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN user_credentials.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: user_role_assignments
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- Assignment of a role to a user. Replacing a role expires the previous row
-- instead of deleting it, so history is preserved while the partial unique
-- index uq_user_role_assignments_active_user keeps at most one active
-- assignment per user.
-- --------------------------------------------------------------------------
CREATE TABLE user_role_assignments (
    -- User the role is assigned to.
    user_id BIGINT NOT NULL,
    -- Role held by the user. Single-role RBAC: only the active row counts.
    role_id BIGINT NOT NULL,
    -- Identifier of the user who assigned this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    assigned_by_user_id BIGINT,
    -- Moment the assignment becomes effective.
    starts_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Expiry of a temporary assignment. NULL means active and permanent; the
    -- partial unique index uq_user_role_assignments_active_user covers
    -- exactly these rows and is the database-level one-user/one-active-role
    -- guarantee.
    expires_at TIMESTAMP WITH TIME ZONE,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_user_role_assignments PRIMARY KEY (id),
    CONSTRAINT fk_user_role_assignments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role_assignments_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id),
    CONSTRAINT fk_user_role_assignments_assigned_by_user_id_users FOREIGN KEY(assigned_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_user_role_assignments_user_id ON user_role_assignments (user_id);
CREATE UNIQUE INDEX uq_user_role_assignments_active_user ON user_role_assignments (user_id) WHERE expires_at IS NULL;

COMMENT ON TABLE user_role_assignments IS 'Assignment of a role to a user. Replacing a role expires the previous row instead of deleting it, so history is preserved while the partial unique index uq_user_role_assignments_active_user keeps at most one active assignment per user.';
COMMENT ON COLUMN user_role_assignments.user_id IS 'User the role is assigned to.';
COMMENT ON COLUMN user_role_assignments.role_id IS 'Role held by the user. Single-role RBAC: only the active row counts.';
COMMENT ON COLUMN user_role_assignments.assigned_by_user_id IS 'Identifier of the user who assigned this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN user_role_assignments.starts_at IS 'Moment the assignment becomes effective.';
COMMENT ON COLUMN user_role_assignments.expires_at IS 'Expiry of a temporary assignment. NULL means active and permanent; the partial unique index uq_user_role_assignments_active_user covers exactly these rows and is the database-level one-user/one-active-role guarantee.';
COMMENT ON COLUMN user_role_assignments.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN user_role_assignments.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN user_role_assignments.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: user_sessions
-- Module: Authentication & Access Control  [app.modules.auth.models]
-- A refresh-token session, one row per issued refresh token. The token itself
-- is stored only as a SHA-256 hash, so a database leak cannot be replayed.
-- --------------------------------------------------------------------------
CREATE TABLE user_sessions (
    -- Session owner.
    user_id BIGINT NOT NULL,
    -- SHA-256 hash of the refresh token. Unique. Token rotation replaces this
    -- value, so a stolen copy of the old token is rejected after first use.
    refresh_token_hash VARCHAR(128) NOT NULL,
    -- Friendly device or browser label shown in the user's active-session
    -- list.
    device_name VARCHAR(255),
    -- IP address the session was created from, retained for audit and anomaly
    -- detection.
    ip_address VARCHAR(64),
    -- Raw User-Agent header captured at sign-in.
    user_agent TEXT,
    -- Timestamp of the most recent request authenticated by this session.
    last_used_at TIMESTAMP WITH TIME ZONE,
    -- Hard expiry enforced by the server; the session is invalid after this
    -- instant.
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Set when the session is logged out or revoked. NULL while the session
    -- is valid.
    revoked_at TIMESTAMP WITH TIME ZONE,
    -- TRUE for "Remember me" sessions: a persistent cookie plus the full
    -- configured lifetime, instead of a browser-session cookie with a short
    -- deadline.
    remember_me BOOLEAN DEFAULT false NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_user_sessions PRIMARY KEY (id),
    CONSTRAINT fk_user_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT uq_user_sessions_refresh_token_hash UNIQUE (refresh_token_hash)
);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

COMMENT ON TABLE user_sessions IS 'A refresh-token session, one row per issued refresh token. The token itself is stored only as a SHA-256 hash, so a database leak cannot be replayed.';
COMMENT ON COLUMN user_sessions.user_id IS 'Session owner.';
COMMENT ON COLUMN user_sessions.refresh_token_hash IS 'SHA-256 hash of the refresh token. Unique. Token rotation replaces this value, so a stolen copy of the old token is rejected after first use.';
COMMENT ON COLUMN user_sessions.device_name IS 'Friendly device or browser label shown in the user''s active-session list.';
COMMENT ON COLUMN user_sessions.ip_address IS 'IP address the session was created from, retained for audit and anomaly detection.';
COMMENT ON COLUMN user_sessions.user_agent IS 'Raw User-Agent header captured at sign-in.';
COMMENT ON COLUMN user_sessions.last_used_at IS 'Timestamp of the most recent request authenticated by this session.';
COMMENT ON COLUMN user_sessions.expires_at IS 'Hard expiry enforced by the server; the session is invalid after this instant.';
COMMENT ON COLUMN user_sessions.revoked_at IS 'Set when the session is logged out or revoked. NULL while the session is valid.';
COMMENT ON COLUMN user_sessions.remember_me IS 'TRUE for "Remember me" sessions: a persistent cookie plus the full configured lifetime, instead of a browser-session cookie with a short deadline.';
COMMENT ON COLUMN user_sessions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN user_sessions.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN user_sessions.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: attachment_links
-- Module: Service Operations  [app.modules.operations.models]
-- Polymorphic link attaching a stored file to any business record.
-- --------------------------------------------------------------------------
CREATE TABLE attachment_links (
    -- Attachment being linked. CASCADE on attachment deletion.
    attachment_id BIGINT NOT NULL,
    -- Table name of the linked record, for example 'service_orders'.
    entity_type VARCHAR(64) NOT NULL,
    -- Primary key of the linked record, resolved together with entity_type.
    -- Deliberately not a foreign key, because a link may point at any table.
    entity_id BIGINT NOT NULL,
    -- Purpose of the attachment: ATTACHMENT, INVOICE, POD (proof of
    -- delivery), CUSTOMS DECLARATION, BILL_OF_LADING and similar.
    attachment_role VARCHAR(64) NOT NULL,
    -- TRUE for the one file that represents the record, for example the
    -- signed proof of delivery.
    is_primary BOOLEAN NOT NULL,
    -- Timestamp the link was created.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_attachment_links PRIMARY KEY (id),
    CONSTRAINT uq_attachment_links_target UNIQUE (attachment_id, entity_type, entity_id, attachment_role),
    CONSTRAINT fk_attachment_links_attachment_id_attachments FOREIGN KEY(attachment_id) REFERENCES attachments (id) ON DELETE CASCADE
);
CREATE INDEX ix_attachment_links_attachment_id ON attachment_links (attachment_id);

COMMENT ON TABLE attachment_links IS 'Polymorphic link attaching a stored file to any business record.';
COMMENT ON COLUMN attachment_links.attachment_id IS 'Attachment being linked. CASCADE on attachment deletion.';
COMMENT ON COLUMN attachment_links.entity_type IS 'Table name of the linked record, for example ''service_orders''.';
COMMENT ON COLUMN attachment_links.entity_id IS 'Primary key of the linked record, resolved together with entity_type. Deliberately not a foreign key, because a link may point at any table.';
COMMENT ON COLUMN attachment_links.attachment_role IS 'Purpose of the attachment: ATTACHMENT, INVOICE, POD (proof of delivery), CUSTOMS DECLARATION, BILL_OF_LADING and similar.';
COMMENT ON COLUMN attachment_links.is_primary IS 'TRUE for the one file that represents the record, for example the signed proof of delivery.';
COMMENT ON COLUMN attachment_links.created_at IS 'Timestamp the link was created.';
COMMENT ON COLUMN attachment_links.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: backup_logs
-- Module: Google Sheets Backup  [app.modules.backup.models]
-- Structured log lines emitted per table while a backup run executes.
-- --------------------------------------------------------------------------
CREATE TABLE backup_logs (
    -- Run the log line belongs to. CASCADE, so deleting a run removes its
    -- log.
    run_id BIGINT,
    -- Log severity: debug, info, warning or error.
    level VARCHAR(16) NOT NULL,
    -- Table being processed when the line was written.
    table_name VARCHAR(128),
    -- Human-readable log message.
    message TEXT NOT NULL,
    -- JSONB payload with structured context for the line.
    detail JSONB,
    -- Timestamp the log line was written (UTC, timezone-aware).
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_backup_logs PRIMARY KEY (id),
    CONSTRAINT fk_backup_logs_run_id_backup_runs FOREIGN KEY(run_id) REFERENCES backup_runs (id) ON DELETE CASCADE
);
CREATE INDEX ix_backup_logs_run_id ON backup_logs (run_id);

COMMENT ON TABLE backup_logs IS 'Structured log lines emitted per table while a backup run executes.';
COMMENT ON COLUMN backup_logs.run_id IS 'Run the log line belongs to. CASCADE, so deleting a run removes its log.';
COMMENT ON COLUMN backup_logs.level IS 'Log severity: debug, info, warning or error.';
COMMENT ON COLUMN backup_logs.table_name IS 'Table being processed when the line was written.';
COMMENT ON COLUMN backup_logs.message IS 'Human-readable log message.';
COMMENT ON COLUMN backup_logs.detail IS 'JSONB payload with structured context for the line.';
COMMENT ON COLUMN backup_logs.created_at IS 'Timestamp the log line was written (UTC, timezone-aware).';
COMMENT ON COLUMN backup_logs.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: backup_records
-- Module: Google Sheets Backup  [app.modules.backup.models]
-- One immutable version of one database row. Append-only: a complete history
-- of every change is preserved and can be replayed after data loss.
-- --------------------------------------------------------------------------
CREATE TABLE backup_records (
    -- Run that produced this version. Set to NULL when the run row is
    -- deleted.
    run_id BIGINT,
    -- Source table the row belongs to.
    table_name VARCHAR(128) NOT NULL,
    -- Primary key of the source row, stored as text because not every table
    -- uses an integer key.
    record_id VARCHAR(255) NOT NULL,
    -- Monotonic version number for this row, incremented on every change.
    backup_version BIGINT NOT NULL,
    -- Timestamp this version was captured.
    backup_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- How the row changed relative to the previous version: insert, update or
    -- delete.
    change_kind VARCHAR(16) NOT NULL,
    -- Deterministic hash of the row contents, used to detect changes.
    row_hash VARCHAR(64) NOT NULL,
    -- JSONB snapshot of the row exactly as it was at backup_at.
    data JSONB NOT NULL,
    -- TRUE once this version has been written to the spreadsheet.
    synced BOOLEAN NOT NULL,
    -- Timestamp the version was written to the spreadsheet.
    synced_at TIMESTAMP WITH TIME ZONE,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_backup_records PRIMARY KEY (id),
    CONSTRAINT uq_backup_records_version UNIQUE (table_name, record_id, row_hash),
    CONSTRAINT fk_backup_records_run_id_backup_runs FOREIGN KEY(run_id) REFERENCES backup_runs (id) ON DELETE SET NULL
);
CREATE INDEX ix_backup_records_synced ON backup_records (synced);
CREATE INDEX ix_backup_records_table_name ON backup_records (table_name);
CREATE INDEX ix_backup_records_table_record ON backup_records (table_name, record_id);

COMMENT ON TABLE backup_records IS 'One immutable version of one database row. Append-only: a complete history of every change is preserved and can be replayed after data loss.';
COMMENT ON COLUMN backup_records.run_id IS 'Run that produced this version. Set to NULL when the run row is deleted.';
COMMENT ON COLUMN backup_records.table_name IS 'Source table the row belongs to.';
COMMENT ON COLUMN backup_records.record_id IS 'Primary key of the source row, stored as text because not every table uses an integer key.';
COMMENT ON COLUMN backup_records.backup_version IS 'Monotonic version number for this row, incremented on every change.';
COMMENT ON COLUMN backup_records.backup_at IS 'Timestamp this version was captured.';
COMMENT ON COLUMN backup_records.change_kind IS 'How the row changed relative to the previous version: insert, update or delete.';
COMMENT ON COLUMN backup_records.row_hash IS 'Deterministic hash of the row contents, used to detect changes.';
COMMENT ON COLUMN backup_records.data IS 'JSONB snapshot of the row exactly as it was at backup_at.';
COMMENT ON COLUMN backup_records.synced IS 'TRUE once this version has been written to the spreadsheet.';
COMMENT ON COLUMN backup_records.synced_at IS 'Timestamp the version was written to the spreadsheet.';
COMMENT ON COLUMN backup_records.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN backup_records.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN backup_records.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: business_party_roles
-- Module: Master Data  [app.modules.master_data.models]
-- Many-to-many assignment of party roles to business parties. The unique pair
-- prevents the same role being assigned twice, and the role FK is RESTRICT so
-- an assigned role cannot be hard-deleted.
-- --------------------------------------------------------------------------
CREATE TABLE business_party_roles (
    -- Party holding the role. CASCADE when the party is purged.
    business_party_id BIGINT NOT NULL,
    -- Assigned role. RESTRICT so an assigned role cannot be hard-deleted.
    party_role_id BIGINT NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_business_party_roles PRIMARY KEY (id),
    CONSTRAINT uq_business_party_roles UNIQUE (business_party_id, party_role_id),
    CONSTRAINT fk_business_party_roles_business_party_id_business_parties FOREIGN KEY(business_party_id) REFERENCES business_parties (id) ON DELETE CASCADE,
    CONSTRAINT fk_business_party_roles_party_role_id_party_roles FOREIGN KEY(party_role_id) REFERENCES party_roles (id) ON DELETE RESTRICT
);
CREATE INDEX ix_business_party_roles_business_party_id ON business_party_roles (business_party_id);
CREATE INDEX ix_business_party_roles_party_role_id ON business_party_roles (party_role_id);

COMMENT ON TABLE business_party_roles IS 'Many-to-many assignment of party roles to business parties. The unique pair prevents the same role being assigned twice, and the role FK is RESTRICT so an assigned role cannot be hard-deleted.';
COMMENT ON COLUMN business_party_roles.business_party_id IS 'Party holding the role. CASCADE when the party is purged.';
COMMENT ON COLUMN business_party_roles.party_role_id IS 'Assigned role. RESTRICT so an assigned role cannot be hard-deleted.';
COMMENT ON COLUMN business_party_roles.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: component_tabs
-- Module: Master Data  [app.modules.master_data.models]
-- A Service Order tab composed of component groups, optionally shown for one
-- trade direction only.
-- --------------------------------------------------------------------------
CREATE TABLE component_tabs (
    -- Tab code. Unique and referenced by the frontend tab registry.
    code VARCHAR(64) NOT NULL,
    -- Display name of the tab.
    name VARCHAR(255) NOT NULL,
    -- Free-text explanation of what the tab holds.
    description TEXT,
    -- Trade direction the tab applies to. NULL means the tab is shown for
    -- every direction.
    trade_direction_id BIGINT,
    -- Sort position within its group or list. Lower values are rendered
    -- first; ties are broken by code.
    display_order INTEGER NOT NULL,
    -- TRUE when the tab is enabled on the Service Order form.
    is_active BOOLEAN NOT NULL,
    -- TRUE when the record has been withdrawn. Archived records are hidden
    -- from pickers but retained so historical documents still resolve.
    is_archived BOOLEAN NOT NULL,
    -- Published configuration version this tab participated in. NULL for a
    -- tab created after the last publish; set by the next publish.
    config_version_id BIGINT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_component_tabs PRIMARY KEY (id),
    CONSTRAINT uq_component_tabs_code UNIQUE (code),
    CONSTRAINT fk_component_tabs_trade_direction_id_trade_directions FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id) ON DELETE SET NULL,
    CONSTRAINT fk_component_tabs_config_version_id_configuration_versions FOREIGN KEY(config_version_id) REFERENCES configuration_versions (id) ON DELETE SET NULL
);
CREATE INDEX ix_component_tabs_trade_direction_id ON component_tabs (trade_direction_id);

COMMENT ON TABLE component_tabs IS 'A Service Order tab composed of component groups, optionally shown for one trade direction only.';
COMMENT ON COLUMN component_tabs.code IS 'Tab code. Unique and referenced by the frontend tab registry.';
COMMENT ON COLUMN component_tabs.name IS 'Display name of the tab.';
COMMENT ON COLUMN component_tabs.description IS 'Free-text explanation of what the tab holds.';
COMMENT ON COLUMN component_tabs.trade_direction_id IS 'Trade direction the tab applies to. NULL means the tab is shown for every direction.';
COMMENT ON COLUMN component_tabs.display_order IS 'Sort position within its group or list. Lower values are rendered first; ties are broken by code.';
COMMENT ON COLUMN component_tabs.is_active IS 'TRUE when the tab is enabled on the Service Order form.';
COMMENT ON COLUMN component_tabs.is_archived IS 'TRUE when the record has been withdrawn. Archived records are hidden from pickers but retained so historical documents still resolve.';
COMMENT ON COLUMN component_tabs.config_version_id IS 'Published configuration version this tab participated in. NULL for a tab created after the last publish; set by the next publish.';
COMMENT ON COLUMN component_tabs.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN component_tabs.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN component_tabs.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: customer_customs_accounts
-- Module: Master Data  [app.modules.master_data.models]
-- Credentials for a customer's portal on an external customs/declaration
-- system, stored so declarations can be filed without re-entering logins.
-- --------------------------------------------------------------------------
CREATE TABLE customer_customs_accounts (
    -- Customer the account belongs to. Deleting the party cascades the
    -- account row away.
    party_id BIGINT NOT NULL,
    -- External system the credentials belong to, for example a customs
    -- declaration portal.
    system_name VARCHAR(128) NOT NULL,
    -- Username on the external system.
    username VARCHAR(255) NOT NULL,
    -- Reference to the secret-store entry holding the password. Preferred
    -- over storing the secret inline.
    password_secret_reference VARCHAR(255),
    -- Encrypted password, used only when no secret-store reference is
    -- available. The plaintext is never stored.
    encrypted_password BYTEA,
    -- Timestamp of the last successful automated verification against the
    -- external system.
    last_verified_at TIMESTAMP WITH TIME ZONE,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_customer_customs_accounts PRIMARY KEY (id),
    CONSTRAINT fk_customer_customs_accounts_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id) ON DELETE CASCADE
);

COMMENT ON TABLE customer_customs_accounts IS 'Credentials for a customer''s portal on an external customs/declaration system, stored so declarations can be filed without re-entering logins.';
COMMENT ON COLUMN customer_customs_accounts.party_id IS 'Customer the account belongs to. Deleting the party cascades the account row away.';
COMMENT ON COLUMN customer_customs_accounts.system_name IS 'External system the credentials belong to, for example a customs declaration portal.';
COMMENT ON COLUMN customer_customs_accounts.username IS 'Username on the external system.';
COMMENT ON COLUMN customer_customs_accounts.password_secret_reference IS 'Reference to the secret-store entry holding the password. Preferred over storing the secret inline.';
COMMENT ON COLUMN customer_customs_accounts.encrypted_password IS 'Encrypted password, used only when no secret-store reference is available. The plaintext is never stored.';
COMMENT ON COLUMN customer_customs_accounts.last_verified_at IS 'Timestamp of the last successful automated verification against the external system.';
COMMENT ON COLUMN customer_customs_accounts.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN customer_customs_accounts.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN customer_customs_accounts.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN customer_customs_accounts.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: place_role_places
-- Module: Master Data  [app.modules.master_data.models]
-- Optional allowed-place mapping for a Place Role. Retained from the former
-- master-data screen; historical route stops use the role plus free text, so
-- the mapping is not required for new writes.
-- --------------------------------------------------------------------------
CREATE TABLE place_role_places (
    -- Place Role the allowed place belongs to. CASCADE on role deletion.
    place_role_id BIGINT NOT NULL,
    -- Allowed legacy place. CASCADE on place deletion.
    place_id BIGINT NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_place_role_places PRIMARY KEY (id),
    CONSTRAINT uq_place_role_places UNIQUE (place_role_id, place_id),
    CONSTRAINT fk_place_role_places_place_role_id_place_roles FOREIGN KEY(place_role_id) REFERENCES place_roles (id) ON DELETE CASCADE,
    CONSTRAINT fk_place_role_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id) ON DELETE CASCADE
);
CREATE INDEX ix_place_role_places_place_id ON place_role_places (place_id);
CREATE INDEX ix_place_role_places_place_role_id ON place_role_places (place_role_id);

COMMENT ON TABLE place_role_places IS 'Optional allowed-place mapping for a Place Role. Retained from the former master-data screen; historical route stops use the role plus free text, so the mapping is not required for new writes.';
COMMENT ON COLUMN place_role_places.place_role_id IS 'Place Role the allowed place belongs to. CASCADE on role deletion.';
COMMENT ON COLUMN place_role_places.place_id IS 'Allowed legacy place. CASCADE on place deletion.';
COMMENT ON COLUMN place_role_places.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: posting_rules
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Rule mapping a document type and fee type to the debit and credit
-- general-ledger accounts applied when a document is posted.
-- --------------------------------------------------------------------------
CREATE TABLE posting_rules (
    -- Document type the rule applies to.
    document_type VARCHAR(32) NOT NULL,
    -- Fee type the rule applies to. NULL makes it the fallback rule for the
    -- whole document type.
    fee_type_id BIGINT,
    -- General-ledger account debited when a matching document is posted.
    debit_account_id BIGINT NOT NULL,
    -- General-ledger account credited when a matching document is posted.
    credit_account_id BIGINT NOT NULL,
    -- General-ledger account that accumulates the tax charged. NULL when no
    -- tax is posted.
    tax_account_id BIGINT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Orders rules that match the same document and fee type. The resolver
    -- takes the highest; two rules sharing the top priority are an ambiguity
    -- error rather than an arbitrary winner. Defaults to 0.
    priority INTEGER NOT NULL,
    -- Administrator's note about why this rule exists.
    description TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_posting_rules PRIMARY KEY (id),
    CONSTRAINT fk_posting_rules_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id),
    CONSTRAINT fk_posting_rules_debit_account_id_chart_of_accounts FOREIGN KEY(debit_account_id) REFERENCES chart_of_accounts (id),
    CONSTRAINT fk_posting_rules_credit_account_id_chart_of_accounts FOREIGN KEY(credit_account_id) REFERENCES chart_of_accounts (id),
    CONSTRAINT fk_posting_rules_tax_account_id_chart_of_accounts FOREIGN KEY(tax_account_id) REFERENCES chart_of_accounts (id)
);
CREATE INDEX ix_posting_rules_resolution ON posting_rules (document_type, status, priority);
CREATE UNIQUE INDEX uq_posting_rules_active_priority ON posting_rules (document_type, coalesce(fee_type_id, 0), priority) WHERE status = 'ACTIVE';

COMMENT ON TABLE posting_rules IS 'Rule mapping a document type and fee type to the debit and credit general-ledger accounts applied when a document is posted.';
COMMENT ON COLUMN posting_rules.document_type IS 'Document type the rule applies to.';
COMMENT ON COLUMN posting_rules.fee_type_id IS 'Fee type the rule applies to. NULL makes it the fallback rule for the whole document type.';
COMMENT ON COLUMN posting_rules.debit_account_id IS 'General-ledger account debited when a matching document is posted.';
COMMENT ON COLUMN posting_rules.credit_account_id IS 'General-ledger account credited when a matching document is posted.';
COMMENT ON COLUMN posting_rules.tax_account_id IS 'General-ledger account that accumulates the tax charged. NULL when no tax is posted.';
COMMENT ON COLUMN posting_rules.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN posting_rules.priority IS 'Orders rules that match the same document and fee type. The resolver takes the highest; two rules sharing the top priority are an ambiguity error rather than an arbitrary winner. Defaults to 0.';
COMMENT ON COLUMN posting_rules.description IS 'Administrator''s note about why this rule exists.';
COMMENT ON COLUMN posting_rules.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN posting_rules.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN posting_rules.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: quotations
-- Module: Quotations  [app.modules.quotations.models]
-- Quotation header. Holds the customer, trade direction and a pointer to the
-- current revision; all commercial detail lives in the revisions so history
-- is never overwritten.
-- --------------------------------------------------------------------------
CREATE TABLE quotations (
    -- Human-facing quotation number, allocated from document_sequences.
    -- Unique.
    quotation_no VARCHAR(50) NOT NULL,
    -- Business party the quotation is issued to.
    customer_party_id BIGINT NOT NULL,
    -- Trade direction the quotation covers.
    trade_direction_id BIGINT NOT NULL,
    -- Revision number currently treated as the live offer. Revisions are
    -- never deleted, so superseded numbers stay reachable for audit.
    current_revision_no INTEGER NOT NULL,
    -- Quotation lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED,
    -- CONVERTED).
    status VARCHAR(20) NOT NULL,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_quotations PRIMARY KEY (id),
    CONSTRAINT uq_quotations_no UNIQUE (quotation_no),
    CONSTRAINT fk_quotations_customer_party_id_business_parties FOREIGN KEY(customer_party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_quotations_trade_direction_id_trade_directions FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id)
);
CREATE INDEX ix_quotations_status ON quotations (status);

COMMENT ON TABLE quotations IS 'Quotation header. Holds the customer, trade direction and a pointer to the current revision; all commercial detail lives in the revisions so history is never overwritten.';
COMMENT ON COLUMN quotations.quotation_no IS 'Human-facing quotation number, allocated from document_sequences. Unique.';
COMMENT ON COLUMN quotations.customer_party_id IS 'Business party the quotation is issued to.';
COMMENT ON COLUMN quotations.trade_direction_id IS 'Trade direction the quotation covers.';
COMMENT ON COLUMN quotations.current_revision_no IS 'Revision number currently treated as the live offer. Revisions are never deleted, so superseded numbers stay reachable for audit.';
COMMENT ON COLUMN quotations.status IS 'Quotation lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED, CONVERTED).';
COMMENT ON COLUMN quotations.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN quotations.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN quotations.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN quotations.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: transport_assets
-- Module: Master Data  [app.modules.master_data.models]
-- Physical transport asset (truck, vessel, aircraft) owned or operated by a
-- business party and assigned to a movement leg.
-- --------------------------------------------------------------------------
CREATE TABLE transport_assets (
    -- Fleet or internal asset number (e.g. VH-118).
    asset_code VARCHAR(50) NOT NULL,
    -- Transport mode this asset belongs to.
    transport_type_id BIGINT NOT NULL,
    -- Registration number, IMO number or tail number identifying the asset.
    identity VARCHAR(128) NOT NULL,
    -- What identity represents: License Plate, IMO Number, Flight Number or
    -- Other.
    identity_type VARCHAR(64) NOT NULL,
    -- Business party that owns the asset.
    owner_party_id BIGINT,
    -- Business party that operates the asset; may differ from the owner.
    operator_party_id BIGINT,
    -- Free-text notes about the asset.
    description TEXT,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Soft-deletion timestamp. A non-NULL value means the row is archived: it
    -- is excluded from listings and uniqueness checks but stays in place.
    deleted_at TIMESTAMP WITH TIME ZONE,
    -- Identifier of the user who archived this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    deleted_by_user_id BIGINT,
    CONSTRAINT pk_transport_assets PRIMARY KEY (id),
    CONSTRAINT fk_transport_assets_transport_type_id_transport_types FOREIGN KEY(transport_type_id) REFERENCES transport_types (id),
    CONSTRAINT fk_transport_assets_owner_party_id_business_parties FOREIGN KEY(owner_party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_transport_assets_operator_party_id_business_parties FOREIGN KEY(operator_party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_transport_assets_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_transport_assets_deleted_at ON transport_assets (deleted_at);
CREATE INDEX ix_transport_assets_deleted_by_user_id ON transport_assets (deleted_by_user_id);
CREATE UNIQUE INDEX uq_transport_assets_asset_code_active ON transport_assets (asset_code) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_transport_assets_type_identity_active ON transport_assets (transport_type_id, identity) WHERE deleted_at IS NULL;

COMMENT ON TABLE transport_assets IS 'Physical transport asset (truck, vessel, aircraft) owned or operated by a business party and assigned to a movement leg.';
COMMENT ON COLUMN transport_assets.asset_code IS 'Fleet or internal asset number (e.g. VH-118).';
COMMENT ON COLUMN transport_assets.transport_type_id IS 'Transport mode this asset belongs to.';
COMMENT ON COLUMN transport_assets.identity IS 'Registration number, IMO number or tail number identifying the asset.';
COMMENT ON COLUMN transport_assets.identity_type IS 'What identity represents: License Plate, IMO Number, Flight Number or Other.';
COMMENT ON COLUMN transport_assets.owner_party_id IS 'Business party that owns the asset.';
COMMENT ON COLUMN transport_assets.operator_party_id IS 'Business party that operates the asset; may differ from the owner.';
COMMENT ON COLUMN transport_assets.description IS 'Free-text notes about the asset.';
COMMENT ON COLUMN transport_assets.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN transport_assets.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN transport_assets.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN transport_assets.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';
COMMENT ON COLUMN transport_assets.deleted_at IS 'Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded from listings and uniqueness checks but stays in place.';
COMMENT ON COLUMN transport_assets.deleted_by_user_id IS 'Identifier of the user who archived this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';

-- --------------------------------------------------------------------------
-- Table: component_tab_groups
-- Module: Master Data  [app.modules.master_data.models]
-- Membership of a component group in a component tab, including the display
-- layout for that assignment (mode, cardinality, form columns,
-- title/read-only/collapse flags).
-- --------------------------------------------------------------------------
CREATE TABLE component_tab_groups (
    -- Component tab the group belongs to. CASCADE on tab deletion.
    tab_id BIGINT NOT NULL,
    -- Component group shown on the tab. CASCADE on group deletion.
    group_id BIGINT NOT NULL,
    -- Sort position within its group or list. Lower values are rendered
    -- first; ties are broken by code.
    display_order INTEGER NOT NULL,
    -- How this group renders in this tab: form_only, table_only or
    -- form_and_table. NULL inherits component_groups.render_mode.
    display_mode VARCHAR(20),
    -- Whether the group holds a single record or multiple records in this
    -- tab. NULL inherits component_groups.render_mode.
    data_cardinality VARCHAR(20),
    -- Number of form columns (1-4) for form layouts. NULL inherits the
    -- default of 3.
    form_columns INTEGER,
    -- Whether the group heading is rendered. NULL defaults to TRUE.
    show_group_title BOOLEAN,
    -- FALSE renders the group read-only and makes the save endpoint refuse
    -- writes. NULL defaults to TRUE.
    editable BOOLEAN,
    -- Whether the group can be collapsed by the user. NULL defaults to FALSE.
    collapsible BOOLEAN,
    -- Initial expanded state of a collapsible group. NULL defaults to TRUE.
    default_expanded BOOLEAN,
    -- Record status (ACTIVE, INACTIVE).
    status VARCHAR(20) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_component_tab_groups PRIMARY KEY (id),
    CONSTRAINT uq_component_tab_groups_tab_group UNIQUE (tab_id, group_id),
    CONSTRAINT ck_component_tab_groups_display_mode CHECK (display_mode IS NULL OR display_mode IN ('form_only', 'table_only', 'form_and_table')),
    CONSTRAINT ck_component_tab_groups_data_cardinality CHECK (data_cardinality IS NULL OR data_cardinality IN ('single', 'multiple')),
    CONSTRAINT ck_component_tab_groups_form_columns CHECK (form_columns IS NULL OR (form_columns BETWEEN 1 AND 4)),
    CONSTRAINT fk_component_tab_groups_tab_id_component_tabs FOREIGN KEY(tab_id) REFERENCES component_tabs (id) ON DELETE CASCADE,
    CONSTRAINT fk_component_tab_groups_group_id_component_groups FOREIGN KEY(group_id) REFERENCES component_groups (id) ON DELETE CASCADE
);
CREATE INDEX ix_component_tab_groups_group_id ON component_tab_groups (group_id);
CREATE INDEX ix_component_tab_groups_tab_id ON component_tab_groups (tab_id);

COMMENT ON TABLE component_tab_groups IS 'Membership of a component group in a component tab, including the display layout for that assignment (mode, cardinality, form columns, title/read-only/collapse flags).';
COMMENT ON COLUMN component_tab_groups.tab_id IS 'Component tab the group belongs to. CASCADE on tab deletion.';
COMMENT ON COLUMN component_tab_groups.group_id IS 'Component group shown on the tab. CASCADE on group deletion.';
COMMENT ON COLUMN component_tab_groups.display_order IS 'Sort position within its group or list. Lower values are rendered first; ties are broken by code.';
COMMENT ON COLUMN component_tab_groups.display_mode IS 'How this group renders in this tab: form_only, table_only or form_and_table. NULL inherits component_groups.render_mode.';
COMMENT ON COLUMN component_tab_groups.data_cardinality IS 'Whether the group holds a single record or multiple records in this tab. NULL inherits component_groups.render_mode.';
COMMENT ON COLUMN component_tab_groups.form_columns IS 'Number of form columns (1-4) for form layouts. NULL inherits the default of 3.';
COMMENT ON COLUMN component_tab_groups.show_group_title IS 'Whether the group heading is rendered. NULL defaults to TRUE.';
COMMENT ON COLUMN component_tab_groups.editable IS 'FALSE renders the group read-only and makes the save endpoint refuse writes. NULL defaults to TRUE.';
COMMENT ON COLUMN component_tab_groups.collapsible IS 'Whether the group can be collapsed by the user. NULL defaults to FALSE.';
COMMENT ON COLUMN component_tab_groups.default_expanded IS 'Initial expanded state of a collapsible group. NULL defaults to TRUE.';
COMMENT ON COLUMN component_tab_groups.status IS 'Record status (ACTIVE, INACTIVE).';
COMMENT ON COLUMN component_tab_groups.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN component_tab_groups.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN component_tab_groups.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: quotation_revisions
-- Module: Quotations  [app.modules.quotations.models]
-- One version of a quotation's commercial terms. Editing an issued quotation
-- creates a new revision instead of mutating this row, so what the customer
-- accepted is always recoverable.
-- --------------------------------------------------------------------------
CREATE TABLE quotation_revisions (
    -- Quotation this revision belongs to. CASCADE on quotation deletion.
    quotation_id BIGINT NOT NULL,
    -- Sequential revision number within the quotation, 1-based. Unique per
    -- quotation together with quotation_id.
    revision_no INTEGER NOT NULL,
    -- Revision lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED,
    -- SUPERSEDED, CONVERTED).
    status VARCHAR(20) NOT NULL,
    -- Date printed on the quotation.
    quotation_date DATE NOT NULL,
    -- Last date the offer is honoured. Past this date the revision is treated
    -- as EXPIRED.
    valid_until DATE,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Short summary of the quotation.
    description TEXT,
    -- Terms and conditions printed with the quotation.
    notes TEXT,
    -- Sum of line subtotals before discount and tax.
    subtotal_amount NUMERIC(19, 4) NOT NULL,
    -- Total discount applied across all lines.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Total tax (VAT) charged across all lines.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Payable total: subtotal minus discount plus tax.
    total_amount NUMERIC(19, 4) NOT NULL,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- Timestamp this revision was sent to the customer.
    sent_at TIMESTAMP WITH TIME ZONE,
    -- Timestamp the customer accepted this revision. The acceptance locks the
    -- commercial terms; further changes require a new revision.
    accepted_at TIMESTAMP WITH TIME ZONE,
    -- Timestamp the customer rejected this revision.
    rejected_at TIMESTAMP WITH TIME ZONE,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_quotation_revisions PRIMARY KEY (id),
    CONSTRAINT uq_quotation_revisions_no UNIQUE (quotation_id, revision_no),
    CONSTRAINT fk_quotation_revisions_quotation_id_quotations FOREIGN KEY(quotation_id) REFERENCES quotations (id) ON DELETE CASCADE,
    CONSTRAINT fk_quotation_revisions_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_quotation_revisions_quotation_id ON quotation_revisions (quotation_id);
CREATE INDEX ix_quotation_revisions_status ON quotation_revisions (status);

COMMENT ON TABLE quotation_revisions IS 'One version of a quotation''s commercial terms. Editing an issued quotation creates a new revision instead of mutating this row, so what the customer accepted is always recoverable.';
COMMENT ON COLUMN quotation_revisions.quotation_id IS 'Quotation this revision belongs to. CASCADE on quotation deletion.';
COMMENT ON COLUMN quotation_revisions.revision_no IS 'Sequential revision number within the quotation, 1-based. Unique per quotation together with quotation_id.';
COMMENT ON COLUMN quotation_revisions.status IS 'Revision lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED, SUPERSEDED, CONVERTED).';
COMMENT ON COLUMN quotation_revisions.quotation_date IS 'Date printed on the quotation.';
COMMENT ON COLUMN quotation_revisions.valid_until IS 'Last date the offer is honoured. Past this date the revision is treated as EXPIRED.';
COMMENT ON COLUMN quotation_revisions.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN quotation_revisions.description IS 'Short summary of the quotation.';
COMMENT ON COLUMN quotation_revisions.notes IS 'Terms and conditions printed with the quotation.';
COMMENT ON COLUMN quotation_revisions.subtotal_amount IS 'Sum of line subtotals before discount and tax.';
COMMENT ON COLUMN quotation_revisions.discount_amount IS 'Total discount applied across all lines.';
COMMENT ON COLUMN quotation_revisions.tax_amount IS 'Total tax (VAT) charged across all lines.';
COMMENT ON COLUMN quotation_revisions.total_amount IS 'Payable total: subtotal minus discount plus tax.';
COMMENT ON COLUMN quotation_revisions.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN quotation_revisions.sent_at IS 'Timestamp this revision was sent to the customer.';
COMMENT ON COLUMN quotation_revisions.accepted_at IS 'Timestamp the customer accepted this revision. The acceptance locks the commercial terms; further changes require a new revision.';
COMMENT ON COLUMN quotation_revisions.rejected_at IS 'Timestamp the customer rejected this revision.';
COMMENT ON COLUMN quotation_revisions.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN quotation_revisions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN quotation_revisions.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN quotation_revisions.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: quotation_conversions
-- Module: Quotations  [app.modules.quotations.models]
-- Record of a quotation revision being converted into a service order. Both
-- unique constraints make conversion idempotent — a revision yields at most
-- one service order and an order originates from at most one revision.
-- --------------------------------------------------------------------------
CREATE TABLE quotation_conversions (
    -- Revision that was converted. UNIQUE, so a revision can produce at most
    -- one service order.
    quotation_revision_id BIGINT NOT NULL,
    -- Service order created from the revision. UNIQUE, so an order originates
    -- from at most one revision.
    service_order_id BIGINT NOT NULL,
    -- Identifier of the user who converted this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    converted_by_user_id BIGINT,
    -- Timestamp the conversion was performed.
    converted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Free-text notes recorded at conversion time.
    notes TEXT,
    -- Client-supplied key that makes a repeated conversion request a no-op.
    -- UNIQUE.
    idempotency_key VARCHAR(128),
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_quotation_conversions PRIMARY KEY (id),
    CONSTRAINT uq_quotation_conversions_quotation_revision_id UNIQUE (quotation_revision_id),
    CONSTRAINT fk_quotation_conversions_quotation_revision_id_quotatio_6c51 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id),
    CONSTRAINT uq_quotation_conversions_service_order_id UNIQUE (service_order_id),
    CONSTRAINT fk_quotation_conversions_converted_by_user_id_users FOREIGN KEY(converted_by_user_id) REFERENCES users (id),
    CONSTRAINT uq_quotation_conversions_idempotency_key UNIQUE (idempotency_key)
);

COMMENT ON TABLE quotation_conversions IS 'Record of a quotation revision being converted into a service order. Both unique constraints make conversion idempotent — a revision yields at most one service order and an order originates from at most one revision.';
COMMENT ON COLUMN quotation_conversions.quotation_revision_id IS 'Revision that was converted. UNIQUE, so a revision can produce at most one service order.';
COMMENT ON COLUMN quotation_conversions.service_order_id IS 'Service order created from the revision. UNIQUE, so an order originates from at most one revision.';
COMMENT ON COLUMN quotation_conversions.converted_by_user_id IS 'Identifier of the user who converted this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN quotation_conversions.converted_at IS 'Timestamp the conversion was performed.';
COMMENT ON COLUMN quotation_conversions.notes IS 'Free-text notes recorded at conversion time.';
COMMENT ON COLUMN quotation_conversions.idempotency_key IS 'Client-supplied key that makes a repeated conversion request a no-op. UNIQUE.';
COMMENT ON COLUMN quotation_conversions.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: quotation_revision_containers
-- Module: Quotations  [app.modules.quotations.models]
-- Container requirement line of a quotation revision.
-- --------------------------------------------------------------------------
CREATE TABLE quotation_revision_containers (
    -- Revision the requirement belongs to. CASCADE on revision deletion.
    quotation_revision_id BIGINT NOT NULL,
    -- Container type being quoted.
    container_type_id BIGINT NOT NULL,
    -- Number of containers of this type quoted (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Quoted gross weight per container in kilograms.
    gross_weight_kg NUMERIC(12, 3),
    -- Short description of the container requirement.
    description TEXT,
    -- Free-text remarks shown on the quotation.
    remarks TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_quotation_revision_containers PRIMARY KEY (id),
    CONSTRAINT fk_quotation_revision_containers_quotation_revision_id__e5b2 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE,
    CONSTRAINT fk_quotation_revision_containers_container_type_id_cont_3afe FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_quotation_revision_containers_quotation_revision_id ON quotation_revision_containers (quotation_revision_id);

COMMENT ON TABLE quotation_revision_containers IS 'Container requirement line of a quotation revision.';
COMMENT ON COLUMN quotation_revision_containers.quotation_revision_id IS 'Revision the requirement belongs to. CASCADE on revision deletion.';
COMMENT ON COLUMN quotation_revision_containers.container_type_id IS 'Container type being quoted.';
COMMENT ON COLUMN quotation_revision_containers.quantity IS 'Number of containers of this type quoted (NUMERIC(12,3)).';
COMMENT ON COLUMN quotation_revision_containers.gross_weight_kg IS 'Quoted gross weight per container in kilograms.';
COMMENT ON COLUMN quotation_revision_containers.description IS 'Short description of the container requirement.';
COMMENT ON COLUMN quotation_revision_containers.remarks IS 'Free-text remarks shown on the quotation.';
COMMENT ON COLUMN quotation_revision_containers.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: quotation_revision_places
-- Module: Quotations  [app.modules.quotations.models]
-- Routing stop of a quotation revision (origin, destination, pickup,
-- delivery).
-- --------------------------------------------------------------------------
CREATE TABLE quotation_revision_places (
    -- Revision the routing stop belongs to. CASCADE on revision deletion.
    quotation_revision_id BIGINT NOT NULL,
    -- Configured Place Role the stop plays. SET NULL only if the role row is
    -- purged; the place_role text snapshot keeps the historical label.
    place_role_id BIGINT,
    -- Legacy Places reference retained for historical route stops. New writes
    -- use the role and free_text snapshot; NULL when the stop never selected
    -- a place.
    place_id BIGINT,
    -- Text snapshot of the role (the role name at save time). Preserved so a
    -- route still prints after the role is renamed or deactivated.
    place_role VARCHAR(32) NOT NULL,
    -- Position of this stop within the route. Unique per revision; the server
    -- renumbers from the submitted row order.
    sequence_no INTEGER NOT NULL,
    -- Planned date/time for the stop.
    planned_at TIMESTAMP WITH TIME ZONE,
    -- Free-text location typed for the stop, kept for printing and history.
    free_text TEXT,
    -- Free-text notes about this stop.
    notes TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_quotation_revision_places PRIMARY KEY (id),
    CONSTRAINT uq_quotation_revision_places_sequence UNIQUE (quotation_revision_id, sequence_no),
    CONSTRAINT fk_quotation_revision_places_quotation_revision_id_quot_f0f2 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE,
    CONSTRAINT fk_quotation_revision_places_place_role_id_place_roles FOREIGN KEY(place_role_id) REFERENCES place_roles (id) ON DELETE SET NULL,
    CONSTRAINT fk_quotation_revision_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id)
);
CREATE INDEX ix_quotation_revision_places_quotation_revision_id ON quotation_revision_places (quotation_revision_id);

COMMENT ON TABLE quotation_revision_places IS 'Routing stop of a quotation revision (origin, destination, pickup, delivery).';
COMMENT ON COLUMN quotation_revision_places.quotation_revision_id IS 'Revision the routing stop belongs to. CASCADE on revision deletion.';
COMMENT ON COLUMN quotation_revision_places.place_role_id IS 'Configured Place Role the stop plays. SET NULL only if the role row is purged; the place_role text snapshot keeps the historical label.';
COMMENT ON COLUMN quotation_revision_places.place_id IS 'Legacy Places reference retained for historical route stops. New writes use the role and free_text snapshot; NULL when the stop never selected a place.';
COMMENT ON COLUMN quotation_revision_places.place_role IS 'Text snapshot of the role (the role name at save time). Preserved so a route still prints after the role is renamed or deactivated.';
COMMENT ON COLUMN quotation_revision_places.sequence_no IS 'Position of this stop within the route. Unique per revision; the server renumbers from the submitted row order.';
COMMENT ON COLUMN quotation_revision_places.planned_at IS 'Planned date/time for the stop.';
COMMENT ON COLUMN quotation_revision_places.free_text IS 'Free-text location typed for the stop, kept for printing and history.';
COMMENT ON COLUMN quotation_revision_places.notes IS 'Free-text notes about this stop.';
COMMENT ON COLUMN quotation_revision_places.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: service_orders
-- Module: Service Operations  [app.modules.operations.models]
-- Service order header — the operational job opened for a customer.
-- Containers, routing, movements, milestones, pricing and charges all hang
-- off this row.
-- --------------------------------------------------------------------------
CREATE TABLE service_orders (
    -- Human-facing order number allocated from document_sequences. Unique.
    service_order_no VARCHAR(50) NOT NULL,
    -- Quotation revision this order was converted from. NULL for orders
    -- entered directly.
    quotation_revision_id BIGINT,
    -- Business party the job is performed for.
    customer_party_id BIGINT NOT NULL,
    -- Trade direction the job covers.
    trade_direction_id BIGINT NOT NULL,
    -- Order lifecycle state (DRAFT, CONFIRMED, IN_PROGRESS, COMPLETED,
    -- CANCELLED). Indexed because the order list filters on it.
    status VARCHAR(20) NOT NULL,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Short summary of the job.
    description TEXT,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- Published configuration version this order was created under. Pins the
    -- order to the dynamic form it was filled in, so publishing a new
    -- configuration cannot re-interpret its saved component rows.
    configuration_version_id BIGINT,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_orders PRIMARY KEY (id),
    CONSTRAINT uq_service_orders_no UNIQUE (service_order_no),
    CONSTRAINT fk_service_orders_quotation_revision_id_quotation_revisions FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id),
    CONSTRAINT fk_service_orders_customer_party_id_business_parties FOREIGN KEY(customer_party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_service_orders_trade_direction_id_trade_directions FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id),
    CONSTRAINT fk_service_orders_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_service_orders_configuration_version_id_configuratio_6d1e FOREIGN KEY(configuration_version_id) REFERENCES configuration_versions (id) ON DELETE SET NULL
);
CREATE INDEX ix_service_orders_status ON service_orders (status);

COMMENT ON TABLE service_orders IS 'Service order header — the operational job opened for a customer. Containers, routing, movements, milestones, pricing and charges all hang off this row.';
COMMENT ON COLUMN service_orders.service_order_no IS 'Human-facing order number allocated from document_sequences. Unique.';
COMMENT ON COLUMN service_orders.quotation_revision_id IS 'Quotation revision this order was converted from. NULL for orders entered directly.';
COMMENT ON COLUMN service_orders.customer_party_id IS 'Business party the job is performed for.';
COMMENT ON COLUMN service_orders.trade_direction_id IS 'Trade direction the job covers.';
COMMENT ON COLUMN service_orders.status IS 'Order lifecycle state (DRAFT, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED). Indexed because the order list filters on it.';
COMMENT ON COLUMN service_orders.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN service_orders.description IS 'Short summary of the job.';
COMMENT ON COLUMN service_orders.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN service_orders.configuration_version_id IS 'Published configuration version this order was created under. Pins the order to the dynamic form it was filled in, so publishing a new configuration cannot re-interpret its saved component rows.';
COMMENT ON COLUMN service_orders.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN service_orders.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_orders.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_orders.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: financial_documents
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Financial document header (tax invoice, proforma, credit note, receipt,
-- payment). Holds the monetary totals and the link to the journal entry
-- produced when it is posted.
-- --------------------------------------------------------------------------
CREATE TABLE financial_documents (
    -- Document number allocated from document_sequences. UNIQUE.
    document_no VARCHAR(50) NOT NULL,
    -- Document kind: TAX_INVOICE, PROFORMA_INVOICE, CREDIT_NOTE, DEBIT_NOTE,
    -- RECEIPT or PAYMENT.
    document_type VARCHAR(32) NOT NULL,
    -- Date of the document as printed.
    document_date DATE NOT NULL,
    -- Date the document was posted to the ledger. This, not document_date,
    -- selects the accounting period it lands in.
    posting_date DATE,
    -- Document lifecycle state (DRAFT, POSTED, PAID, PARTIALLY_PAID,
    -- CANCELLED, REVERSED). Indexed because document lists filter on it.
    status VARCHAR(20) NOT NULL,
    -- Business party the document is issued to or received from.
    party_id BIGINT,
    -- Service order the document bills.
    service_order_id BIGINT,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Rate applied to convert currency_code into base_currency_code
    -- (NUMERIC(19,8)): base amount = amount * rate. Always 1 when the
    -- document is already in the base currency, and snapshotted here so the
    -- conversion survives a rate change.
    exchange_rate NUMERIC(19, 8) NOT NULL,
    -- Base currency this document converts into, taken from the company's
    -- configured base currency when the document is saved. NULL on rows
    -- written before multi-currency existed, when the base currency was a
    -- setting that may since have changed.
    base_currency_code VARCHAR(3),
    -- Short description of the document.
    description TEXT,
    -- External reference, for example the customer's PO or our own proforma
    -- number.
    reference_number VARCHAR(128),
    -- Date payment falls due.
    due_date DATE,
    -- How the payment was or will be made (CASH, BANK_TRANSFER, CARD).
    payment_method_code VARCHAR(64),
    -- Bank or cash account a payment receipt was booked against.
    financial_account_id BIGINT,
    -- Bank value date of a payment document. Kept separate from document_date
    -- because the two often differ by a day or two.
    value_date DATE,
    -- Sum of line amounts before discount and tax.
    subtotal_amount NUMERIC(19, 4) NOT NULL,
    -- Total discount applied across all lines.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Total tax (VAT) charged across all lines.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Document total: subtotal minus discount plus tax.
    total_amount NUMERIC(19, 4) NOT NULL,
    -- subtotal_amount converted into base_currency_code at exchange_rate.
    base_subtotal_amount NUMERIC(19, 4) NOT NULL,
    -- discount_amount converted into base_currency_code at exchange_rate.
    base_discount_amount NUMERIC(19, 4) NOT NULL,
    -- tax_amount converted into base_currency_code at exchange_rate.
    base_tax_amount NUMERIC(19, 4) NOT NULL,
    -- total_amount converted into base_currency_code at exchange_rate,
    -- rounded with the document currency's precision. Re-derived when the
    -- document posts, so it always agrees with the journal lines it writes.
    base_total_amount NUMERIC(19, 4) NOT NULL,
    -- Amount already settled through financial_document_allocations.
    paid_amount NUMERIC(19, 4) NOT NULL,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- Identifier of the user who posted this record. NULL when the action was
    -- performed by the system, or set to NULL by ON DELETE SET NULL once the
    -- user is removed.
    posted_by_user_id BIGINT,
    -- Timestamp the document was posted to the ledger.
    posted_at TIMESTAMP WITH TIME ZONE,
    -- Document that this row reverses. Set on the reversing row and NULL on
    -- originals, so a reversal is always traceable in both directions.
    reversed_document_id BIGINT,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_financial_documents PRIMARY KEY (id),
    CONSTRAINT uq_financial_documents_no UNIQUE (document_no),
    CONSTRAINT fk_financial_documents_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_financial_documents_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id),
    CONSTRAINT fk_financial_documents_financial_account_id_financial_accounts FOREIGN KEY(financial_account_id) REFERENCES financial_accounts (id),
    CONSTRAINT fk_financial_documents_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_financial_documents_posted_by_user_id_users FOREIGN KEY(posted_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_financial_documents_reversed_document_id_financial_documents FOREIGN KEY(reversed_document_id) REFERENCES financial_documents (id)
);
CREATE INDEX ix_financial_documents_document_type ON financial_documents (document_type);
CREATE INDEX ix_financial_documents_status ON financial_documents (status);

COMMENT ON TABLE financial_documents IS 'Financial document header (tax invoice, proforma, credit note, receipt, payment). Holds the monetary totals and the link to the journal entry produced when it is posted.';
COMMENT ON COLUMN financial_documents.document_no IS 'Document number allocated from document_sequences. UNIQUE.';
COMMENT ON COLUMN financial_documents.document_type IS 'Document kind: TAX_INVOICE, PROFORMA_INVOICE, CREDIT_NOTE, DEBIT_NOTE, RECEIPT or PAYMENT.';
COMMENT ON COLUMN financial_documents.document_date IS 'Date of the document as printed.';
COMMENT ON COLUMN financial_documents.posting_date IS 'Date the document was posted to the ledger. This, not document_date, selects the accounting period it lands in.';
COMMENT ON COLUMN financial_documents.status IS 'Document lifecycle state (DRAFT, POSTED, PAID, PARTIALLY_PAID, CANCELLED, REVERSED). Indexed because document lists filter on it.';
COMMENT ON COLUMN financial_documents.party_id IS 'Business party the document is issued to or received from.';
COMMENT ON COLUMN financial_documents.service_order_id IS 'Service order the document bills.';
COMMENT ON COLUMN financial_documents.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN financial_documents.exchange_rate IS 'Rate applied to convert currency_code into base_currency_code (NUMERIC(19,8)): base amount = amount * rate. Always 1 when the document is already in the base currency, and snapshotted here so the conversion survives a rate change.';
COMMENT ON COLUMN financial_documents.base_currency_code IS 'Base currency this document converts into, taken from the company''s configured base currency when the document is saved. NULL on rows written before multi-currency existed, when the base currency was a setting that may since have changed.';
COMMENT ON COLUMN financial_documents.description IS 'Short description of the document.';
COMMENT ON COLUMN financial_documents.reference_number IS 'External reference, for example the customer''s PO or our own proforma number.';
COMMENT ON COLUMN financial_documents.due_date IS 'Date payment falls due.';
COMMENT ON COLUMN financial_documents.payment_method_code IS 'How the payment was or will be made (CASH, BANK_TRANSFER, CARD).';
COMMENT ON COLUMN financial_documents.financial_account_id IS 'Bank or cash account a payment receipt was booked against.';
COMMENT ON COLUMN financial_documents.value_date IS 'Bank value date of a payment document. Kept separate from document_date because the two often differ by a day or two.';
COMMENT ON COLUMN financial_documents.subtotal_amount IS 'Sum of line amounts before discount and tax.';
COMMENT ON COLUMN financial_documents.discount_amount IS 'Total discount applied across all lines.';
COMMENT ON COLUMN financial_documents.tax_amount IS 'Total tax (VAT) charged across all lines.';
COMMENT ON COLUMN financial_documents.total_amount IS 'Document total: subtotal minus discount plus tax.';
COMMENT ON COLUMN financial_documents.base_subtotal_amount IS 'subtotal_amount converted into base_currency_code at exchange_rate.';
COMMENT ON COLUMN financial_documents.base_discount_amount IS 'discount_amount converted into base_currency_code at exchange_rate.';
COMMENT ON COLUMN financial_documents.base_tax_amount IS 'tax_amount converted into base_currency_code at exchange_rate.';
COMMENT ON COLUMN financial_documents.base_total_amount IS 'total_amount converted into base_currency_code at exchange_rate, rounded with the document currency''s precision. Re-derived when the document posts, so it always agrees with the journal lines it writes.';
COMMENT ON COLUMN financial_documents.paid_amount IS 'Amount already settled through financial_document_allocations.';
COMMENT ON COLUMN financial_documents.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN financial_documents.posted_by_user_id IS 'Identifier of the user who posted this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN financial_documents.posted_at IS 'Timestamp the document was posted to the ledger.';
COMMENT ON COLUMN financial_documents.reversed_document_id IS 'Document that this row reverses. Set on the reversing row and NULL on originals, so a reversal is always traceable in both directions.';
COMMENT ON COLUMN financial_documents.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN financial_documents.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN financial_documents.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN financial_documents.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: quotation_revision_lines
-- Module: Quotations  [app.modules.quotations.models]
-- Chargeable price line of a quotation revision.
-- --------------------------------------------------------------------------
CREATE TABLE quotation_revision_lines (
    -- Revision the price line belongs to. CASCADE on revision deletion.
    quotation_revision_id BIGINT NOT NULL,
    -- Sequential line number within the parent document, 1-based and
    -- displayed in order.
    line_no INTEGER NOT NULL,
    -- Catalogue fee this line prices.
    fee_type_id BIGINT,
    -- Container requirement this line prices. Set for per-container charges,
    -- NULL for document-level charges.
    container_requirement_id BIGINT,
    -- Description printed on the quotation for this line.
    service_description TEXT NOT NULL,
    -- Billed quantity (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG,
    -- PERCENT).
    unit_code VARCHAR(32),
    -- Price per unit in currency_code, before discount and tax.
    unit_price NUMERIC(19, 4) NOT NULL,
    -- Discount applied to the line as a rate (NUMERIC(7,4); 0.0500 means 5%).
    discount_rate NUMERIC(7, 4) NOT NULL,
    -- Tax/VAT rate applied to the line (NUMERIC(7,4); 0.1000 means 10%).
    tax_rate NUMERIC(7, 4) NOT NULL,
    -- quantity multiplied by unit_price, before discount and tax.
    line_subtotal NUMERIC(19, 4) NOT NULL,
    -- Absolute discount deducted from line_subtotal.
    line_discount NUMERIC(19, 4) NOT NULL,
    -- Absolute tax charged on the discounted amount.
    line_tax NUMERIC(19, 4) NOT NULL,
    -- Final payable amount for this line.
    line_total NUMERIC(19, 4) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_quotation_revision_lines PRIMARY KEY (id),
    CONSTRAINT uq_quotation_revision_lines_no UNIQUE (quotation_revision_id, line_no),
    CONSTRAINT fk_quotation_revision_lines_quotation_revision_id_quota_6e8c FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE,
    CONSTRAINT fk_quotation_revision_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id),
    CONSTRAINT fk_quotation_revision_lines_container_requirement_id_qu_27b0 FOREIGN KEY(container_requirement_id) REFERENCES quotation_revision_containers (id)
);
CREATE INDEX ix_quotation_revision_lines_quotation_revision_id ON quotation_revision_lines (quotation_revision_id);

COMMENT ON TABLE quotation_revision_lines IS 'Chargeable price line of a quotation revision.';
COMMENT ON COLUMN quotation_revision_lines.quotation_revision_id IS 'Revision the price line belongs to. CASCADE on revision deletion.';
COMMENT ON COLUMN quotation_revision_lines.line_no IS 'Sequential line number within the parent document, 1-based and displayed in order.';
COMMENT ON COLUMN quotation_revision_lines.fee_type_id IS 'Catalogue fee this line prices.';
COMMENT ON COLUMN quotation_revision_lines.container_requirement_id IS 'Container requirement this line prices. Set for per-container charges, NULL for document-level charges.';
COMMENT ON COLUMN quotation_revision_lines.service_description IS 'Description printed on the quotation for this line.';
COMMENT ON COLUMN quotation_revision_lines.quantity IS 'Billed quantity (NUMERIC(12,3)).';
COMMENT ON COLUMN quotation_revision_lines.unit_code IS 'Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG, PERCENT).';
COMMENT ON COLUMN quotation_revision_lines.unit_price IS 'Price per unit in currency_code, before discount and tax.';
COMMENT ON COLUMN quotation_revision_lines.discount_rate IS 'Discount applied to the line as a rate (NUMERIC(7,4); 0.0500 means 5%).';
COMMENT ON COLUMN quotation_revision_lines.tax_rate IS 'Tax/VAT rate applied to the line (NUMERIC(7,4); 0.1000 means 10%).';
COMMENT ON COLUMN quotation_revision_lines.line_subtotal IS 'quantity multiplied by unit_price, before discount and tax.';
COMMENT ON COLUMN quotation_revision_lines.line_discount IS 'Absolute discount deducted from line_subtotal.';
COMMENT ON COLUMN quotation_revision_lines.line_tax IS 'Absolute tax charged on the discounted amount.';
COMMENT ON COLUMN quotation_revision_lines.line_total IS 'Final payable amount for this line.';
COMMENT ON COLUMN quotation_revision_lines.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: service_order_charges
-- Module: Service Operations  [app.modules.operations.models]
-- Customer-facing invoice or service note raised from a service order.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_charges (
    -- Service order the charge belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Document number allocated from document_sequences. UNIQUE across all
    -- charges.
    charge_no VARCHAR(50) NOT NULL,
    -- Document kind (SERVICE_NOTE, PROFORMA_INVOICE, TAX_INVOICE,
    -- CREDIT_NOTE).
    document_type VARCHAR(32) NOT NULL,
    -- Date printed on the document.
    document_date DATE NOT NULL,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Charge lifecycle state (DRAFT, ISSUED, SENT, PAID, VOID). Indexed
    -- because the charges list filters on it.
    status VARCHAR(20) NOT NULL,
    -- Sum of line amounts before discount and tax.
    subtotal_amount NUMERIC(19, 4) NOT NULL,
    -- Total discount applied across all charge lines.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Total tax (VAT) charged across all charge lines.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Payable total: subtotal minus discount plus tax.
    total_amount NUMERIC(19, 4) NOT NULL,
    -- Free-text remark printed at the foot of the document.
    remark TEXT,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_charges PRIMARY KEY (id),
    CONSTRAINT uq_service_order_charges_no UNIQUE (charge_no),
    CONSTRAINT fk_service_order_charges_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_charges_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_order_charges_service_order_id ON service_order_charges (service_order_id);
CREATE INDEX ix_service_order_charges_status ON service_order_charges (status);

COMMENT ON TABLE service_order_charges IS 'Customer-facing invoice or service note raised from a service order.';
COMMENT ON COLUMN service_order_charges.service_order_id IS 'Service order the charge belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_charges.charge_no IS 'Document number allocated from document_sequences. UNIQUE across all charges.';
COMMENT ON COLUMN service_order_charges.document_type IS 'Document kind (SERVICE_NOTE, PROFORMA_INVOICE, TAX_INVOICE, CREDIT_NOTE).';
COMMENT ON COLUMN service_order_charges.document_date IS 'Date printed on the document.';
COMMENT ON COLUMN service_order_charges.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN service_order_charges.status IS 'Charge lifecycle state (DRAFT, ISSUED, SENT, PAID, VOID). Indexed because the charges list filters on it.';
COMMENT ON COLUMN service_order_charges.subtotal_amount IS 'Sum of line amounts before discount and tax.';
COMMENT ON COLUMN service_order_charges.discount_amount IS 'Total discount applied across all charge lines.';
COMMENT ON COLUMN service_order_charges.tax_amount IS 'Total tax (VAT) charged across all charge lines.';
COMMENT ON COLUMN service_order_charges.total_amount IS 'Payable total: subtotal minus discount plus tax.';
COMMENT ON COLUMN service_order_charges.remark IS 'Free-text remark printed at the foot of the document.';
COMMENT ON COLUMN service_order_charges.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN service_order_charges.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN service_order_charges.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_charges.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_charges.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_component_rows
-- Module: Service Operations  [app.modules.operations.models]
-- One row of a table-mode component group, or the single record of a
-- form-mode group. Values are stored as JSON keyed by the attribute code, so
-- changing a group's attributes never requires a schema migration.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_component_rows (
    -- Service order the row belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Component group this row renders. CASCADE on group deletion.
    group_id BIGINT NOT NULL,
    -- Position of this row within its group. NULL for rows written directly.
    row_no INTEGER NOT NULL,
    -- TRUE when the record has been withdrawn. Archived records are hidden
    -- from pickers but retained so historical documents still resolve.
    is_archived BOOLEAN NOT NULL,
    -- JSONB map of attribute code to entered value. Keyed by
    -- component_attributes.code so that changing a group's attributes needs
    -- no migration.
    values JSONB NOT NULL,
    -- Configuration version in force when the row was written, so a later
    -- configuration change never invalidates a saved row: it is still
    -- interpreted against the layout and rules it was captured under.
    config_version_id BIGINT,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- Identifier of the user who last updated this record. NULL when the
    -- action was performed by the system, or set to NULL by ON DELETE SET
    -- NULL once the user is removed.
    updated_by_user_id BIGINT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_component_rows PRIMARY KEY (id),
    CONSTRAINT fk_service_order_component_rows_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_component_rows_group_id_component_groups FOREIGN KEY(group_id) REFERENCES component_groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_component_rows_config_version_id_confi_1420 FOREIGN KEY(config_version_id) REFERENCES configuration_versions (id) ON DELETE SET NULL,
    CONSTRAINT fk_service_order_component_rows_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_service_order_component_rows_updated_by_user_id_users FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_order_component_rows_group_id ON service_order_component_rows (group_id);
CREATE INDEX ix_service_order_component_rows_service_order_id ON service_order_component_rows (service_order_id);

COMMENT ON TABLE service_order_component_rows IS 'One row of a table-mode component group, or the single record of a form-mode group. Values are stored as JSON keyed by the attribute code, so changing a group''s attributes never requires a schema migration.';
COMMENT ON COLUMN service_order_component_rows.service_order_id IS 'Service order the row belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_component_rows.group_id IS 'Component group this row renders. CASCADE on group deletion.';
COMMENT ON COLUMN service_order_component_rows.row_no IS 'Position of this row within its group. NULL for rows written directly.';
COMMENT ON COLUMN service_order_component_rows.is_archived IS 'TRUE when the record has been withdrawn. Archived records are hidden from pickers but retained so historical documents still resolve.';
COMMENT ON COLUMN service_order_component_rows.values IS 'JSONB map of attribute code to entered value. Keyed by component_attributes.code so that changing a group''s attributes needs no migration.';
COMMENT ON COLUMN service_order_component_rows.config_version_id IS 'Configuration version in force when the row was written, so a later configuration change never invalidates a saved row: it is still interpreted against the layout and rules it was captured under.';
COMMENT ON COLUMN service_order_component_rows.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN service_order_component_rows.updated_by_user_id IS 'Identifier of the user who last updated this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN service_order_component_rows.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_component_rows.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_component_rows.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_container_requirements
-- Module: Service Operations  [app.modules.operations.models]
-- Container the customer has booked, before actual units are assigned to the
-- job.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_container_requirements (
    -- Service order the requirement belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Quotation container requirement this line was converted from, or NULL
    -- when it was added directly.
    source_quotation_container_id BIGINT,
    -- Container type being booked.
    container_type_id BIGINT NOT NULL,
    -- Number of containers of this type booked (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Expected gross weight per container in kilograms.
    gross_weight_kg NUMERIC(12, 3),
    -- Short description of the requirement.
    description TEXT,
    -- Free-text remarks about the requirement.
    remarks TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_service_order_container_requirements PRIMARY KEY (id),
    CONSTRAINT fk_service_order_container_requirements_service_order_i_2728 FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_container_requirements_source_quotatio_1946 FOREIGN KEY(source_quotation_container_id) REFERENCES quotation_revision_containers (id),
    CONSTRAINT fk_service_order_container_requirements_container_type__3695 FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_service_order_container_requirements_service_order_id ON service_order_container_requirements (service_order_id);

COMMENT ON TABLE service_order_container_requirements IS 'Container the customer has booked, before actual units are assigned to the job.';
COMMENT ON COLUMN service_order_container_requirements.service_order_id IS 'Service order the requirement belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_container_requirements.source_quotation_container_id IS 'Quotation container requirement this line was converted from, or NULL when it was added directly.';
COMMENT ON COLUMN service_order_container_requirements.container_type_id IS 'Container type being booked.';
COMMENT ON COLUMN service_order_container_requirements.quantity IS 'Number of containers of this type booked (NUMERIC(12,3)).';
COMMENT ON COLUMN service_order_container_requirements.gross_weight_kg IS 'Expected gross weight per container in kilograms.';
COMMENT ON COLUMN service_order_container_requirements.description IS 'Short description of the requirement.';
COMMENT ON COLUMN service_order_container_requirements.remarks IS 'Free-text remarks about the requirement.';
COMMENT ON COLUMN service_order_container_requirements.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: service_order_milestones
-- Module: Service Operations  [app.modules.operations.models]
-- Checkpoint on a service order's timeline (booking confirmed, gate-in,
-- loaded, arrived).
-- --------------------------------------------------------------------------
CREATE TABLE service_order_milestones (
    -- Service order the milestone belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Stable machine code for the checkpoint (e.g. GATE_IN), used to drive
    -- progress reporting.
    milestone_code VARCHAR(64) NOT NULL,
    -- Display name of the checkpoint as printed on the order.
    milestone_name VARCHAR(255) NOT NULL,
    -- Order of this checkpoint along the timeline.
    sequence_no INTEGER NOT NULL,
    -- Scheduled time of the checkpoint (UTC, timezone-aware).
    planned_at TIMESTAMP WITH TIME ZONE,
    -- Recorded time the checkpoint was reached.
    actual_at TIMESTAMP WITH TIME ZONE,
    -- Checkpoint state (PENDING, DONE, MISSED, SKIPPED).
    status VARCHAR(20) NOT NULL,
    -- Free-text notes about the checkpoint.
    notes TEXT,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_milestones PRIMARY KEY (id),
    CONSTRAINT fk_service_order_milestones_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE
);
CREATE INDEX ix_service_order_milestones_service_order_id ON service_order_milestones (service_order_id);

COMMENT ON TABLE service_order_milestones IS 'Checkpoint on a service order''s timeline (booking confirmed, gate-in, loaded, arrived).';
COMMENT ON COLUMN service_order_milestones.service_order_id IS 'Service order the milestone belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_milestones.milestone_code IS 'Stable machine code for the checkpoint (e.g. GATE_IN), used to drive progress reporting.';
COMMENT ON COLUMN service_order_milestones.milestone_name IS 'Display name of the checkpoint as printed on the order.';
COMMENT ON COLUMN service_order_milestones.sequence_no IS 'Order of this checkpoint along the timeline.';
COMMENT ON COLUMN service_order_milestones.planned_at IS 'Scheduled time of the checkpoint (UTC, timezone-aware).';
COMMENT ON COLUMN service_order_milestones.actual_at IS 'Recorded time the checkpoint was reached.';
COMMENT ON COLUMN service_order_milestones.status IS 'Checkpoint state (PENDING, DONE, MISSED, SKIPPED).';
COMMENT ON COLUMN service_order_milestones.notes IS 'Free-text notes about the checkpoint.';
COMMENT ON COLUMN service_order_milestones.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN service_order_milestones.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_milestones.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_milestones.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_movements
-- Module: Service Operations  [app.modules.operations.models]
-- Planned versus actual movement leg of a service order.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_movements (
    -- Service order the movement leg belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Order of this leg along the shipment itinerary.
    sequence_no INTEGER NOT NULL,
    -- Mode of transport used for this leg.
    transport_type_id BIGINT,
    -- Specific vehicle, vessel or aircraft performing the leg.
    transport_asset_id BIGINT,
    -- Legacy Places reference for the origin of the leg. Retained for
    -- historical rows; the movement data snapshot carries the printable
    -- origin text.
    origin_place_id BIGINT,
    -- Legacy Places reference for the destination of the leg. Retained for
    -- historical rows; the movement data snapshot carries the printable
    -- destination text.
    destination_place_id BIGINT,
    -- Scheduled departure (UTC, timezone-aware).
    planned_departure TIMESTAMP WITH TIME ZONE,
    -- Recorded departure. NULL until the leg actually departs.
    actual_departure TIMESTAMP WITH TIME ZONE,
    -- Scheduled arrival (UTC, timezone-aware).
    planned_arrival TIMESTAMP WITH TIME ZONE,
    -- Recorded arrival. NULL until the leg actually arrives.
    actual_arrival TIMESTAMP WITH TIME ZONE,
    -- Movement lifecycle state (PLANNED, IN_TRANSIT, ARRIVED, CANCELLED).
    status VARCHAR(32) NOT NULL,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_movements PRIMARY KEY (id),
    CONSTRAINT fk_service_order_movements_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_movements_transport_type_id_transport_types FOREIGN KEY(transport_type_id) REFERENCES transport_types (id),
    CONSTRAINT fk_service_order_movements_transport_asset_id_transport_assets FOREIGN KEY(transport_asset_id) REFERENCES transport_assets (id),
    CONSTRAINT fk_service_order_movements_origin_place_id_places FOREIGN KEY(origin_place_id) REFERENCES places (id),
    CONSTRAINT fk_service_order_movements_destination_place_id_places FOREIGN KEY(destination_place_id) REFERENCES places (id)
);
CREATE INDEX ix_service_order_movements_service_order_id ON service_order_movements (service_order_id);

COMMENT ON TABLE service_order_movements IS 'Planned versus actual movement leg of a service order.';
COMMENT ON COLUMN service_order_movements.service_order_id IS 'Service order the movement leg belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_movements.sequence_no IS 'Order of this leg along the shipment itinerary.';
COMMENT ON COLUMN service_order_movements.transport_type_id IS 'Mode of transport used for this leg.';
COMMENT ON COLUMN service_order_movements.transport_asset_id IS 'Specific vehicle, vessel or aircraft performing the leg.';
COMMENT ON COLUMN service_order_movements.origin_place_id IS 'Legacy Places reference for the origin of the leg. Retained for historical rows; the movement data snapshot carries the printable origin text.';
COMMENT ON COLUMN service_order_movements.destination_place_id IS 'Legacy Places reference for the destination of the leg. Retained for historical rows; the movement data snapshot carries the printable destination text.';
COMMENT ON COLUMN service_order_movements.planned_departure IS 'Scheduled departure (UTC, timezone-aware).';
COMMENT ON COLUMN service_order_movements.actual_departure IS 'Recorded departure. NULL until the leg actually departs.';
COMMENT ON COLUMN service_order_movements.planned_arrival IS 'Scheduled arrival (UTC, timezone-aware).';
COMMENT ON COLUMN service_order_movements.actual_arrival IS 'Recorded arrival. NULL until the leg actually arrives.';
COMMENT ON COLUMN service_order_movements.status IS 'Movement lifecycle state (PLANNED, IN_TRANSIT, ARRIVED, CANCELLED).';
COMMENT ON COLUMN service_order_movements.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN service_order_movements.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_movements.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_movements.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_places
-- Module: Service Operations  [app.modules.operations.models]
-- Routing stop attached to a service order.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_places (
    -- Service order the stop belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Configured Place Role the stop plays. Copied from the quotation on
    -- conversion, then independent; SET NULL only if the role row is purged.
    place_role_id BIGINT,
    -- Legacy Places reference retained for historical service-order stops.
    -- New writes use the role and free_text snapshot; NULL when no place was
    -- selected.
    place_id BIGINT,
    -- Text snapshot of the role at save time. Preserved so a route still
    -- prints after the role is renamed or deactivated.
    place_role VARCHAR(32) NOT NULL,
    -- Position of this stop within the route. Unique per order; the server
    -- renumbers from the submitted row order.
    sequence_no INTEGER NOT NULL,
    -- Planned date/time for the stop.
    planned_at TIMESTAMP WITH TIME ZONE,
    -- Actual date/time the stop was served, when known.
    actual_at TIMESTAMP WITH TIME ZONE,
    -- Free-text location typed for the stop, kept for printing and history.
    free_text TEXT,
    -- TRUE when actual_at is set, i.e. the stop has actually been served.
    -- Kept for reports written before actual_at existed.
    is_actual BOOLEAN NOT NULL,
    -- Free-text notes about this stop.
    notes TEXT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_service_order_places PRIMARY KEY (id),
    CONSTRAINT uq_service_order_places_sequence UNIQUE (service_order_id, sequence_no),
    CONSTRAINT fk_service_order_places_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_places_place_role_id_place_roles FOREIGN KEY(place_role_id) REFERENCES place_roles (id) ON DELETE SET NULL,
    CONSTRAINT fk_service_order_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id)
);
CREATE INDEX ix_service_order_places_service_order_id ON service_order_places (service_order_id);

COMMENT ON TABLE service_order_places IS 'Routing stop attached to a service order.';
COMMENT ON COLUMN service_order_places.service_order_id IS 'Service order the stop belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_places.place_role_id IS 'Configured Place Role the stop plays. Copied from the quotation on conversion, then independent; SET NULL only if the role row is purged.';
COMMENT ON COLUMN service_order_places.place_id IS 'Legacy Places reference retained for historical service-order stops. New writes use the role and free_text snapshot; NULL when no place was selected.';
COMMENT ON COLUMN service_order_places.place_role IS 'Text snapshot of the role at save time. Preserved so a route still prints after the role is renamed or deactivated.';
COMMENT ON COLUMN service_order_places.sequence_no IS 'Position of this stop within the route. Unique per order; the server renumbers from the submitted row order.';
COMMENT ON COLUMN service_order_places.planned_at IS 'Planned date/time for the stop.';
COMMENT ON COLUMN service_order_places.actual_at IS 'Actual date/time the stop was served, when known.';
COMMENT ON COLUMN service_order_places.free_text IS 'Free-text location typed for the stop, kept for printing and history.';
COMMENT ON COLUMN service_order_places.is_actual IS 'TRUE when actual_at is set, i.e. the stop has actually been served. Kept for reports written before actual_at existed.';
COMMENT ON COLUMN service_order_places.notes IS 'Free-text notes about this stop.';
COMMENT ON COLUMN service_order_places.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: service_order_pricing
-- Module: Service Operations  [app.modules.operations.models]
-- Pricing summary of a service order. Exactly one row per order, enforced by
-- the unique constraint on service_order_id.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_pricing (
    -- Service order this summary belongs to. UNIQUE, so an order always has
    -- exactly one pricing summary.
    service_order_id BIGINT NOT NULL,
    -- Sum of line subtotals before discount and tax.
    subtotal_amount NUMERIC(19, 4) NOT NULL,
    -- Total discount applied across all pricing lines.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Total tax (VAT) charged across all pricing lines.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Payable total: subtotal minus discount plus tax.
    total_amount NUMERIC(19, 4) NOT NULL,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_pricing PRIMARY KEY (id),
    CONSTRAINT uq_service_order_pricing_service_order_id UNIQUE (service_order_id),
    CONSTRAINT fk_service_order_pricing_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE
);

COMMENT ON TABLE service_order_pricing IS 'Pricing summary of a service order. Exactly one row per order, enforced by the unique constraint on service_order_id.';
COMMENT ON COLUMN service_order_pricing.service_order_id IS 'Service order this summary belongs to. UNIQUE, so an order always has exactly one pricing summary.';
COMMENT ON COLUMN service_order_pricing.subtotal_amount IS 'Sum of line subtotals before discount and tax.';
COMMENT ON COLUMN service_order_pricing.discount_amount IS 'Total discount applied across all pricing lines.';
COMMENT ON COLUMN service_order_pricing.tax_amount IS 'Total tax (VAT) charged across all pricing lines.';
COMMENT ON COLUMN service_order_pricing.total_amount IS 'Payable total: subtotal minus discount plus tax.';
COMMENT ON COLUMN service_order_pricing.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN service_order_pricing.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_pricing.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_pricing.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: financial_document_allocations
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Applies part of a payment document to an open invoice (or a payment against
-- a credit). This is what makes partial settlement and multi-invoice payments
-- possible.
-- --------------------------------------------------------------------------
CREATE TABLE financial_document_allocations (
    -- Payment or receipt document that holds the money.
    payment_document_id BIGINT NOT NULL,
    -- Open document the money is applied to (an invoice or a credit).
    target_document_id BIGINT NOT NULL,
    -- Amount of the payment applied to target_document_id.
    allocated_amount NUMERIC(19, 4) NOT NULL,
    -- ISO 4217 code of allocated_amount, which may differ from either
    -- document.
    allocated_currency_code VARCHAR(3) NOT NULL,
    -- Rate used to convert allocated_currency_code into the base currency.
    exchange_rate NUMERIC(19, 8) NOT NULL,
    -- Timestamp the allocation was applied.
    allocated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- UNIQUE key that makes a repeated allocation request a no-op. This is
    -- what stops a retried request from double-settling an invoice.
    idempotency_key VARCHAR(128),
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_financial_document_allocations PRIMARY KEY (id),
    CONSTRAINT fk_financial_document_allocations_payment_document_id_f_f494 FOREIGN KEY(payment_document_id) REFERENCES financial_documents (id),
    CONSTRAINT fk_financial_document_allocations_target_document_id_fi_faa8 FOREIGN KEY(target_document_id) REFERENCES financial_documents (id),
    CONSTRAINT fk_financial_document_allocations_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id),
    CONSTRAINT uq_financial_document_allocations_idempotency_key UNIQUE (idempotency_key)
);
CREATE INDEX ix_financial_document_allocations_payment_document_id ON financial_document_allocations (payment_document_id);
CREATE INDEX ix_financial_document_allocations_target_document_id ON financial_document_allocations (target_document_id);

COMMENT ON TABLE financial_document_allocations IS 'Applies part of a payment document to an open invoice (or a payment against a credit). This is what makes partial settlement and multi-invoice payments possible.';
COMMENT ON COLUMN financial_document_allocations.payment_document_id IS 'Payment or receipt document that holds the money.';
COMMENT ON COLUMN financial_document_allocations.target_document_id IS 'Open document the money is applied to (an invoice or a credit).';
COMMENT ON COLUMN financial_document_allocations.allocated_amount IS 'Amount of the payment applied to target_document_id.';
COMMENT ON COLUMN financial_document_allocations.allocated_currency_code IS 'ISO 4217 code of allocated_amount, which may differ from either document.';
COMMENT ON COLUMN financial_document_allocations.exchange_rate IS 'Rate used to convert allocated_currency_code into the base currency.';
COMMENT ON COLUMN financial_document_allocations.allocated_at IS 'Timestamp the allocation was applied.';
COMMENT ON COLUMN financial_document_allocations.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN financial_document_allocations.idempotency_key IS 'UNIQUE key that makes a repeated allocation request a no-op. This is what stops a retried request from double-settling an invoice.';
COMMENT ON COLUMN financial_document_allocations.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: financial_document_sources
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Tracks which business record generated a financial document, so a service
-- order or quotation can be traced to the invoices it produced.
-- --------------------------------------------------------------------------
CREATE TABLE financial_document_sources (
    -- Document generated from the source record. CASCADE on deletion.
    financial_document_id BIGINT NOT NULL,
    -- Table name of the source record, for example 'service_orders'.
    source_type VARCHAR(64) NOT NULL,
    -- Primary key of the source record, resolved together with source_type.
    -- Deliberately not a foreign key, because the source may live in any
    -- table.
    source_id BIGINT NOT NULL,
    -- How the source relates to the document: GENERATED_FROM, REFERENCES or
    -- SUPERSEDES.
    relationship_type VARCHAR(32) NOT NULL,
    -- Timestamp the link was created.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_financial_document_sources PRIMARY KEY (id),
    CONSTRAINT uq_fin_doc_sources UNIQUE (financial_document_id, source_type, source_id, relationship_type),
    CONSTRAINT fk_financial_document_sources_financial_document_id_fin_5efa FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id) ON DELETE CASCADE
);
CREATE INDEX ix_financial_document_sources_financial_document_id ON financial_document_sources (financial_document_id);

COMMENT ON TABLE financial_document_sources IS 'Tracks which business record generated a financial document, so a service order or quotation can be traced to the invoices it produced.';
COMMENT ON COLUMN financial_document_sources.financial_document_id IS 'Document generated from the source record. CASCADE on deletion.';
COMMENT ON COLUMN financial_document_sources.source_type IS 'Table name of the source record, for example ''service_orders''.';
COMMENT ON COLUMN financial_document_sources.source_id IS 'Primary key of the source record, resolved together with source_type. Deliberately not a foreign key, because the source may live in any table.';
COMMENT ON COLUMN financial_document_sources.relationship_type IS 'How the source relates to the document: GENERATED_FROM, REFERENCES or SUPERSEDES.';
COMMENT ON COLUMN financial_document_sources.created_at IS 'Timestamp the link was created.';
COMMENT ON COLUMN financial_document_sources.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: journal_entries
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Journal entry header. Every posted financial document produces one. Entries
-- are immutable once posted and are corrected by reversal, never by editing.
-- --------------------------------------------------------------------------
CREATE TABLE journal_entries (
    -- Journal entry number allocated from document_sequences. Unique.
    entry_no VARCHAR(50) NOT NULL,
    -- MANUAL, or the document type that generated the entry automatically.
    entry_type VARCHAR(64) NOT NULL,
    -- Date the entry is recorded as having occurred.
    entry_date DATE NOT NULL,
    -- Date the entry hit the ledger; selects the accounting period.
    posting_date DATE NOT NULL,
    -- Accounting period the entry was posted into.
    accounting_period_id BIGINT,
    -- Entry state (DRAFT, POSTED, REVERSED). Indexed because posting filters
    -- on it.
    status VARCHAR(20) NOT NULL,
    -- Narrative describing the entry.
    description TEXT,
    -- Financial document that generated this entry automatically.
    source_document_id BIGINT,
    -- Posting rule that resolved this entry's accounts, snapshotted at post
    -- time. Has no ON DELETE action: a rule that posted something may be
    -- deactivated but never deleted, or the attribution would be lost. NULL
    -- for a manual journal.
    posting_rule_id BIGINT,
    -- Entry being reversed. Set on the reversing entry and NULL on originals.
    reversal_of_journal_entry_id BIGINT,
    -- Identifier of the user who created this record. NULL when the action
    -- was performed by the system, or set to NULL by ON DELETE SET NULL once
    -- the user is removed.
    created_by_user_id BIGINT,
    -- Identifier of the user who posted this record. NULL when the action was
    -- performed by the system, or set to NULL by ON DELETE SET NULL once the
    -- user is removed.
    posted_by_user_id BIGINT,
    -- Timestamp the entry was posted to the ledger.
    posted_at TIMESTAMP WITH TIME ZONE,
    -- Sum of debit lines. Must equal credit_total before the entry may be
    -- posted — this is the double-entry balance check.
    debit_total NUMERIC(19, 4) NOT NULL,
    -- Sum of credit lines. Must equal debit_total before posting.
    credit_total NUMERIC(19, 4) NOT NULL,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_journal_entries PRIMARY KEY (id),
    CONSTRAINT uq_journal_entries_no UNIQUE (entry_no),
    CONSTRAINT fk_journal_entries_accounting_period_id_accounting_periods FOREIGN KEY(accounting_period_id) REFERENCES accounting_periods (id),
    CONSTRAINT fk_journal_entries_source_document_id_financial_documents FOREIGN KEY(source_document_id) REFERENCES financial_documents (id),
    CONSTRAINT fk_journal_entries_posting_rule_id_posting_rules FOREIGN KEY(posting_rule_id) REFERENCES posting_rules (id),
    CONSTRAINT fk_journal_entries_reversal_of_journal_entry_id_journal_entries FOREIGN KEY(reversal_of_journal_entry_id) REFERENCES journal_entries (id),
    CONSTRAINT fk_journal_entries_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id),
    CONSTRAINT fk_journal_entries_posted_by_user_id_users FOREIGN KEY(posted_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_journal_entries_posting_rule_id ON journal_entries (posting_rule_id);
CREATE INDEX ix_journal_entries_status ON journal_entries (status);

COMMENT ON TABLE journal_entries IS 'Journal entry header. Every posted financial document produces one. Entries are immutable once posted and are corrected by reversal, never by editing.';
COMMENT ON COLUMN journal_entries.entry_no IS 'Journal entry number allocated from document_sequences. Unique.';
COMMENT ON COLUMN journal_entries.entry_type IS 'MANUAL, or the document type that generated the entry automatically.';
COMMENT ON COLUMN journal_entries.entry_date IS 'Date the entry is recorded as having occurred.';
COMMENT ON COLUMN journal_entries.posting_date IS 'Date the entry hit the ledger; selects the accounting period.';
COMMENT ON COLUMN journal_entries.accounting_period_id IS 'Accounting period the entry was posted into.';
COMMENT ON COLUMN journal_entries.status IS 'Entry state (DRAFT, POSTED, REVERSED). Indexed because posting filters on it.';
COMMENT ON COLUMN journal_entries.description IS 'Narrative describing the entry.';
COMMENT ON COLUMN journal_entries.source_document_id IS 'Financial document that generated this entry automatically.';
COMMENT ON COLUMN journal_entries.posting_rule_id IS 'Posting rule that resolved this entry''s accounts, snapshotted at post time. Has no ON DELETE action: a rule that posted something may be deactivated but never deleted, or the attribution would be lost. NULL for a manual journal.';
COMMENT ON COLUMN journal_entries.reversal_of_journal_entry_id IS 'Entry being reversed. Set on the reversing entry and NULL on originals.';
COMMENT ON COLUMN journal_entries.created_by_user_id IS 'Identifier of the user who created this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN journal_entries.posted_by_user_id IS 'Identifier of the user who posted this record. NULL when the action was performed by the system, or set to NULL by ON DELETE SET NULL once the user is removed.';
COMMENT ON COLUMN journal_entries.posted_at IS 'Timestamp the entry was posted to the ledger.';
COMMENT ON COLUMN journal_entries.debit_total IS 'Sum of debit lines. Must equal credit_total before the entry may be posted — this is the double-entry balance check.';
COMMENT ON COLUMN journal_entries.credit_total IS 'Sum of credit lines. Must equal debit_total before posting.';
COMMENT ON COLUMN journal_entries.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN journal_entries.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN journal_entries.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN journal_entries.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_containers
-- Module: Service Operations  [app.modules.operations.models]
-- An actual physical container on the job, with its seal, weights and
-- pickup/return dates.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_containers (
    -- Service order the container belongs to. CASCADE on order deletion.
    service_order_id BIGINT NOT NULL,
    -- Booked requirement this actual container fulfils, or NULL when it was
    -- not planned.
    container_requirement_id BIGINT,
    -- Container type of the actual unit.
    container_type_id BIGINT NOT NULL,
    -- ISO 6346 container number printed on the box. UNIQUE across the system,
    -- so a unit cannot be booked twice.
    container_number VARCHAR(32) NOT NULL,
    -- Seal number recorded at stuffing or gate-in.
    seal_serial VARCHAR(64),
    -- Container lifecycle state (EXPECTED, STUFFED, GATE_IN, GATE_OUT,
    -- DEVOURED, RETURNED).
    status VARCHAR(32) NOT NULL,
    -- Net (cargo) weight in kilograms (NUMERIC(12,3)).
    net_weight_kg NUMERIC(12, 3),
    -- Gross (tare plus cargo) weight in kilograms (NUMERIC(12,3)).
    gross_weight_kg NUMERIC(12, 3),
    -- Date the container is collected.
    pickup_date DATE,
    -- Date the empty container is returned.
    return_date DATE,
    -- JSONB payload for module-specific fields not covered by dedicated
    -- columns.
    data JSONB NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    -- Row creation timestamp (UTC, timezone-aware). Written once; server
    -- default now().
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Last modification timestamp (UTC, timezone-aware). Refreshed by the
    -- application on every update.
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_service_order_containers PRIMARY KEY (id),
    CONSTRAINT uq_service_order_containers_number UNIQUE (container_number),
    CONSTRAINT fk_service_order_containers_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_containers_container_requirement_id_se_2d3c FOREIGN KEY(container_requirement_id) REFERENCES service_order_container_requirements (id),
    CONSTRAINT fk_service_order_containers_container_type_id_container_types FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_service_order_containers_service_order_id ON service_order_containers (service_order_id);

COMMENT ON TABLE service_order_containers IS 'An actual physical container on the job, with its seal, weights and pickup/return dates.';
COMMENT ON COLUMN service_order_containers.service_order_id IS 'Service order the container belongs to. CASCADE on order deletion.';
COMMENT ON COLUMN service_order_containers.container_requirement_id IS 'Booked requirement this actual container fulfils, or NULL when it was not planned.';
COMMENT ON COLUMN service_order_containers.container_type_id IS 'Container type of the actual unit.';
COMMENT ON COLUMN service_order_containers.container_number IS 'ISO 6346 container number printed on the box. UNIQUE across the system, so a unit cannot be booked twice.';
COMMENT ON COLUMN service_order_containers.seal_serial IS 'Seal number recorded at stuffing or gate-in.';
COMMENT ON COLUMN service_order_containers.status IS 'Container lifecycle state (EXPECTED, STUFFED, GATE_IN, GATE_OUT, DEVOURED, RETURNED).';
COMMENT ON COLUMN service_order_containers.net_weight_kg IS 'Net (cargo) weight in kilograms (NUMERIC(12,3)).';
COMMENT ON COLUMN service_order_containers.gross_weight_kg IS 'Gross (tare plus cargo) weight in kilograms (NUMERIC(12,3)).';
COMMENT ON COLUMN service_order_containers.pickup_date IS 'Date the container is collected.';
COMMENT ON COLUMN service_order_containers.return_date IS 'Date the empty container is returned.';
COMMENT ON COLUMN service_order_containers.data IS 'JSONB payload for module-specific fields not covered by dedicated columns.';
COMMENT ON COLUMN service_order_containers.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';
COMMENT ON COLUMN service_order_containers.created_at IS 'Row creation timestamp (UTC, timezone-aware). Written once; server default now().';
COMMENT ON COLUMN service_order_containers.updated_at IS 'Last modification timestamp (UTC, timezone-aware). Refreshed by the application on every update.';

-- --------------------------------------------------------------------------
-- Table: service_order_pricing_lines
-- Module: Service Operations  [app.modules.operations.models]
-- Individual priced line of a service order.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_pricing_lines (
    -- Pricing summary the line belongs to. CASCADE on summary deletion.
    service_order_pricing_id BIGINT NOT NULL,
    -- Sequential line number within the parent document, 1-based and
    -- displayed in order.
    line_no INTEGER NOT NULL,
    -- Quotation price line this line was converted from, or NULL when priced
    -- directly.
    source_quotation_line_id BIGINT,
    -- Catalogue fee priced by this line.
    fee_type_id BIGINT,
    -- Description printed on the order for this line.
    description TEXT NOT NULL,
    -- Billed quantity (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG,
    -- PERCENT).
    unit_code VARCHAR(32),
    -- Price per unit in currency_code, before discount and tax.
    unit_price NUMERIC(19, 4) NOT NULL,
    -- Discount applied to the line as a rate (NUMERIC(7,4)).
    discount_rate NUMERIC(7, 4) NOT NULL,
    -- Tax/VAT rate applied to the line (NUMERIC(7,4)).
    tax_rate NUMERIC(7, 4) NOT NULL,
    -- Final payable amount for this line.
    line_total NUMERIC(19, 4) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_service_order_pricing_lines PRIMARY KEY (id),
    CONSTRAINT uq_so_pricing_lines_no UNIQUE (service_order_pricing_id, line_no),
    CONSTRAINT fk_service_order_pricing_lines_service_order_pricing_id_b7cf FOREIGN KEY(service_order_pricing_id) REFERENCES service_order_pricing (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_pricing_lines_source_quotation_line_id_9a37 FOREIGN KEY(source_quotation_line_id) REFERENCES quotation_revision_lines (id),
    CONSTRAINT fk_service_order_pricing_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id)
);
CREATE INDEX ix_service_order_pricing_lines_service_order_pricing_id ON service_order_pricing_lines (service_order_pricing_id);

COMMENT ON TABLE service_order_pricing_lines IS 'Individual priced line of a service order.';
COMMENT ON COLUMN service_order_pricing_lines.service_order_pricing_id IS 'Pricing summary the line belongs to. CASCADE on summary deletion.';
COMMENT ON COLUMN service_order_pricing_lines.line_no IS 'Sequential line number within the parent document, 1-based and displayed in order.';
COMMENT ON COLUMN service_order_pricing_lines.source_quotation_line_id IS 'Quotation price line this line was converted from, or NULL when priced directly.';
COMMENT ON COLUMN service_order_pricing_lines.fee_type_id IS 'Catalogue fee priced by this line.';
COMMENT ON COLUMN service_order_pricing_lines.description IS 'Description printed on the order for this line.';
COMMENT ON COLUMN service_order_pricing_lines.quantity IS 'Billed quantity (NUMERIC(12,3)).';
COMMENT ON COLUMN service_order_pricing_lines.unit_code IS 'Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG, PERCENT).';
COMMENT ON COLUMN service_order_pricing_lines.unit_price IS 'Price per unit in currency_code, before discount and tax.';
COMMENT ON COLUMN service_order_pricing_lines.discount_rate IS 'Discount applied to the line as a rate (NUMERIC(7,4)).';
COMMENT ON COLUMN service_order_pricing_lines.tax_rate IS 'Tax/VAT rate applied to the line (NUMERIC(7,4)).';
COMMENT ON COLUMN service_order_pricing_lines.line_total IS 'Final payable amount for this line.';
COMMENT ON COLUMN service_order_pricing_lines.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: financial_document_lines
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Line of a financial document.
-- --------------------------------------------------------------------------
CREATE TABLE financial_document_lines (
    -- Document the line belongs to. CASCADE on document deletion.
    financial_document_id BIGINT NOT NULL,
    -- Sequential line number within the parent document, 1-based and
    -- displayed in order.
    line_no INTEGER NOT NULL,
    -- Description printed on the document for this line.
    description TEXT NOT NULL,
    -- Catalogue fee billed by this line.
    fee_type_id BIGINT,
    -- Billed quantity (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG,
    -- PERCENT).
    unit_code VARCHAR(32),
    -- Price per unit in currency_code, before discount and tax.
    unit_price NUMERIC(19, 4) NOT NULL,
    -- Absolute discount deducted from the line subtotal.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Tax/VAT rate applied to the line (NUMERIC(7,4)).
    tax_rate NUMERIC(7, 4) NOT NULL,
    -- Absolute tax charged on this line.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Final payable amount for this line.
    line_amount NUMERIC(19, 4) NOT NULL,
    -- Service order the line is attributed to.
    service_order_id BIGINT,
    -- Container the line is attributed to, for per-container billing.
    service_order_container_id BIGINT,
    -- General-ledger account this line posts to. When set it overrides the
    -- posting rule, which is how ad-hoc accounts are supported.
    account_id BIGINT,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_financial_document_lines PRIMARY KEY (id),
    CONSTRAINT uq_financial_document_lines_no UNIQUE (financial_document_id, line_no),
    CONSTRAINT fk_financial_document_lines_financial_document_id_finan_20b9 FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id) ON DELETE CASCADE,
    CONSTRAINT fk_financial_document_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id),
    CONSTRAINT fk_financial_document_lines_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id),
    CONSTRAINT fk_financial_document_lines_service_order_container_id__95a0 FOREIGN KEY(service_order_container_id) REFERENCES service_order_containers (id),
    CONSTRAINT fk_financial_document_lines_account_id_chart_of_accounts FOREIGN KEY(account_id) REFERENCES chart_of_accounts (id)
);
CREATE INDEX ix_financial_document_lines_financial_document_id ON financial_document_lines (financial_document_id);

COMMENT ON TABLE financial_document_lines IS 'Line of a financial document.';
COMMENT ON COLUMN financial_document_lines.financial_document_id IS 'Document the line belongs to. CASCADE on document deletion.';
COMMENT ON COLUMN financial_document_lines.line_no IS 'Sequential line number within the parent document, 1-based and displayed in order.';
COMMENT ON COLUMN financial_document_lines.description IS 'Description printed on the document for this line.';
COMMENT ON COLUMN financial_document_lines.fee_type_id IS 'Catalogue fee billed by this line.';
COMMENT ON COLUMN financial_document_lines.quantity IS 'Billed quantity (NUMERIC(12,3)).';
COMMENT ON COLUMN financial_document_lines.unit_code IS 'Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG, PERCENT).';
COMMENT ON COLUMN financial_document_lines.unit_price IS 'Price per unit in currency_code, before discount and tax.';
COMMENT ON COLUMN financial_document_lines.discount_amount IS 'Absolute discount deducted from the line subtotal.';
COMMENT ON COLUMN financial_document_lines.tax_rate IS 'Tax/VAT rate applied to the line (NUMERIC(7,4)).';
COMMENT ON COLUMN financial_document_lines.tax_amount IS 'Absolute tax charged on this line.';
COMMENT ON COLUMN financial_document_lines.line_amount IS 'Final payable amount for this line.';
COMMENT ON COLUMN financial_document_lines.service_order_id IS 'Service order the line is attributed to.';
COMMENT ON COLUMN financial_document_lines.service_order_container_id IS 'Container the line is attributed to, for per-container billing.';
COMMENT ON COLUMN financial_document_lines.account_id IS 'General-ledger account this line posts to. When set it overrides the posting rule, which is how ad-hoc accounts are supported.';
COMMENT ON COLUMN financial_document_lines.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: financial_document_postings
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Links a financial document to the journal entries it produced, so a
-- reversal entry stays attached to the document it corrects.
-- --------------------------------------------------------------------------
CREATE TABLE financial_document_postings (
    -- Document that produced the entry.
    financial_document_id BIGINT NOT NULL,
    -- Journal entry produced by posting the document.
    journal_entry_id BIGINT NOT NULL,
    -- Whether this is the ORIGINAL_POSTING, its REVERSAL, or an ADJUSTMENT.
    posting_role VARCHAR(32) NOT NULL,
    -- Timestamp the link was created.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_financial_document_postings PRIMARY KEY (id),
    CONSTRAINT uq_fin_doc_postings UNIQUE (financial_document_id, journal_entry_id),
    CONSTRAINT fk_financial_document_postings_financial_document_id_fi_9505 FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id),
    CONSTRAINT fk_financial_document_postings_journal_entry_id_journal_entries FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id)
);

COMMENT ON TABLE financial_document_postings IS 'Links a financial document to the journal entries it produced, so a reversal entry stays attached to the document it corrects.';
COMMENT ON COLUMN financial_document_postings.financial_document_id IS 'Document that produced the entry.';
COMMENT ON COLUMN financial_document_postings.journal_entry_id IS 'Journal entry produced by posting the document.';
COMMENT ON COLUMN financial_document_postings.posting_role IS 'Whether this is the ORIGINAL_POSTING, its REVERSAL, or an ADJUSTMENT.';
COMMENT ON COLUMN financial_document_postings.created_at IS 'Timestamp the link was created.';
COMMENT ON COLUMN financial_document_postings.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: journal_entry_lines
-- Module: Double-Entry Finance  [app.modules.finance.models]
-- Debit or credit line of a journal entry. Amounts are held both in the
-- transaction currency and in the base currency, so the ledger stays balanced
-- across currencies.
-- --------------------------------------------------------------------------
CREATE TABLE journal_entry_lines (
    -- Journal entry the line belongs to. CASCADE on entry deletion.
    journal_entry_id BIGINT NOT NULL,
    -- Sequential line number within the parent document, 1-based and
    -- displayed in order.
    line_no INTEGER NOT NULL,
    -- General-ledger account debited or credited. Must reference a postable
    -- account.
    account_id BIGINT NOT NULL,
    -- Business party the line relates to, for party-level reporting.
    party_id BIGINT,
    -- Service order the line relates to, for operational reporting.
    service_order_id BIGINT,
    -- Financial document the line was generated from.
    financial_document_id BIGINT,
    -- Narrative printed on the line.
    description TEXT,
    -- Debit amount in currency_code. Zero on a pure credit line.
    debit_amount NUMERIC(19, 4) NOT NULL,
    -- Credit amount in currency_code. Zero on a pure debit line.
    credit_amount NUMERIC(19, 4) NOT NULL,
    -- ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on
    -- the row are denominated in this currency.
    currency_code VARCHAR(3) NOT NULL,
    -- Rate used to convert the amounts into the base currency.
    exchange_rate NUMERIC(19, 8) NOT NULL,
    -- debit_amount converted to the base currency. Summed for the trial
    -- balance.
    base_debit_amount NUMERIC(19, 4) NOT NULL,
    -- credit_amount converted to the base currency. Summed for the trial
    -- balance.
    base_credit_amount NUMERIC(19, 4) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_journal_entry_lines PRIMARY KEY (id),
    CONSTRAINT uq_journal_entry_lines_no UNIQUE (journal_entry_id, line_no),
    CONSTRAINT fk_journal_entry_lines_journal_entry_id_journal_entries FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE,
    CONSTRAINT fk_journal_entry_lines_account_id_chart_of_accounts FOREIGN KEY(account_id) REFERENCES chart_of_accounts (id),
    CONSTRAINT fk_journal_entry_lines_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id),
    CONSTRAINT fk_journal_entry_lines_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id),
    CONSTRAINT fk_journal_entry_lines_financial_document_id_financial__f6c2 FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id)
);
CREATE INDEX ix_journal_entry_lines_account_id ON journal_entry_lines (account_id);
CREATE INDEX ix_journal_entry_lines_journal_entry_id ON journal_entry_lines (journal_entry_id);

COMMENT ON TABLE journal_entry_lines IS 'Debit or credit line of a journal entry. Amounts are held both in the transaction currency and in the base currency, so the ledger stays balanced across currencies.';
COMMENT ON COLUMN journal_entry_lines.journal_entry_id IS 'Journal entry the line belongs to. CASCADE on entry deletion.';
COMMENT ON COLUMN journal_entry_lines.line_no IS 'Sequential line number within the parent document, 1-based and displayed in order.';
COMMENT ON COLUMN journal_entry_lines.account_id IS 'General-ledger account debited or credited. Must reference a postable account.';
COMMENT ON COLUMN journal_entry_lines.party_id IS 'Business party the line relates to, for party-level reporting.';
COMMENT ON COLUMN journal_entry_lines.service_order_id IS 'Service order the line relates to, for operational reporting.';
COMMENT ON COLUMN journal_entry_lines.financial_document_id IS 'Financial document the line was generated from.';
COMMENT ON COLUMN journal_entry_lines.description IS 'Narrative printed on the line.';
COMMENT ON COLUMN journal_entry_lines.debit_amount IS 'Debit amount in currency_code. Zero on a pure credit line.';
COMMENT ON COLUMN journal_entry_lines.credit_amount IS 'Credit amount in currency_code. Zero on a pure debit line.';
COMMENT ON COLUMN journal_entry_lines.currency_code IS 'ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are denominated in this currency.';
COMMENT ON COLUMN journal_entry_lines.exchange_rate IS 'Rate used to convert the amounts into the base currency.';
COMMENT ON COLUMN journal_entry_lines.base_debit_amount IS 'debit_amount converted to the base currency. Summed for the trial balance.';
COMMENT ON COLUMN journal_entry_lines.base_credit_amount IS 'credit_amount converted to the base currency. Summed for the trial balance.';
COMMENT ON COLUMN journal_entry_lines.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- --------------------------------------------------------------------------
-- Table: service_order_charge_lines
-- Module: Service Operations  [app.modules.operations.models]
-- Chargeable line of a service order charge.
-- --------------------------------------------------------------------------
CREATE TABLE service_order_charge_lines (
    -- Charge document the line belongs to. CASCADE on deletion.
    service_order_charge_id BIGINT NOT NULL,
    -- Sequential line number within the parent document, 1-based and
    -- displayed in order.
    line_no INTEGER NOT NULL,
    -- Catalogue fee billed by this line.
    fee_type_id BIGINT,
    -- Container this charge is attributed to, for per-container billing. NULL
    -- for document-level charges.
    service_order_container_id BIGINT,
    -- Description printed on the charge for this line.
    description TEXT NOT NULL,
    -- Billed quantity (NUMERIC(12,3)).
    quantity NUMERIC(12, 3) NOT NULL,
    -- Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG,
    -- PERCENT).
    unit_code VARCHAR(32),
    -- Price per unit in currency_code, before discount and tax.
    unit_price NUMERIC(19, 4) NOT NULL,
    -- Absolute discount deducted from the line subtotal.
    discount_amount NUMERIC(19, 4) NOT NULL,
    -- Tax/VAT rate applied to the line (NUMERIC(7,4)).
    tax_rate NUMERIC(7, 4) NOT NULL,
    -- Absolute tax charged on this line.
    tax_amount NUMERIC(19, 4) NOT NULL,
    -- Final payable amount for this line.
    line_amount NUMERIC(19, 4) NOT NULL,
    -- Surrogate primary key. BIGSERIAL sequence-backed and never reused.
    id BIGSERIAL NOT NULL,
    CONSTRAINT pk_service_order_charge_lines PRIMARY KEY (id),
    CONSTRAINT uq_service_order_charge_lines_no UNIQUE (service_order_charge_id, line_no),
    CONSTRAINT fk_service_order_charge_lines_service_order_charge_id_s_b0ca FOREIGN KEY(service_order_charge_id) REFERENCES service_order_charges (id) ON DELETE CASCADE,
    CONSTRAINT fk_service_order_charge_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id),
    CONSTRAINT fk_service_order_charge_lines_service_order_container_i_e64b FOREIGN KEY(service_order_container_id) REFERENCES service_order_containers (id)
);
CREATE INDEX ix_service_order_charge_lines_service_order_charge_id ON service_order_charge_lines (service_order_charge_id);

COMMENT ON TABLE service_order_charge_lines IS 'Chargeable line of a service order charge.';
COMMENT ON COLUMN service_order_charge_lines.service_order_charge_id IS 'Charge document the line belongs to. CASCADE on deletion.';
COMMENT ON COLUMN service_order_charge_lines.line_no IS 'Sequential line number within the parent document, 1-based and displayed in order.';
COMMENT ON COLUMN service_order_charge_lines.fee_type_id IS 'Catalogue fee billed by this line.';
COMMENT ON COLUMN service_order_charge_lines.service_order_container_id IS 'Container this charge is attributed to, for per-container billing. NULL for document-level charges.';
COMMENT ON COLUMN service_order_charge_lines.description IS 'Description printed on the charge for this line.';
COMMENT ON COLUMN service_order_charge_lines.quantity IS 'Billed quantity (NUMERIC(12,3)).';
COMMENT ON COLUMN service_order_charge_lines.unit_code IS 'Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG, PERCENT).';
COMMENT ON COLUMN service_order_charge_lines.unit_price IS 'Price per unit in currency_code, before discount and tax.';
COMMENT ON COLUMN service_order_charge_lines.discount_amount IS 'Absolute discount deducted from the line subtotal.';
COMMENT ON COLUMN service_order_charge_lines.tax_rate IS 'Tax/VAT rate applied to the line (NUMERIC(7,4)).';
COMMENT ON COLUMN service_order_charge_lines.tax_amount IS 'Absolute tax charged on this line.';
COMMENT ON COLUMN service_order_charge_lines.line_amount IS 'Final payable amount for this line.';
COMMENT ON COLUMN service_order_charge_lines.id IS 'Surrogate primary key. BIGSERIAL sequence-backed and never reused.';

-- ==========================================================================
-- END OF SCHEMA - 67 tables
-- ==========================================================================
