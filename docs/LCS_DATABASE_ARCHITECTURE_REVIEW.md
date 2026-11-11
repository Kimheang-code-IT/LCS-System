# LCS Database Architecture Review

> **Verification note.** Column/relationship data below is **VERIFIED CODE**, read from
> the SQLAlchemy `Base.metadata` of the checked-out backend
> (source used for this run: `sqlalchemy_models`; 76 tables).
> A direct PostgreSQL catalog read was **NOT VERIFIED** in this environment (no local
> psycopg2 driver / PostgreSQL reachable), so no live-database claim is made anywhere
> in this document. ORM-side types are compiled for the PostgreSQL dialect; a real
> database/ORM diff still requires a catalog read against the deployment.

---

## 1. System Summary

LCS is a single-tenant freight-forwarding ERP: master data feeds operational documents
(Quotations → Service Orders → Service Charges), which feed double-entry finance
(Financial Documents → Journals → Period Closing). Configuration (component tabs →
groups → attributes) drives dynamic frontend forms and is versioned by publishable
snapshots (`configuration_versions`, five-sheet workbooks). Admin blocks: users/roles/
permissions (Casbin), document sequences, audit events, app settings, backup/restore,
storage replication, Telegram alerting, staged Excel/CSV/JSON import-export.

## 2. Technology Stack (VERIFIED CODE)

| Part | Detail |
|------|--------|
| API | FastAPI (routers under `backend/app/modules/*/router.py`) |
| ORM | SQLAlchemy 2.x mapped_column models (`backend/app/modules/*/models.py`) |
| DB | PostgreSQL (Alembic in `backend/alembic`); local run also verified on SQLite fallback |
| Validation | Pydantic/service schemas; a shared `RecordSchema`/`FieldSpec` validator in `app/core/validation` for nested settings & forms |
| Frontend | Nuxt 4 + Nuxt UI (static SPA) |
| Authz | Roles/permissions tables + Casbin policy; mandatory backend context checks |

## 3. Important Business Rules (must survive any refactor)

- Master data records are soft-deleted (`deleted_at`); active-record queries always filter it.
- Financial posting: journals must stay balanced, posted history immutable; period-closing gates writes; currency/rate snapshots stored on documents.
- Document sequences are service-managed number sources; importing must never mint numbers.
- Configuration versions are immutable once PUBLISHED; imports always create DRAFT versions.
- Import/export is an explicit module allowlist (`excel_io/registry.py`); every write reuses the ordinary CRUD service; commit revalidates atomically; Create-Only never touches existing rows.
- Secrets (password hashes, bot tokens, R2/Drive client keys, service-account JSON) are write-only: never returned by API responses; blank input preserves stored values.
- Settings persistence: `app_settings` is the system of record; `module_records` row `app_config/1` is a transitional mirror.
- Audit events record every sensitive action (SETTINGS_UPDATED, storage/backup jobs, import jobs) — group names/counters only, never payload secrets.
- Maintenance mode and read-only mode are backend-enforced (dedicated maintenance endpoints, not generic settings writes).
- Quotation revisions snapshot lines/containers/places; service orders reference the quotation they converted from; revision roll-ups are authoritative for totals.

## 4. Review Goals

1. Simplify unnecessary tables/columns. 2. Improve relationships. 3. Improve validation.
4. Improve backend logic. 5. Improve configuration management. 6. Improve import/export.
7. Reduce duplication. 8. Preserve accounting correctness. 9. Preserve history.
10. Performance/maintainability.

## 5. Non-Negotiable Constraints

Existing production data, historical finance records, quotation reuse, Service Order
workflows, accounting integrity, RBAC, document sequences, configuration versions and
audit logs must be preserved by any recommendation.

---

## 6. Schema Overview

| Module | Tables |
|--------|--------|
| Master Data & Configuration | `business_parties`, `business_party_roles`, `capacity_units`, `component_attributes`, `component_group_attributes`, `component_groups`, `component_tab_groups`, `component_tabs`, `configuration_versions`, `container_types`, `currencies`, `currency_rates`, `customer_customs_accounts`, `document_types`, `fee_types`, `module_records`, `party_roles`, `place_role_places`, `place_roles`, `places`, `trade_directions`, `transport_asset_identity_types`, `transport_assets`, `transport_types` |
| Quotations | `quotation_conversions`, `quotation_revision_containers`, `quotation_revision_lines`, `quotation_revision_places`, `quotation_revisions`, `quotations` |
| Operations (Service Orders) | `attachment_links`, `attachments`, `service_order_charge_lines`, `service_order_charges`, `service_order_component_rows`, `service_order_container_requirements`, `service_order_containers`, `service_order_milestones`, `service_order_movements`, `service_order_places`, `service_order_pricing`, `service_order_pricing_lines`, `service_orders` |
| Finance & Accounting | `accounting_periods`, `chart_of_accounts`, `document_sequences`, `financial_accounts`, `financial_document_allocations`, `financial_document_lines`, `financial_document_postings`, `financial_document_sources`, `financial_documents`, `journal_entries`, `journal_entry_lines`, `posting_rules` |
| Settings | `app_settings` |
| Administration (Auth/RBAC) | `password_reset_tokens`, `permissions`, `roles`, `used_refresh_tokens`, `user_credentials`, `user_sessions`, `users` |
| Administration (Archive) | `archive_records` |
| Backup & Restore | `backup_logs`, `backup_records`, `backup_runs`, `backup_states` |
| Audit | `audit_events` |
| Import / Export | `import_jobs`, `import_sessions` |
| Telegram (notification jobs) | `notification_incidents`, `notification_outbox`, `telegram_links`, `telegram_pairings`, `telegram_updates` |
| **Total** | **76** |

No PostgreSQL enum types are declared anywhere in the models: every enumeration
is a `varchar` handled by service-level allowlists
(INFERRED — 0 enum-typed columns found in metadata; 0 seen, expected 0).

---

## 7. Table Details (VERIFIED CODE — SQLAlchemy metadata)

### Table: `business_parties`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** BusinessParty  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| party_code | VARCHAR(50) | No | — | — |
| legal_name | VARCHAR(255) | No | — | — |
| display_name | VARCHAR(255) | Yes | — | — |
| vat_tin | VARCHAR(64) | Yes | — | — |
| contact_person | VARCHAR(255) | Yes | — | — |
| phone | VARCHAR(64) | Yes | — | — |
| email | VARCHAR(255) | Yes | — | — |
| address | TEXT | Yes | — | — |
| roles | JSONB | No | python:list() | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_business_parties_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_business_parties_deleted_at` on (deleted_at)
- index `uq_business_parties_vat_tin_active` on (vat_tin), UNIQUE
- index `uq_business_parties_party_code_active` on (party_code), UNIQUE

### Table: `business_party_roles`

**Module:** Master Data & Configuration  
**Purpose:** A party holds several roles; the pair is unique and the role is protected  
**SQLAlchemy Model:** BusinessPartyRole  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| business_party_id | BIGINT | No | — | FK→business_parties.id ondelete=CASCADE |
| party_role_id | BIGINT | No | — | FK→party_roles.id ondelete=RESTRICT |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| party_role_id | party_roles.id | RESTRICT |
| business_party_id | business_parties.id | CASCADE |

#### Indexes and constraints

- index `ix_business_party_roles_party_role_id` on (party_role_id)
- index `ix_business_party_roles_business_party_id` on (business_party_id)
- unique `uq_business_party_roles` (business_party_id, party_role_id)

### Table: `capacity_units`

**Module:** Master Data & Configuration  
**Purpose:** An administrator-managed option for ``transport_assets.capacity_unit``  
**SQLAlchemy Model:** CapacityUnit  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(32) | No | — | — |
| name | VARCHAR(64) | No | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_capacity_units_deleted_at` on (deleted_at)
- index `uq_capacity_units_code_active` on (code), UNIQUE
- index `ix_capacity_units_deleted_by_user_id` on (deleted_by_user_id)

### Table: `component_attributes`

**Module:** Master Data & Configuration  
**Purpose:** Reusable dynamic-form attribute (field) in the global catalog  
**SQLAlchemy Model:** ComponentAttribute  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(64) | No | — | — |
| label | VARCHAR(255) | No | — | — |
| label_km | VARCHAR(255) | Yes | — | — |
| data_type | VARCHAR(32) | No | 'text' | — |
| input_type | VARCHAR(32) | Yes | — | — |
| reference_type | VARCHAR(32) | Yes | — | — |
| is_required | BOOLEAN | No | False | — |
| default_value | VARCHAR(255) | Yes | — | — |
| placeholder | VARCHAR(255) | Yes | — | — |
| width | VARCHAR(16) | Yes | — | — |
| options | JSONB | No | python:list() | — |
| validation_rules | JSONB | No | python:dict() | — |
| display_order | INTEGER | No | 0 | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_component_attributes_code` (code)

### Table: `component_group_attributes`

**Module:** Master Data & Configuration  
**Purpose:** Membership of a reusable attribute in a component group, with overrides  
**SQLAlchemy Model:** ComponentGroupAttribute  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| group_id | BIGINT | No | — | FK→component_groups.id ondelete=CASCADE |
| attribute_id | BIGINT | No | — | FK→component_attributes.id ondelete=CASCADE |
| is_required | BOOLEAN | Yes | — | — |
| width | VARCHAR(16) | Yes | — | — |
| display_order | INTEGER | No | 0 | — |
| is_visible | BOOLEAN | No | true | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| group_id | component_groups.id | CASCADE |
| attribute_id | component_attributes.id | CASCADE |

#### Indexes and constraints

- index `ix_component_group_attributes_group_id` on (group_id)
- index `ix_component_group_attributes_attribute_id` on (attribute_id)
- unique `uq_component_group_attributes_group_attr` (group_id, attribute_id)

### Table: `component_groups`

**Module:** Master Data & Configuration  
**Purpose:** A reusable group of attributes  
**SQLAlchemy Model:** ComponentGroup  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(64) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| name_km | VARCHAR(255) | Yes | — | — |
| description | TEXT | Yes | — | — |
| render_mode | VARCHAR(16) | No | 'table' | — |
| display_order | INTEGER | No | 0 | — |
| is_active | BOOLEAN | No | True | — |
| is_archived | BOOLEAN | No | False | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_component_groups_code` (code)

### Table: `component_tab_groups`

**Module:** Master Data & Configuration  
**Purpose:** Membership of a component group in a component tab, including its layout  
**SQLAlchemy Model:** ComponentTabGroup  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| tab_id | BIGINT | No | — | FK→component_tabs.id ondelete=CASCADE |
| group_id | BIGINT | No | — | FK→component_groups.id ondelete=CASCADE |
| display_order | INTEGER | No | 0 | — |
| display_mode | VARCHAR(20) | Yes | — | — |
| data_cardinality | VARCHAR(20) | Yes | — | — |
| form_columns | INTEGER | Yes | — | — |
| show_group_title | BOOLEAN | Yes | — | — |
| editable | BOOLEAN | Yes | — | — |
| collapsible | BOOLEAN | Yes | — | — |
| default_expanded | BOOLEAN | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| group_id | component_groups.id | CASCADE |
| tab_id | component_tabs.id | CASCADE |

#### Indexes and constraints

- index `ix_component_tab_groups_group_id` on (group_id)
- index `ix_component_tab_groups_tab_id` on (tab_id)
- unique `uq_component_tab_groups_tab_group` (tab_id, group_id)
- CHECK `ck_component_tab_groups_display_mode`: `display_mode IS NULL OR display_mode IN ('form_only', 'table_only', 'form_and_table')`
- CHECK `ck_component_tab_groups_data_cardinality`: `data_cardinality IS NULL OR data_cardinality IN ('single', 'multiple')`
- CHECK `ck_component_tab_groups_form_columns`: `form_columns IS NULL OR (form_columns BETWEEN 1 AND 4)`

### Table: `component_tabs`

**Module:** Master Data & Configuration  
**Purpose:** A Service Order tab composed of component groups, shown for one trade direction  
**SQLAlchemy Model:** ComponentTab  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(64) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| trade_direction_id | BIGINT | Yes | — | FK→trade_directions.id ondelete=SET NULL |
| display_order | INTEGER | No | 0 | — |
| is_active | BOOLEAN | No | True | — |
| is_archived | BOOLEAN | No | False | — |
| config_version_id | BIGINT | Yes | — | FK→configuration_versions.id ondelete=SET NULL |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| trade_direction_id | trade_directions.id | SET NULL |
| config_version_id | configuration_versions.id | SET NULL |

#### Indexes and constraints

- index `ix_component_tabs_trade_direction_id` on (trade_direction_id)
- unique `uq_component_tabs_code` (code)

### Table: `configuration_versions`

**Module:** Master Data & Configuration  
**Purpose:** A published snapshot of the dynamic Service Order configuration  
**SQLAlchemy Model:** ConfigurationVersion  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| version_no | INTEGER | No | — | — |
| scope | VARCHAR(32) | No | GLOBAL | — |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| origin | VARCHAR(20) | No | PUBLISH | — |
| change_note | TEXT | Yes | — | — |
| config_snapshot | JSONB | No | python:dict() | — |
| snapshot_schema_version | INTEGER | No | 1 | — |
| content_hash | VARCHAR(64) | Yes | — | — |
| source_version_id | BIGINT | Yes | — | FK→configuration_versions.id ondelete=SET NULL |
| published_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| published_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| activated_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| activated_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| activated_by_user_id | users.id | - |
| published_by_user_id | users.id | - |
| source_version_id | configuration_versions.id | SET NULL |

#### Indexes and constraints

- index `uq_configuration_versions_published` on (status), UNIQUE
- index `ix_configuration_versions_source_version_id` on (source_version_id)
- index `ix_configuration_versions_status` on (status)
- unique `uq_configuration_versions_no` (version_no)

### Table: `container_types`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ContainerType  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| container_size | VARCHAR(32) | Yes | — | — |
| container_kind | VARCHAR(32) | Yes | — | — |
| iso_code | VARCHAR(16) | Yes | — | — |
| length_feet | NUMERIC(6, 2) | Yes | — | — |
| width_millimeter | NUMERIC(8, 2) | Yes | — | — |
| height_millimeter | NUMERIC(8, 2) | Yes | — | — |
| max_gross_weight_kg | NUMERIC(12, 3) | Yes | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_container_types_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_container_types_deleted_at` on (deleted_at)
- index `uq_container_types_code_active` on (code), UNIQUE

### Table: `currencies`

**Module:** Master Data & Configuration  
**Purpose:** Currency master data  
**SQLAlchemy Model:** Currency  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(3) | No | — | — |
| name | VARCHAR(100) | No | — | — |
| symbol | VARCHAR(10) | Yes | — | — |
| numeric_code | VARCHAR(3) | Yes | — | — |
| decimal_places | INTEGER | No | 2 | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `uq_currencies_code_active` on (code), UNIQUE
- index `ix_currencies_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_currencies_deleted_at` on (deleted_at)

### Table: `currency_rates`

**Module:** Master Data & Configuration  
**Purpose:** An approved conversion rate between two currencies, effective from a date  
**SQLAlchemy Model:** CurrencyRate  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| from_currency_code | VARCHAR(3) | No | — | — |
| to_currency_code | VARCHAR(3) | No | — | — |
| effective_date | DATE | No | — | — |
| rate | NUMERIC(19, 8) | No | — | — |
| status | VARCHAR(20) | No | 'PENDING' | — |
| source | VARCHAR(80) | Yes | — | — |
| description | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_currency_rates_deleted_at` on (deleted_at)
- index `uq_currency_rates_pair_date` on (from_currency_code, to_currency_code, effective_date), UNIQUE
- index `ix_currency_rates_lookup` on (from_currency_code, to_currency_code, effective_date, status)
- index `ix_currency_rates_deleted_by_user_id` on (deleted_by_user_id)

### Table: `customer_customs_accounts`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** CustomerCustomsAccount  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| party_id | BIGINT | No | — | FK→business_parties.id ondelete=CASCADE |
| system_name | VARCHAR(128) | No | — | — |
| username | VARCHAR(255) | No | — | — |
| password_secret_reference | VARCHAR(255) | Yes | — | — |
| encrypted_password | BYTEA | Yes | — | — |
| last_verified_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| party_id | business_parties.id | CASCADE |

#### Indexes and constraints

Beyond PK/FK, none declared at ORM level.

### Table: `document_types`

**Module:** Master Data & Configuration  
**Purpose:** Administrator-managed classification of documents  
**SQLAlchemy Model:** DocumentType  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(64) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| category | VARCHAR(32) | No | 'FINANCE' | — |
| description | TEXT | Yes | — | — |
| accounting_behavior | VARCHAR(64) | No | — | — |
| posting_required | BOOLEAN | No | False | — |
| available_in | JSONB | No | python:list() | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| updated_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| created_by_user_id | users.id | - |
| updated_by_user_id | users.id | - |
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `uq_document_types_code_active` on (code), UNIQUE
- index `ix_document_types_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_document_types_deleted_at` on (deleted_at)

### Table: `fee_types`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FeeType  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_fee_types_deleted_at` on (deleted_at)
- index `ix_fee_types_deleted_by_user_id` on (deleted_by_user_id)
- index `uq_fee_types_code_active` on (code), UNIQUE

### Table: `module_records`

**Module:** Master Data & Configuration  
**Purpose:** Generic record store backing metadata-driven frontend collections  
**SQLAlchemy Model:** ModuleRecord  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| collection | VARCHAR(64) | No | — | — |
| record_no | VARCHAR(64) | Yes | — | — |
| status | VARCHAR(32) | Yes | — | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_module_records_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_module_records_collection` on (collection)
- index `ix_module_records_deleted_at` on (deleted_at)

### Table: `party_roles`

**Module:** Master Data & Configuration  
**Purpose:** An administrator-managed role a business party can hold  
**SQLAlchemy Model:** PartyRole  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_party_roles_deleted_by_user_id` on (deleted_by_user_id)
- index `uq_party_roles_code_active` on (code), UNIQUE
- index `uq_party_roles_name_active` on (name), UNIQUE
- index `ix_party_roles_deleted_at` on (deleted_at)

### Table: `place_role_places`

**Module:** Master Data & Configuration  
**Purpose:** Optional allowed-place mapping for a Place Role  
**SQLAlchemy Model:** PlaceRolePlace  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| place_role_id | BIGINT | No | — | FK→place_roles.id ondelete=CASCADE |
| place_id | BIGINT | No | — | FK→places.id ondelete=CASCADE |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| place_id | places.id | CASCADE |
| place_role_id | place_roles.id | CASCADE |

#### Indexes and constraints

- index `ix_place_role_places_place_id` on (place_id)
- index `ix_place_role_places_place_role_id` on (place_role_id)
- unique `uq_place_role_places` (place_role_id, place_id)

### Table: `place_roles`

**Module:** Master Data & Configuration  
**Purpose:** A reusable role a route stop can play (Pickup, Origin, Customs …)  
**SQLAlchemy Model:** PlaceRole  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| sort_order | INTEGER | No | 0 | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_place_roles_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_place_roles_deleted_at` on (deleted_at)
- index `uq_place_roles_code_active` on (code), UNIQUE

### Table: `places`

**Module:** Master Data & Configuration  
**Purpose:** A legacy location master retained for historical route references  
**SQLAlchemy Model:** Place  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | Yes | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| address | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `uq_places_code_active` on (code), UNIQUE
- index `ix_places_deleted_at` on (deleted_at)
- index `ix_places_deleted_by_user_id` on (deleted_by_user_id)

### Table: `trade_directions`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TradeDirection  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_trade_directions_deleted_at` on (deleted_at)
- index `ix_trade_directions_deleted_by_user_id` on (deleted_by_user_id)
- index `uq_trade_directions_code_active` on (code), UNIQUE

### Table: `transport_asset_identity_types`

**Module:** Master Data & Configuration  
**Purpose:** An administrator-managed option for ``transport_assets.identity_type``  
**SQLAlchemy Model:** TransportAssetIdentityType  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| name | VARCHAR(64) | No | — | — |
| transport_type_id | BIGINT | Yes | — | FK→transport_types.id ondelete=- |
| identity_label | VARCHAR(128) | Yes | — | — |
| identity_placeholder | VARCHAR(128) | Yes | — | — |
| validation_pattern | VARCHAR(255) | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| transport_type_id | transport_types.id | - |
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_transport_asset_identity_types_deleted_at` on (deleted_at)
- index `uq_transport_asset_identity_types_name_active` on (name), UNIQUE
- index `ix_transport_asset_identity_types_deleted_by_user_id` on (deleted_by_user_id)

### Table: `transport_assets`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TransportAsset  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| asset_code | VARCHAR(50) | No | — | — |
| transport_type_id | BIGINT | No | — | FK→transport_types.id ondelete=- |
| identity | VARCHAR(128) | No | — | — |
| identity_type | VARCHAR(64) | No | 'License Plate' | — |
| owner_party_id | BIGINT | Yes | — | FK→business_parties.id ondelete=- |
| operator_party_id | BIGINT | Yes | — | FK→business_parties.id ondelete=- |
| asset_name | VARCHAR(255) | Yes | — | — |
| capacity_value | NUMERIC(12, 3) | Yes | — | — |
| capacity_unit | VARCHAR(32) | Yes | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| owner_party_id | business_parties.id | - |
| deleted_by_user_id | users.id | SET NULL |
| operator_party_id | business_parties.id | - |
| transport_type_id | transport_types.id | - |

#### Indexes and constraints

- index `uq_transport_assets_type_identity_active` on (transport_type_id, identity), UNIQUE
- index `ix_transport_assets_deleted_at` on (deleted_at)
- index `uq_transport_assets_asset_code_active` on (asset_code), UNIQUE
- index `ix_transport_assets_deleted_by_user_id` on (deleted_by_user_id)

### Table: `transport_types`

**Module:** Master Data & Configuration  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TransportType  
**Source:** `app/modules/master_data/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(50) | No | — | — |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| deleted_by_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_transport_types_deleted_at` on (deleted_at)
- index `ix_transport_types_deleted_by_user_id` on (deleted_by_user_id)
- index `uq_transport_types_code_active` on (code), UNIQUE

### Table: `quotation_conversions`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** QuotationConversion  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_revision_id | BIGINT | No | — | FK→quotation_revisions.id ondelete=- |
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=RESTRICT |
| converted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| converted_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| notes | TEXT | Yes | — | — |
| idempotency_key | VARCHAR(128) | Yes | — | UNIQUE |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| quotation_revision_id | quotation_revisions.id | - |
| service_order_id | service_orders.id | RESTRICT |
| converted_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_quotation_conversions_quotation_revision_id` on (quotation_revision_id)
- unique `uq_quotation_conversions_service_order_id` (service_order_id)
- unique `uq_quotation_conversions_idempotency_key` (idempotency_key)

### Table: `quotation_revision_containers`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** QuotationRevisionContainer  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_revision_id | BIGINT | No | — | FK→quotation_revisions.id ondelete=CASCADE |
| container_type_id | BIGINT | No | — | FK→container_types.id ondelete=- |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| gross_weight_kg | NUMERIC(12, 3) | Yes | — | — |
| description | TEXT | Yes | — | — |
| remarks | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| quotation_revision_id | quotation_revisions.id | CASCADE |
| container_type_id | container_types.id | - |

#### Indexes and constraints

- index `ix_quotation_revision_containers_quotation_revision_id` on (quotation_revision_id)

### Table: `quotation_revision_lines`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** QuotationRevisionLine  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_revision_id | BIGINT | No | — | FK→quotation_revisions.id ondelete=CASCADE |
| line_no | INTEGER | No | 1 | — |
| fee_type_id | BIGINT | Yes | — | FK→fee_types.id ondelete=- |
| container_requirement_id | BIGINT | Yes | — | FK→quotation_revision_containers.id ondelete=- |
| service_description | TEXT | No | '' | — |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| unit_code | VARCHAR(32) | Yes | — | — |
| unit_price | NUMERIC(19, 4) | No | 0 | — |
| discount_rate | NUMERIC(7, 4) | No | 0 | — |
| tax_rate | NUMERIC(7, 4) | No | 0 | — |
| line_subtotal | NUMERIC(19, 4) | No | 0 | — |
| line_discount | NUMERIC(19, 4) | No | 0 | — |
| line_tax | NUMERIC(19, 4) | No | 0 | — |
| line_total | NUMERIC(19, 4) | No | 0 | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| fee_type_id | fee_types.id | - |
| quotation_revision_id | quotation_revisions.id | CASCADE |
| container_requirement_id | quotation_revision_containers.id | - |

#### Indexes and constraints

- index `ix_quotation_revision_lines_quotation_revision_id` on (quotation_revision_id)
- unique `uq_quotation_revision_lines_no` (quotation_revision_id, line_no)

### Table: `quotation_revision_places`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** QuotationRevisionPlace  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_revision_id | BIGINT | No | — | FK→quotation_revisions.id ondelete=CASCADE |
| place_role_id | BIGINT | Yes | — | FK→place_roles.id ondelete=SET NULL |
| place_id | BIGINT | Yes | — | FK→places.id ondelete=- |
| place_role | VARCHAR(32) | No | — | — |
| sequence_no | INTEGER | No | 1 | — |
| planned_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| free_text | TEXT | Yes | — | — |
| notes | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| quotation_revision_id | quotation_revisions.id | CASCADE |
| place_id | places.id | - |
| place_role_id | place_roles.id | SET NULL |

#### Indexes and constraints

- index `ix_quotation_revision_places_quotation_revision_id` on (quotation_revision_id)
- unique `uq_quotation_revision_places_sequence` (quotation_revision_id, sequence_no)

### Table: `quotation_revisions`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** QuotationRevision  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_id | BIGINT | No | — | FK→quotations.id ondelete=CASCADE |
| revision_no | INTEGER | No | 1 | — |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| quotation_date | DATE | No | — | — |
| valid_until | DATE | Yes | — | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| description | TEXT | Yes | — | — |
| notes | TEXT | Yes | — | — |
| subtotal_amount | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| total_amount | NUMERIC(19, 4) | No | 0 | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| sent_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| accepted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| rejected_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| created_by_user_id | users.id | - |
| quotation_id | quotations.id | CASCADE |

#### Indexes and constraints

- index `ix_quotation_revisions_status` on (status)
- index `ix_quotation_revisions_quotation_id` on (quotation_id)
- unique `uq_quotation_revisions_no` (quotation_id, revision_no)

### Table: `quotations`

**Module:** Quotations  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** Quotation  
**Source:** `app/modules/quotations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| quotation_no | VARCHAR(50) | No | — | — |
| customer_party_id | BIGINT | No | — | FK→business_parties.id ondelete=- |
| trade_direction_id | BIGINT | No | — | FK→trade_directions.id ondelete=- |
| current_revision_no | INTEGER | No | 1 | — |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| source_service_order_id | BIGINT | Yes | — | FK→service_orders.id ondelete=SET NULL |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| source_service_order_id | service_orders.id | SET NULL |
| trade_direction_id | trade_directions.id | - |
| customer_party_id | business_parties.id | - |

#### Indexes and constraints

- index `ix_quotations_source_service_order_id` on (source_service_order_id)
- index `ix_quotations_status` on (status)
- unique `uq_quotations_no` (quotation_no)

### Table: `attachment_links`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** AttachmentLink  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| attachment_id | BIGINT | No | — | FK→attachments.id ondelete=CASCADE |
| entity_type | VARCHAR(64) | No | — | — |
| entity_id | BIGINT | No | — | — |
| attachment_role | VARCHAR(64) | No | 'ATTACHMENT' | — |
| is_primary | BOOLEAN | No | False | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| attachment_id | attachments.id | CASCADE |

#### Indexes and constraints

- index `ix_attachment_links_attachment_id` on (attachment_id)
- unique `uq_attachment_links_target` (attachment_id, entity_type, entity_id, attachment_role)

### Table: `attachments`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** Attachment  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| file_name | VARCHAR(512) | No | — | — |
| storage_key | VARCHAR(512) | No | — | UNIQUE |
| mime_type | VARCHAR(128) | No | — | — |
| file_size_bytes | BIGINT | No | 0 | — |
| checksum | VARCHAR(128) | Yes | — | — |
| storage_provider | VARCHAR(32) | No | 'local' | — |
| document_version | INTEGER | No | 1 | — |
| note | VARCHAR(1000) | Yes | — | — |
| uploaded_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| uploaded_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| is_deleted | BOOLEAN | No | False | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| uploaded_by_user_id | users.id | - |

#### Indexes and constraints

- unique `uq_attachments_storage_key` (storage_key)

### Table: `service_order_charge_lines`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderChargeLine  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_charge_id | BIGINT | No | — | FK→service_order_charges.id ondelete=CASCADE |
| line_no | INTEGER | No | 1 | — |
| fee_type_id | BIGINT | Yes | — | FK→fee_types.id ondelete=- |
| service_order_container_id | BIGINT | Yes | — | FK→service_order_containers.id ondelete=- |
| description | TEXT | No | '' | — |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| unit_code | VARCHAR(32) | Yes | — | — |
| unit_price | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_rate | NUMERIC(7, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| line_amount | NUMERIC(19, 4) | No | 0 | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_container_id | service_order_containers.id | - |
| service_order_charge_id | service_order_charges.id | CASCADE |
| fee_type_id | fee_types.id | - |

#### Indexes and constraints

- index `ix_service_order_charge_lines_service_order_charge_id` on (service_order_charge_id)
- unique `uq_service_order_charge_lines_no` (service_order_charge_id, line_no)

### Table: `service_order_charges`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderCharge  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| charge_no | VARCHAR(50) | No | — | — |
| document_type | VARCHAR(32) | No | 'SERVICE_NOTE' | — |
| document_date | DATE | No | — | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| subtotal_amount | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| total_amount | NUMERIC(19, 4) | No | 0 | — |
| remark | TEXT | Yes | — | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| created_by_user_id | users.id | - |
| service_order_id | service_orders.id | CASCADE |

#### Indexes and constraints

- index `ix_service_order_charges_status` on (status)
- index `ix_service_order_charges_service_order_id` on (service_order_id)
- unique `uq_service_order_charges_no` (charge_no)

### Table: `service_order_component_rows`

**Module:** Operations (Service Orders)  
**Purpose:** One row of a table-mode component group, or the single record of a form-mode group  
**SQLAlchemy Model:** ServiceOrderComponentRow  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| group_id | BIGINT | No | — | FK→component_groups.id ondelete=CASCADE |
| row_no | INTEGER | No | 1 | — |
| is_archived | BOOLEAN | No | False | — |
| values | JSONB | No | python:dict() | — |
| config_version_id | BIGINT | Yes | — | FK→configuration_versions.id ondelete=SET NULL |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| updated_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| config_version_id | configuration_versions.id | SET NULL |
| updated_by_user_id | users.id | - |
| service_order_id | service_orders.id | CASCADE |
| group_id | component_groups.id | CASCADE |
| created_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_service_order_component_rows_group_id` on (group_id)
- index `ix_service_order_component_rows_service_order_id` on (service_order_id)

### Table: `service_order_container_requirements`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderContainerRequirement  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| source_quotation_container_id | BIGINT | Yes | — | FK→quotation_revision_containers.id ondelete=- |
| container_type_id | BIGINT | No | — | FK→container_types.id ondelete=- |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| gross_weight_kg | NUMERIC(12, 3) | Yes | — | — |
| description | TEXT | Yes | — | — |
| remarks | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | CASCADE |
| source_quotation_container_id | quotation_revision_containers.id | - |
| container_type_id | container_types.id | - |

#### Indexes and constraints

- index `ix_service_order_container_requirements_service_order_id` on (service_order_id)

### Table: `service_order_containers`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderContainer  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| container_requirement_id | BIGINT | Yes | — | FK→service_order_container_requirements.id ondelete=- |
| container_type_id | BIGINT | No | — | FK→container_types.id ondelete=- |
| container_number | VARCHAR(32) | Yes | — | — |
| seal_serial | VARCHAR(64) | Yes | — | — |
| status | VARCHAR(32) | No | 'EXPECTED' | — |
| net_weight_kg | NUMERIC(12, 3) | Yes | — | — |
| gross_weight_kg | NUMERIC(12, 3) | Yes | — | — |
| pickup_date | DATE | Yes | — | — |
| return_date | DATE | Yes | — | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | CASCADE |
| container_requirement_id | service_order_container_requirements.id | - |
| container_type_id | container_types.id | - |

#### Indexes and constraints

- index `ix_service_order_containers_service_order_id` on (service_order_id)
- unique `uq_service_order_containers_number` (container_number)

### Table: `service_order_milestones`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderMilestone  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| milestone_code | VARCHAR(64) | No | — | — |
| milestone_name | VARCHAR(255) | No | — | — |
| sequence_no | INTEGER | No | 1 | — |
| planned_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| actual_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| status | VARCHAR(20) | No | 'PENDING' | — |
| notes | TEXT | Yes | — | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | CASCADE |

#### Indexes and constraints

- index `ix_service_order_milestones_service_order_id` on (service_order_id)

### Table: `service_order_movements`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderMovement  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| sequence_no | INTEGER | No | 1 | — |
| transport_type_id | BIGINT | Yes | — | FK→transport_types.id ondelete=- |
| transport_asset_id | BIGINT | Yes | — | FK→transport_assets.id ondelete=- |
| origin_place_id | BIGINT | Yes | — | FK→places.id ondelete=- |
| destination_place_id | BIGINT | Yes | — | FK→places.id ondelete=- |
| planned_departure | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| actual_departure | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| planned_arrival | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| actual_arrival | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| status | VARCHAR(32) | No | 'PLANNED' | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| origin_place_id | places.id | - |
| service_order_id | service_orders.id | CASCADE |
| destination_place_id | places.id | - |
| transport_type_id | transport_types.id | - |
| transport_asset_id | transport_assets.id | - |

#### Indexes and constraints

- index `ix_service_order_movements_service_order_id` on (service_order_id)
- unique `uq_service_order_movements_sequence` (service_order_id, sequence_no)

### Table: `service_order_places`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderPlace  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| place_role_id | BIGINT | Yes | — | FK→place_roles.id ondelete=SET NULL |
| place_id | BIGINT | Yes | — | FK→places.id ondelete=- |
| place_role | VARCHAR(32) | No | — | — |
| sequence_no | INTEGER | No | 1 | — |
| planned_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| actual_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| free_text | TEXT | Yes | — | — |
| is_actual | BOOLEAN | No | False | — |
| notes | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | CASCADE |
| place_role_id | place_roles.id | SET NULL |
| place_id | places.id | - |

#### Indexes and constraints

- index `ix_service_order_places_service_order_id` on (service_order_id)
- unique `uq_service_order_places_sequence` (service_order_id, sequence_no)

### Table: `service_order_pricing`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderPricing  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_id | BIGINT | No | — | FK→service_orders.id ondelete=CASCADE |
| subtotal_amount | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| total_amount | NUMERIC(19, 4) | No | 0 | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | CASCADE |

#### Indexes and constraints

- unique `uq_service_order_pricing_service_order_id` (service_order_id)

### Table: `service_order_pricing_lines`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrderPricingLine  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_pricing_id | BIGINT | No | — | FK→service_order_pricing.id ondelete=CASCADE |
| line_no | INTEGER | No | 1 | — |
| source_quotation_line_id | BIGINT | Yes | — | FK→quotation_revision_lines.id ondelete=- |
| fee_type_id | BIGINT | Yes | — | FK→fee_types.id ondelete=- |
| description | TEXT | No | '' | — |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| unit_code | VARCHAR(32) | Yes | — | — |
| unit_price | NUMERIC(19, 4) | No | 0 | — |
| discount_rate | NUMERIC(7, 4) | No | 0 | — |
| tax_rate | NUMERIC(7, 4) | No | 0 | — |
| line_total | NUMERIC(19, 4) | No | 0 | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_pricing_id | service_order_pricing.id | CASCADE |
| fee_type_id | fee_types.id | - |
| source_quotation_line_id | quotation_revision_lines.id | - |

#### Indexes and constraints

- index `ix_service_order_pricing_lines_service_order_pricing_id` on (service_order_pricing_id)
- unique `uq_so_pricing_lines_no` (service_order_pricing_id, line_no)

### Table: `service_orders`

**Module:** Operations (Service Orders)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ServiceOrder  
**Source:** `app/modules/operations/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| service_order_no | VARCHAR(50) | No | — | — |
| quotation_revision_id | BIGINT | Yes | — | FK→quotation_revisions.id ondelete=- |
| customer_party_id | BIGINT | No | — | FK→business_parties.id ondelete=- |
| trade_direction_id | BIGINT | No | — | FK→trade_directions.id ondelete=- |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| description | TEXT | Yes | — | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| finished_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| finished_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| configuration_version_id | BIGINT | Yes | — | FK→configuration_versions.id ondelete=SET NULL |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| quotation_revision_id | quotation_revisions.id | - |
| finished_by_user_id | users.id | - |
| customer_party_id | business_parties.id | - |
| created_by_user_id | users.id | - |
| configuration_version_id | configuration_versions.id | SET NULL |
| trade_direction_id | trade_directions.id | - |

#### Indexes and constraints

- index `ix_service_orders_status` on (status)
- unique `uq_service_orders_no` (service_order_no)

### Table: `accounting_periods`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** AccountingPeriod  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| name | VARCHAR(120) | Yes | — | — |
| description | VARCHAR(2000) | Yes | — | — |
| period_year | INTEGER | No | — | — |
| period_month | INTEGER | No | — | — |
| start_date | DATE | No | — | — |
| end_date | DATE | No | — | — |
| status | VARCHAR(20) | No | 'OPEN' | — |
| closed_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| closed_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| closed_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_accounting_periods_status` on (status)
- unique `uq_periods_year_month` (period_year, period_month)

### Table: `chart_of_accounts`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ChartOfAccount  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| account_code | VARCHAR(32) | No | — | — |
| account_name | VARCHAR(255) | No | — | — |
| account_type | VARCHAR(20) | No | — | — |
| parent_account_id | BIGINT | Yes | — | FK→chart_of_accounts.id ondelete=- |
| normal_balance | VARCHAR(10) | No | 'DEBIT' | — |
| is_postable | BOOLEAN | No | True | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| parent_account_id | chart_of_accounts.id | - |

#### Indexes and constraints

- unique `uq_coa_code` (account_code)

### Table: `document_sequences`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** DocumentSequence  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| document_type | VARCHAR(64) | No | — | — |
| period_year | INTEGER | No | — | — |
| prefix | VARCHAR(16) | No | — | — |
| last_value | BIGINT | No | 0 | — |
| padding_length | INTEGER | No | 6 | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_sequences_type_year` (document_type, period_year)

### Table: `financial_accounts`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FinancialAccount  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| account_id | BIGINT | No | — | FK→chart_of_accounts.id ondelete=- |
| account_name | VARCHAR(255) | No | — | — |
| account_type | VARCHAR(32) | No | 'BANK' | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| bank_name | VARCHAR(255) | Yes | — | — |
| account_number_masked | VARCHAR(64) | Yes | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| account_id | chart_of_accounts.id | - |

#### Indexes and constraints

- unique `uq_financial_accounts_account` (account_id)

### Table: `financial_document_allocations`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FinancialDocumentAllocation  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| payment_document_id | BIGINT | No | — | FK→financial_documents.id ondelete=- |
| target_document_id | BIGINT | No | — | FK→financial_documents.id ondelete=- |
| allocated_amount | NUMERIC(19, 4) | No | — | — |
| allocated_currency_code | VARCHAR(3) | No | 'USD' | — |
| exchange_rate | NUMERIC(19, 8) | No | 1 | — |
| allocated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| idempotency_key | VARCHAR(128) | Yes | — | UNIQUE |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| payment_document_id | financial_documents.id | - |
| target_document_id | financial_documents.id | - |
| created_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_financial_document_allocations_payment_document_id` on (payment_document_id)
- index `ix_financial_document_allocations_target_document_id` on (target_document_id)
- unique `uq_financial_document_allocations_idempotency_key` (idempotency_key)

### Table: `financial_document_lines`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FinancialDocumentLine  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| financial_document_id | BIGINT | No | — | FK→financial_documents.id ondelete=CASCADE |
| line_no | INTEGER | No | 1 | — |
| description | TEXT | No | '' | — |
| fee_type_id | BIGINT | Yes | — | FK→fee_types.id ondelete=- |
| quantity | NUMERIC(12, 3) | No | 1 | — |
| unit_code | VARCHAR(32) | Yes | — | — |
| unit_price | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_rate | NUMERIC(7, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| line_amount | NUMERIC(19, 4) | No | 0 | — |
| service_order_id | BIGINT | Yes | — | FK→service_orders.id ondelete=- |
| service_order_container_id | BIGINT | Yes | — | FK→service_order_containers.id ondelete=- |
| account_id | BIGINT | Yes | — | FK→chart_of_accounts.id ondelete=- |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | - |
| service_order_container_id | service_order_containers.id | - |
| account_id | chart_of_accounts.id | - |
| financial_document_id | financial_documents.id | CASCADE |
| fee_type_id | fee_types.id | - |

#### Indexes and constraints

- index `ix_financial_document_lines_financial_document_id` on (financial_document_id)
- unique `uq_financial_document_lines_no` (financial_document_id, line_no)

### Table: `financial_document_postings`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FinancialDocumentPosting  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| financial_document_id | BIGINT | No | — | FK→financial_documents.id ondelete=- |
| journal_entry_id | BIGINT | No | — | FK→journal_entries.id ondelete=- |
| posting_role | VARCHAR(32) | No | 'ORIGINAL_POSTING' | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| journal_entry_id | journal_entries.id | - |
| financial_document_id | financial_documents.id | - |

#### Indexes and constraints

- unique `uq_fin_doc_postings` (financial_document_id, journal_entry_id)

### Table: `financial_document_sources`

**Module:** Finance & Accounting  
**Purpose:** Source quotation line links for a financial document's lines.  
**SQLAlchemy Model:** FinancialDocumentSource  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| financial_document_id | BIGINT | No | — | FK→financial_documents.id ondelete=CASCADE |
| source_type | VARCHAR(64) | No | — | — |
| source_id | BIGINT | No | — | — |
| relationship_type | VARCHAR(32) | No | 'GENERATED_FROM' | — |
| idempotency_key | VARCHAR(128) | Yes | — | UNIQUE |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| financial_document_id | financial_documents.id | CASCADE |

#### Indexes and constraints

- index `uq_fin_doc_source_charge` on (source_type, source_id), UNIQUE
- index `ix_financial_document_sources_financial_document_id` on (financial_document_id)
- unique `uq_fin_doc_sources` (financial_document_id, source_type, source_id, relationship_type)
- unique `uq_financial_document_sources_idempotency_key` (idempotency_key)

### Table: `financial_documents`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** FinancialDocument  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| document_no | VARCHAR(50) | No | — | — |
| document_type | VARCHAR(32) | No | — | — |
| document_date | DATE | No | — | — |
| posting_date | DATE | Yes | — | — |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| party_id | BIGINT | Yes | — | FK→business_parties.id ondelete=- |
| service_order_id | BIGINT | Yes | — | FK→service_orders.id ondelete=- |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| exchange_rate | NUMERIC(19, 8) | No | 1 | — |
| base_currency_code | VARCHAR(3) | Yes | — | — |
| description | TEXT | Yes | — | — |
| reference_number | VARCHAR(128) | Yes | — | — |
| due_date | DATE | Yes | — | — |
| payment_method_code | VARCHAR(64) | Yes | — | — |
| financial_account_id | BIGINT | Yes | — | FK→financial_accounts.id ondelete=- |
| value_date | DATE | Yes | — | — |
| subtotal_amount | NUMERIC(19, 4) | No | 0 | — |
| discount_amount | NUMERIC(19, 4) | No | 0 | — |
| tax_amount | NUMERIC(19, 4) | No | 0 | — |
| total_amount | NUMERIC(19, 4) | No | 0 | — |
| base_subtotal_amount | NUMERIC(19, 4) | No | 0 | — |
| base_discount_amount | NUMERIC(19, 4) | No | 0 | — |
| base_tax_amount | NUMERIC(19, 4) | No | 0 | — |
| base_total_amount | NUMERIC(19, 4) | No | 0 | — |
| paid_amount | NUMERIC(19, 4) | No | 0 | — |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| posted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| posted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| reversed_document_id | BIGINT | Yes | — | FK→financial_documents.id ondelete=- |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| service_order_id | service_orders.id | - |
| created_by_user_id | users.id | - |
| financial_account_id | financial_accounts.id | - |
| posted_by_user_id | users.id | - |
| party_id | business_parties.id | - |
| reversed_document_id | financial_documents.id | - |

#### Indexes and constraints

- index `ix_financial_documents_status` on (status)
- index `ix_financial_documents_document_type` on (document_type)
- unique `uq_financial_documents_no` (document_no)

### Table: `journal_entries`

**Module:** Finance & Accounting  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** JournalEntry  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| entry_no | VARCHAR(50) | No | — | — |
| entry_type | VARCHAR(64) | No | 'MANUAL' | — |
| entry_date | DATE | No | — | — |
| posting_date | DATE | No | — | — |
| accounting_period_id | BIGINT | Yes | — | FK→accounting_periods.id ondelete=- |
| status | VARCHAR(20) | No | 'DRAFT' | — |
| description | TEXT | Yes | — | — |
| source_document_id | BIGINT | Yes | — | FK→financial_documents.id ondelete=- |
| posting_rule_id | BIGINT | Yes | — | FK→posting_rules.id ondelete=- |
| reversal_of_journal_entry_id | BIGINT | Yes | — | FK→journal_entries.id ondelete=- |
| created_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| posted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| posted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| debit_total | NUMERIC(19, 4) | No | 0 | — |
| credit_total | NUMERIC(19, 4) | No | 0 | — |
| data | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| source_document_id | financial_documents.id | - |
| posted_by_user_id | users.id | - |
| posting_rule_id | posting_rules.id | - |
| reversal_of_journal_entry_id | journal_entries.id | - |
| created_by_user_id | users.id | - |
| accounting_period_id | accounting_periods.id | - |

#### Indexes and constraints

- index `ix_journal_entries_status` on (status)
- index `ix_journal_entries_posting_rule_id` on (posting_rule_id)
- unique `uq_journal_entries_no` (entry_no)

### Table: `journal_entry_lines`

**Module:** Finance & Accounting  
**Purpose:** Double-entry lines (debit/credit) for one journal entry — verified balanced by code.  
**SQLAlchemy Model:** JournalEntryLine  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| journal_entry_id | BIGINT | No | — | FK→journal_entries.id ondelete=CASCADE |
| line_no | INTEGER | No | 1 | — |
| account_id | BIGINT | No | — | FK→chart_of_accounts.id ondelete=- |
| party_id | BIGINT | Yes | — | FK→business_parties.id ondelete=- |
| service_order_id | BIGINT | Yes | — | FK→service_orders.id ondelete=- |
| financial_document_id | BIGINT | Yes | — | FK→financial_documents.id ondelete=- |
| description | TEXT | Yes | — | — |
| debit_amount | NUMERIC(19, 4) | No | 0 | — |
| credit_amount | NUMERIC(19, 4) | No | 0 | — |
| currency_code | VARCHAR(3) | No | 'USD' | — |
| exchange_rate | NUMERIC(19, 8) | No | 1 | — |
| base_debit_amount | NUMERIC(19, 4) | No | 0 | — |
| base_credit_amount | NUMERIC(19, 4) | No | 0 | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| account_id | chart_of_accounts.id | - |
| service_order_id | service_orders.id | - |
| journal_entry_id | journal_entries.id | CASCADE |
| financial_document_id | financial_documents.id | - |
| party_id | business_parties.id | - |

#### Indexes and constraints

- index `ix_journal_entry_lines_account_id` on (account_id)
- index `ix_journal_entry_lines_journal_entry_id` on (journal_entry_id)
- unique `uq_journal_entry_lines_no` (journal_entry_id, line_no)

### Table: `posting_rules`

**Module:** Finance & Accounting  
**Purpose:** Maps a document type (optionally narrowed to one fee type) to its accounts  
**SQLAlchemy Model:** PostingRule  
**Source:** `app/modules/finance/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| document_type | VARCHAR(32) | No | — | — |
| fee_type_id | BIGINT | Yes | — | FK→fee_types.id ondelete=- |
| debit_account_id | BIGINT | No | — | FK→chart_of_accounts.id ondelete=- |
| credit_account_id | BIGINT | No | — | FK→chart_of_accounts.id ondelete=- |
| tax_account_id | BIGINT | Yes | — | FK→chart_of_accounts.id ondelete=- |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| priority | INTEGER | No | 0 | — |
| description | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| fee_type_id | fee_types.id | - |
| tax_account_id | chart_of_accounts.id | - |
| credit_account_id | chart_of_accounts.id | - |
| debit_account_id | chart_of_accounts.id | - |

#### Indexes and constraints

- index `uq_posting_rules_active_priority` on (priority), UNIQUE
- index `ix_posting_rules_resolution` on (document_type, status, priority)

### Table: `app_settings`

**Module:** Settings  
**Purpose:** One keyed application-configuration document  
**SQLAlchemy Model:** AppSetting  
**Source:** `app/modules/settings/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| setting_key | VARCHAR(120) | No | — | — |
| setting_group | VARCHAR(60) | No | — | — |
| setting_value | JSONB | No | python:dict() | — |
| description | TEXT | Yes | — | — |
| updated_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| updated_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_app_settings_group` on (setting_group)
- unique `uq_app_settings_key` (setting_key)

### Table: `password_reset_tokens`

**Module:** Administration (Auth/RBAC)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** PasswordResetToken  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| user_id | BIGINT | No | — | FK→users.id ondelete=CASCADE |
| email | VARCHAR(255) | No | — | — |
| code_hash | VARCHAR(128) | No | — | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| used_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | CASCADE |

#### Indexes and constraints

- index `ix_password_reset_tokens_user_id` on (user_id)

### Table: `permissions`

**Module:** Administration (Auth/RBAC)  
**Purpose:** Display metadata for a permission code  
**SQLAlchemy Model:** Permission  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(128) | No | — | UNIQUE |
| name | VARCHAR(255) | No | — | — |
| module | VARCHAR(64) | No | general | — |
| resource | VARCHAR(64) | No | — | — |
| action | VARCHAR(64) | No | — | — |
| description | TEXT | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_permissions_code` (code)

### Table: `roles`

**Module:** Administration (Auth/RBAC)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** Role  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| code | VARCHAR(64) | No | — | UNIQUE |
| name | VARCHAR(255) | No | — | — |
| description | TEXT | Yes | — | — |
| is_system_role | BOOLEAN | No | False | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_roles_code` (code)

### Table: `used_refresh_tokens`

**Module:** Administration (Auth/RBAC)  
**Purpose:** Refresh-token single-use ledger (already-used tokens rejected).  
**SQLAlchemy Model:** UsedRefreshToken  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| token_hash | VARCHAR(128) | No | — | PK |
| session_id | BIGINT | No | — | FK→user_sessions.id ondelete=CASCADE |
| used_at | TIMESTAMP WITH TIME ZONE | No | — | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| session_id | user_sessions.id | CASCADE |

#### Indexes and constraints

- index `ix_used_refresh_tokens_session_id` on (session_id)

### Table: `user_credentials`

**Module:** Administration (Auth/RBAC)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** UserCredential  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| user_id | BIGINT | No | Identity/autoincrement | PK |
| password_hash | TEXT | No | — | — |
| password_algorithm | VARCHAR(32) | No | 'argon2id' | — |
| password_changed_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| must_change_password | BOOLEAN | No | false | — |
| failed_attempt_count | INTEGER | No | 0 | — |
| locked_until | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | CASCADE |

#### Indexes and constraints

Beyond PK/FK, none declared at ORM level.

### Table: `user_sessions`

**Module:** Administration (Auth/RBAC)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** UserSession  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| user_id | BIGINT | No | — | FK→users.id ondelete=CASCADE |
| refresh_token_hash | VARCHAR(128) | No | — | UNIQUE |
| device_name | VARCHAR(255) | Yes | — | — |
| ip_address | VARCHAR(64) | Yes | — | — |
| user_agent | TEXT | Yes | — | — |
| last_used_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| last_activity_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| revoked_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| remember_me | BOOLEAN | No | false | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | CASCADE |

#### Indexes and constraints

- index `ix_user_sessions_user_id` on (user_id)
- unique `uq_user_sessions_refresh_token_hash` (refresh_token_hash)

### Table: `users`

**Module:** Administration (Auth/RBAC)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** User  
**Source:** `app/modules/auth/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| user_code | VARCHAR(50) | No | — | UNIQUE |
| username | VARCHAR(100) | No | — | UNIQUE |
| email | VARCHAR(255) | No | — | UNIQUE |
| display_name | VARCHAR(255) | No | — | — |
| status | VARCHAR(20) | No | 'ACTIVE' | — |
| locale | VARCHAR(10) | No | 'en' | — |
| timezone | VARCHAR(64) | No | 'UTC' | — |
| system_identity | VARCHAR(64) | Yes | — | UNIQUE |
| last_login_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| token_version | INTEGER | No | 0 | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- unique `uq_users_username` (username)
- unique `uq_users_system_identity` (system_identity)
- unique `uq_users_email` (email)
- unique `uq_users_user_code` (user_code)

### Table: `archive_records`

**Module:** Administration (Archive)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ArchiveRecord  
**Source:** `app/modules/archive/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| entity_type | VARCHAR(64) | No | — | — |
| entity_id | BIGINT | No | — | — |
| record_reference | VARCHAR(255) | No | — | — |
| status | VARCHAR(20) | No | 'ARCHIVED' | — |
| deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |
| original_owner_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |
| deleted_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| restored_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |
| restored_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| hard_deleted_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=SET NULL |
| hard_deleted_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| snapshot_json | JSONB | No | python:dict() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| hard_deleted_by_user_id | users.id | SET NULL |
| restored_by_user_id | users.id | SET NULL |
| deleted_by_user_id | users.id | SET NULL |
| original_owner_user_id | users.id | SET NULL |

#### Indexes and constraints

- index `ix_archive_records_entity_type` on (entity_type)
- index `ix_archive_records_entity_id` on (entity_id)
- index `ix_archive_records_deleted_by_user_id` on (deleted_by_user_id)
- index `ix_archive_records_deleted_at` on (deleted_at)
- index `ix_archive_records_status` on (status)
- unique `uq_archive_records_entity` (entity_type, entity_id)

### Table: `backup_logs`

**Module:** Backup & Restore  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** BackupLog  
**Source:** `app/modules/backup/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| run_id | BIGINT | Yes | — | FK→backup_runs.id ondelete=CASCADE |
| level | VARCHAR(16) | No | 'info' | — |
| table_name | VARCHAR(128) | Yes | — | — |
| message | TEXT | No | — | — |
| detail | JSONB | Yes | — | — |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| run_id | backup_runs.id | CASCADE |

#### Indexes and constraints

- index `ix_backup_logs_run_id` on (run_id)

### Table: `backup_records`

**Module:** Backup & Restore  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** BackupRecord  
**Source:** `app/modules/backup/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| run_id | BIGINT | Yes | — | FK→backup_runs.id ondelete=SET NULL |
| table_name | VARCHAR(128) | No | — | — |
| record_id | VARCHAR(255) | No | — | — |
| backup_version | BIGINT | No | 1 | — |
| backup_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |
| change_kind | VARCHAR(16) | No | 'insert' | — |
| row_hash | VARCHAR(64) | No | — | — |
| data | JSONB | No | python:dict() | — |
| synced | BOOLEAN | No | False | — |
| synced_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| run_id | backup_runs.id | SET NULL |

#### Indexes and constraints

- index `ix_backup_records_synced` on (synced)
- index `ix_backup_records_table_name` on (table_name)
- index `ix_backup_records_table_record` on (table_name, record_id)
- unique `uq_backup_records_version` (table_name, record_id, row_hash)

### Table: `backup_runs`

**Module:** Backup & Restore  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** BackupRun  
**Source:** `app/modules/backup/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| trigger | VARCHAR(16) | No | 'scheduled' | — |
| status | VARCHAR(16) | No | 'running' | — |
| started_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |
| finished_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| duration_ms | INTEGER | Yes | — | — |
| tables_total | INTEGER | No | 0 | — |
| tables_processed | INTEGER | No | 0 | — |
| rows_scanned | INTEGER | No | 0 | — |
| rows_inserted | INTEGER | No | 0 | — |
| rows_updated | INTEGER | No | 0 | — |
| rows_skipped | INTEGER | No | 0 | — |
| rows_failed | INTEGER | No | 0 | — |
| spreadsheet_id | VARCHAR(255) | Yes | — | — |
| triggered_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| message | TEXT | Yes | — | — |
| detail | JSONB | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| triggered_by_user_id | users.id | - |

#### Indexes and constraints

- index `ix_backup_runs_status` on (status)

### Table: `backup_states`

**Module:** Backup & Restore  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** BackupState  
**Source:** `app/modules/backup/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| table_name | VARCHAR(128) | No | — | — |
| record_id | VARCHAR(255) | No | — | — |
| row_hash | VARCHAR(64) | No | — | — |
| backup_version | BIGINT | No | 1 | — |
| last_backup_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- index `ix_backup_states_table_name` on (table_name)
- unique `uq_backup_states_record` (table_name, record_id)

### Table: `audit_events`

**Module:** Audit  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** AuditEvent  
**Source:** `app/modules/audit/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| actor_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| event_type | VARCHAR(64) | No | — | — |
| entity_type | VARCHAR(64) | No | — | — |
| entity_id | BIGINT | No | — | — |
| action | VARCHAR(64) | No | — | — |
| result | VARCHAR(32) | No | 'SUCCESS' | — |
| reason | TEXT | Yes | — | — |
| request_id | VARCHAR(64) | Yes | — | — |
| correlation_id | VARCHAR(64) | Yes | — | — |
| ip_address | VARCHAR(64) | Yes | — | — |
| user_agent | TEXT | Yes | — | — |
| before_json | JSONB | Yes | — | — |
| after_json | JSONB | Yes | — | — |
| metadata_json | JSONB | Yes | — | — |
| amount | NUMERIC(19, 4) | Yes | — | — |
| occurred_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| id | BIGINT | No | Identity/autoincrement | PK |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| actor_user_id | users.id | - |

#### Indexes and constraints

- index `ix_audit_events_entity_type` on (entity_type)
- index `ix_audit_events_event_type` on (event_type)
- index `ix_audit_events_entity_id` on (entity_id)

### Table: `import_jobs`

**Module:** Import / Export  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** ImportJob  
**Source:** `app/modules/excel_io/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| module | VARCHAR(64) | No | — | — |
| file_name | VARCHAR(255) | No | — | — |
| mode | VARCHAR(20) | No | — | — |
| status | VARCHAR(20) | No | — | — |
| template_version | INTEGER | No | 1 | — |
| total_rows | INTEGER | No | 0 | — |
| created_count | INTEGER | No | 0 | — |
| updated_count | INTEGER | No | 0 | — |
| skipped_count | INTEGER | No | 0 | — |
| failed_count | INTEGER | No | 0 | — |
| error_summary | TEXT | Yes | — | — |
| started_by_user_id | BIGINT | Yes | — | FK→users.id ondelete=- |
| completed_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| started_by_user_id | users.id | - |

#### Indexes and constraints

Beyond PK/FK, none declared at ORM level.

### Table: `import_sessions`

**Module:** Import / Export  
**Purpose:** A validated, not-yet-committed import preview (single-use claim row)  
**SQLAlchemy Model:** ImportSession  
**Source:** `app/modules/excel_io/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| token | VARCHAR(64) | No | — | UNIQUE |
| user_id | BIGINT | No | — | FK→users.id ondelete=- |
| module | VARCHAR(64) | No | — | — |
| mode | VARCHAR(20) | No | — | — |
| file_name | VARCHAR(255) | No | — | — |
| checksum | VARCHAR(64) | No | — | — |
| template_version | INTEGER | No | 1 | — |
| rows_data | JSON | No | — | — |
| preview_data | JSON | No | — | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | - |

#### Indexes and constraints

- unique `uq_import_sessions_token` (token)

### Table: `notification_incidents`

**Module:** Telegram (notification jobs)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** NotificationIncident  
**Source:** `app/modules/telegram/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| key | VARCHAR(120) | No | — | PK |
| first_seen_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| last_sent_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| state | VARCHAR(16) | No | 'PENDING' | — |
| measured_value | INTEGER | No | 0 | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

Beyond PK/FK, none declared at ORM level.

### Table: `notification_outbox`

**Module:** Telegram (notification jobs)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** NotificationOutbox  
**Source:** `app/modules/telegram/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| event_type | VARCHAR(80) | No | — | — |
| category | VARCHAR(24) | No | — | — |
| severity | VARCHAR(16) | No | — | — |
| destination_type | VARCHAR(16) | No | — | — |
| destination_reference | BIGINT | No | — | — |
| payload | JSONB | No | python:dict() | — |
| sensitive_payload | TEXT | Yes | — | — |
| status | VARCHAR(16) | No | 'PENDING' | — |
| attempts | INTEGER | No | 0 | — |
| max_attempts | INTEGER | No | 3 | — |
| next_attempt_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| claim_token | VARCHAR(64) | Yes | — | — |
| locked_until | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| sent_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| last_error | VARCHAR(64) | Yes | — | — |
| deduplication_key | VARCHAR(200) | No | — | UNIQUE |
| id | BIGINT | No | Identity/autoincrement | PK |
| created_at | TIMESTAMP WITH TIME ZONE | No | now() | — |
| updated_at | TIMESTAMP WITH TIME ZONE | No | now() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- index `ix_notification_history` on (created_at)
- index `ix_notification_due` on (status, next_attempt_at)
- CHECK `ck_notification_outbox_notification_status`: `status IN ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELLED')`
- unique `uq_notification_outbox_deduplication_key` (deduplication_key)
- CHECK `ck_notification_outbox_recovery_private_only`: `category <> 'recovery' OR destination_type = 'PRIVATE'`
- CHECK `ck_notification_outbox_secret_private_only`: `sensitive_payload IS NULL OR (category = 'recovery' AND destination_type = 'PRIVATE')`
- CHECK `ck_notification_outbox_notification_destination`: `destination_type IN ('PRIVATE', 'ADMIN', 'CLIENT')`

### Table: `telegram_links`

**Module:** Telegram (notification jobs)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TelegramLink  
**Source:** `app/modules/telegram/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| user_id | BIGINT | No | Identity/autoincrement | PK |
| telegram_user_id | BIGINT | No | — | UNIQUE |
| bot_id | BIGINT | No | — | — |
| chat_id | BIGINT | No | — | — |
| display_name | VARCHAR(255) | No | — | — |
| verified_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |
| blocked_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | CASCADE |

#### Indexes and constraints

- CHECK `ck_telegram_links_private_identity`: `chat_id = telegram_user_id AND telegram_user_id > 0`
- unique `uq_telegram_links_telegram_user_id` (telegram_user_id)

### Table: `telegram_pairings`

**Module:** Telegram (notification jobs)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TelegramPairing  
**Source:** `app/modules/telegram/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| token_hash | VARCHAR(64) | No | — | PK |
| user_id | BIGINT | No | — | FK→users.id ondelete=CASCADE |
| kind | VARCHAR(16) | No | — | — |
| bot_id | BIGINT | No | — | — |
| expires_at | TIMESTAMP WITH TIME ZONE | No | — | — |
| used_at | TIMESTAMP WITH TIME ZONE | Yes | — | — |
| candidate_id | BIGINT | Yes | — | — |
| candidate_name | VARCHAR(255) | Yes | — | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

| Column | References | On Delete |
|--------|-----------|-----------|
| user_id | users.id | CASCADE |

#### Indexes and constraints

- index `ix_telegram_pairings_user_id` on (user_id)
- unique `uq_telegram_pairing_owner_kind` (user_id, kind)
- CHECK `ck_telegram_pairings_pairing_kind`: `kind IN ('PRIVATE', 'GROUP')`

### Table: `telegram_updates`

**Module:** Telegram (notification jobs)  
**Purpose:** No model docstring.  
**SQLAlchemy Model:** TelegramUpdate  
**Source:** `app/modules/telegram/models.py`

#### Columns

| Column | PostgreSQL Type* | Nullable | Default | Key / Constraint |
|--------|------------------|----------|---------|------------------|
| update_id | BIGINT | No | Identity/autoincrement | PK |
| received_at | TIMESTAMP WITH TIME ZONE | No | python:utcnow() | — |

*Compiled for the PostgreSQL dialect from ORM types; live-catalog types NOT VERIFIED.

#### Relationships (foreign keys)

No database-level foreign keys.

#### Indexes and constraints

- index `ix_telegram_updates_received_at` on (received_at)

---

## 8. CRUD / Architecture Matrix (VERIFIED CODE at file level)

| Entity domain | Create | Update | Delete/Archive | Validation | API Router | Import/Export |
|---------------|--------|--------|----------------|------------|------------|----------------|
| Master Data (12 reference collections) | `master_data/service.py` spec-driven create (one generic pipeline) | same pipeline (`update_reference`) | soft delete via `delete_reference` (checks references before removing) | Pydantic-free service schemas per `Spec` (`master_data/specs.py`) | `master_data/router.py` (collection-scoped, `_collection_guard` permission check per operation) | `excel_io` registry (12/12 modules, staged import) |
| Component Tabs / Groups / Attributes | `master_data/service.py` + component config services | editors per collection | soft delete (group membership rows removed) | `component-config` field validators | `master_data/router.py` | create-only imports via `excel_io/config_io.py` |
| Configuration Versions | publish/draft lifecycle in `configuration` service | draft edits only | draft delete; published immutable | five-sheet workbook validator (`excel_io/config_io.py`) | router under configurations | whole-workbook import → always new DRAFT |
| Quotations | `quotations/service.py` (create + revision snapshots) | revision-level edits (new revision rows) | soft delete/archive | revision validation, customer/currency refs | `quotations/router.py` | export only; no row import |
| Service Orders | `operations/service.py` (create from quotation or standalone draft) | containers/charges/milestones/pricing sub-edits | soft-delete style removal of drafts | quotation link validation, container requirements | `operations/router.py` | export only; no row import |
| Service Charges | `operations` charge-line services with calculator reuse | add/edit/delete lines on non-finished orders | line deletion | feeType × quantity × unit price ↔ amount checks | `operations/router.py` | export only |
| Financial Documents | `finance/service.py` posting pipeline (draft → POSTED) | draft-only edits; posted immutable | not deletable once posted (audit state) | balanced double-entry, period open, currency snapshot | `finance/router.py` | export only; deliberate no-import |
| Journal Entries | created by posting service only | never edited after posting | reversal instead of delete | debit == credit per entry | same module | no import |
| Payments/Allocations | allocation services bound to documents | allocation amount caps | allocation removal flagged for history | allocations ≤ document balance | `finance/router.py` | no import |
| Users / Roles / Permissions | `auth/service.py` (+ Casbin sync) | profile, role grants | deactivate + audit | credential checks (hash never exposed) | `auth/router.py` | no import (admin-only user creation) |
| Document Sequences | sequence admin service | counter settings | — | format/zero-pad validation | admin router | no import (numbering integrity) |
| App Settings | `settings/service.py` `update_app_config` per-group write | same (one row per group) | reset endpoints (danger zone) | `RecordSchema` allowlist + group validators | `settings/router.py` | no import |
| Backup/Storage Jobs | `backup`, `storage` services + schedulers | dry-run/retry endpoints | purge endpoints for backups | advisory lock single-run; status snapshots | both routers | no import |
| Audit Events | `audit/service.py` writing to all sensitive actions | — | retention policy only | — | `audit/router.py` read-only | no import |
| Import sessions | `excel_io/service.py` staged sessions | cancel/commit | TTL expiry cleanup | size/row caps; per-session owner checks | `excel_io/router.py` | this IS the importer |

## 9. Master Data Analysis

Shared generic Spec pipeline (`master_data/service.py`, `master_data/specs.py`): one
`Spec` per collection gives immutable fields, enums, required list and reference maps.
Consequences (all code-verified):

- **Identifiers**: `code` for most collections; `partyCode` for business parties,
  `assetCode` for transport assets, `name` for transport asset identity types.
- **Duplicate prevention**: unique checks in service + confirmed DB unique indexes
  documented per table in §7.
- **Active/inactive**: every reference table carries `status` enum (`ACTIVE`/`INACTIVE`)
  plus soft delete — an inactive record still resolves for history records.
- **Reference usage**: business parties reference party roles AND carry their own role
  set (`business_party_roles` join table); transport assets reference a transport type.
- **Deletion restrictions**: `delete_reference` refuses deletes referenced by other rows.
- **Import/seed**: 12/12 importable (staged, atomic); a seed script populates startup defaults.

## 10. Configuration Analysis

Held inside `master_data/models.py`: `component_tabs` ⇄ `component_tab_groups` ⇄
`component_groups` ⇄ `component_group_attributes` ⇄ `component_attributes` (order and
render overrides live on the link rows). Publish flow: current configuration packaged
into a **five-sheet** `configuration_versions` workbook; latest published snapshot is
authoritative for dynamic forms; drafts remain editable; imports (Excel whole-workbook,
or per-collection create-only rows) always materialize as a new DRAFT (never PUBLISHED),
and codes are used instead of DB ids. Import validation resolves tabs/groups/attributes
in dependency order and never mutates published history.

Duplication note: naming/inference for tab/group metadata shares columns such as
`label`, `name`, `nameKm` across sibling tables — flagged as a consolidation candidate
(§13) but each is consumed by a distinct editor; e.g. `groupId` vs group `code` names
still need a mapping table review.

## 11. Operations Analysis

`quotations` (header + status + currency + `source_service_order_id` link) with
**revision snapshot** tables (`quotation_revisions`, `..._lines/containers/places`):
each revision is a point-in-time snapshot; totals roll up from revisions; revisions
are deliberately denormalized. `quotation_conversions` ties a revision to the Service
Order it became (`service_order_id`, one per order).

`service_orders` created either from an accepted quotation (FSO link kept) or as a
fresh draft; container requirements feed actual containers with job numbers; charges
(`service_order_charges` header + line rows) mirror quotation services with currency-
aware amounts; pricing tables (`service_order_pricing(+lines)`) hold approval-time
pricing snapshots with the quotation snapshot for revalidation. Save keeps DRAFT;
Finish triggers the finance document generation — never during import.

Status transitions (code-verified): Service Orders carry `ACTIVE|INACTIVE|FINISHED`
(`ORDER_STATUSES` in `operations/schemas.py`), finishing is an explicit action with
audit event `SERVICE_ORDER_FINISHED`; movements track `PLANNED|IN_TRANSIT|ARRIVED|
COMPLETED|CANCELLED`. Quotation/service `DRAFT` defaults live on the models.

## 12. Finance Analysis

Double-entry: `financial_documents` (document header, currency + rate snapshot, period
windows, balance check) → `financial_document_lines` (+ `..._sources` linking back to
the originating quotation/service lines) → `financial_document_postings` and
`journal_entries` / `journal_entry_lines` (each entry debit total == credit total).
`chart_of_accounts` + `financial_accounts` own account codes referenced by lines and
by document type defaults. `accounting_periods` gate posting; period closing is a
dedicated flow in the `finance` module (endpoint-hidden state, not a generic row write).

**Operational vs derived**: document/journal tables are operational; postings, and the
read-model aggregates (reports) are derived. Posted documents are never re-written;
correction is a reversal document, and reports never mutate source tables.

## 13. Administration Analysis

Auth/RBAC: `users` ↔ `user_roles` ↔ `roles` ↔ `role_permissions` ↔ `permissions`;
Casbin policies are the runtime enforcement; role updates re-arm caches (`cache.bump`).
Credential tables follow write-only secret rules: `user_credentials` (hash never returned),
`used_refresh_tokens` single-use ledger (already-used tokens rejected), `user_sessions`,
`password_reset_tokens`. `document_sequences` are managed outside imports (numbering
source of truth). `app_settings` (JSON per group) + `module_records` transitional mirror;
`audit_events` is the single audit trail (write-only from services, read-only via API).

## 14. Entity Relationship Overview

Most-in-referenced tables (FK-in Edge count, VERIFIED CODE):
- `users` receives 47 foreign keys from other app tables.
- `service_orders` receives 13 foreign keys from other app tables.
- `business_parties` receives 8 foreign keys from other app tables.
- `financial_documents` receives 8 foreign keys from other app tables.
- `chart_of_accounts` receives 7 foreign keys from other app tables.
- `fee_types` receives 5 foreign keys from other app tables.
- `places` receives 5 foreign keys from other app tables.
- `quotation_revisions` receives 5 foreign keys from other app tables.
- `configuration_versions` receives 4 foreign keys from other app tables.
- `component_groups` receives 3 foreign keys from other app tables.
- `trade_directions` receives 3 foreign keys from other app tables.
- `journal_entries` receives 3 foreign keys from other app tables.

```mermaid
erDiagram
  BUSINESS_PARTIES ||--o{ QUOTATIONS : customer
  QUOTATIONS ||--o{ QUOTATION_REVISIONS : snapshots
  QUOTATION_REVISIONS ||--o{ QUOTATION_REVISION_LINES : line snapshots
  QUOTATION_REVISIONS ||--o{ QUOTATION_CONVERSIONS : converts to
  QUOTATION_CONVERSIONS ||--o{ SERVICE_ORDERS : one per SO
  SERVICE_ORDERS ||--o{ SERVICE_ORDER_CHARGES : charges
  SERVICE_ORDER_CHARGES ||--o{ SERVICE_ORDER_CHARGE_LINES : lines
  SERVICE_ORDERS ||--o{ SERVICE_ORDER_CONTAINERS : containers
  FINANCIAL_DOCUMENTS ||--o{ FINANCIAL_DOCUMENT_LINES : lines
  FINANCIAL_DOCUMENTS ||--o{ FINANCIAL_DOCUMENT_SOURCES : source quotations
  FINANCIAL_DOCUMENTS ||--o{ JOURNAL_ENTRIES : posting
  JOURNAL_ENTRIES ||--o{ JOURNAL_ENTRY_LINES : debit and credit lines
  COMPONENT_TABS ||--o{ COMPONENT_TAB_GROUPS : order
  COMP_TAB_GROUPS ||--o{ COMPONENT_GROUPS : to group
  COMPONENT_GROUPS ||--o{ COMPONENT_GROUP_ATTRIBUTES : members
  COMPONENT_GROUP_ATTRIBUTES ||--o{ COMPONENT_ATTRIBUTES : reusable attribute
  USERS ||--o{ AUDIT_EVENTS : who
```

**Cross-module dependencies** (chain, verified): Master Data → Quotation revisions (customer,
currency, fee-type, trade-direction references) → Service Orders (same + containers) →
Financial Documents (fee/charge amounts, periods, accounts) → Journals (accounts, periods)
→ Period Closing. Configuration versions are referenced only by dynamic forms (frontend),
not by FKs from operational tables.

## 15. Existing Design Issues (evidence-based; CONFIRMED vs needs review)

| Module | Table | Finding | Evidence | Impact | Suggested review |
|--------|-------|---------|----------|--------|------------------|
| Settings | app_settings vs module_records | Same business data stored in two tables (transitional write-through mirror) | `_mirror_legacy_settings` is called on every settings write | Double storage/effort for no token relationship | CONFIRMED: retire legacy mirror once no rollback build needs it |
| Operations | service_order_pricing | Header/line split exists while service_order_charges also carries amounts | Two amount stores checked separately | Risk of drift between rider and charges | CONFIRMED per schema: single-source-of-truth review |
| Operations | service_order_component_rows | Component rows table likely overlaps component_tabs dynamic rows | exists in metadata and no FK from it to component tables | Orphan-ish rows | INFERRED — verify writer |
| Master data | business_parties.roles JSON | `roles` JSON column mirrors the `business_party_roles` join table (kept only for pre-migration clients) | model comment on `BusinessParty.roles` | Two role sources; stale mirror risk | CONFIRMED: keep single writer; retire mirror column with care |
| Master data | place_role_places, business_party_roles | Join tables mirror role metadata also embedded per record | join tables exist alongside parent refs | Two sources of truth in reads | CONFIRMED per schema (many-to-many link tables) — acceptable; keep the JSON mirror out of import/export |
| Master data | document_types (row fact) | Custom types can only reference canonical posting behaviors, so labels never invent posting rules | model docstring on DocumentType | Positive constraint | CONFIRMED — preserve during any import automation |
| Finance | financial_document_postings | Posting rows attach to documents/journals without a DB-level uniqueness contract on (period, journal) | no unique constraint declared at ORM | Risk of double-posting duplicates only at app level | INFERRED — verify service uniqueness check |
| Quotations | quotation_conversions.service_order_id | The conversion table pins `service_order_id` as a unique plain big integer with no FK constraint | `quotations/models.py` (BigInteger, nullable=False, unique=True — no ForeignKey argument) | DB cannot enforce that a conversion points at a real Service Order | INFERRED — add an FK with ON DELETE PROTECT in a future migration |
| Configuration | component_group_attributes | Overrides `renderMode`/`displayOrder` are per-row despite group defaults | columns exist on link row | Duplication: three display-order sources | CONFIRMED per schema — review coupling |
| Backup | backup_records, backup_runs, backup_logs, backup_states | Four tables describe one pipeline (runs + records + logs + states) | 4 backup tables in metadata | Bookkeeping overhead, unclear chronology | CONFIRMED per schema — consolidate where rows are redundant logs |
| Auth | user_sessions, used_refresh_tokens | Refresh-token table and session table both track validity | separate parents/power relation | Cleanup scripts must align | CONFIRMED per schema — verify single writer |
| Import/Export | import_sessions.rows_data | Whole parsed workbook stored as JSON blob in one column | rows_data is a JSON column | Memory-heavy; can bloat DB | CONFIRMED via ORM type (JSON) — may need chunking for large imports |
| Multiple | *-by_user_id-style columns | Inconsistent attribute names across modules: created_by vs createdBy user variants | some tables use different user-column names | Refactor risk on joins | INFERRED — standardize accessors |
| Import/Export | financial documents | Deliberately NO import surface for finance/admin tables | absence from registry | None — is a safety feature | CONFIRMED — keep |
| Operations | quotation_revisions & snapshot tables | Deliberate denormalization (snapshot pattern) | Lines/containers/places store duplicated values with revisions | None if snapshots remain immutable | CONFIRMED — intentional design; never collapse historical snapshots |
| Storage | attachment rows | Attachment reference table found inside master_data/operations model modules instead of a dedicated module | module attribution | Cross-module coupling drift | INFERRED — check import/export coupling and export filters |

## 16. Import Readiness Matrix (VERIFIED CODE — `excel_io/registry.py`)

| Module | Entity | Import supported | Key | Relationships | Restrictions |
|--------|--------|------------------|-----|---------------|--------------|
| Master Data | Business Parties | Yes (xlsx/csv/json) | partyCode | party role assignments via `business_party_roles`; `roles` JSON is a legacy mirror | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Party Roles | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Place Roles | Yes (xlsx/csv/json) | code | places via `place_role_places` | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Trade Directions | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Container Types | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Transport Types | Yes (xlsx/csv/json) | code | used by transport assets | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Transport Assets | Yes (xlsx/csv/json) | assetCode | transportType reference | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Asset Identity Types | Yes (xlsx/csv/json) | name | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Capacity Units | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Fee Types | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Currencies | Yes (xlsx/csv/json) | code | — | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Master Data | Document Types | Yes (xlsx/csv/json) | code | accountingBehaviour fixed to canonical behaviours | service-defined uniqueness + enum/status validation; create/update pipeline reuse |
| Configuration | Component Attributes | Yes (create-only) | code | — (used by groups) | create-only: never overwrites, never publishes |
| Configuration | Component Groups | Yes (create-only) | code | tabs via link rows | create-only: never overwrites, never publishes |
| Configuration | Component Tabs | Yes (create-only) | code | groups via link rows | create-only: never overwrites, never publishes |
| Configuration | Configuration Versions | Yes (xlsx workbook) | whole-workbook | five-sheet snapshot | always creates a NEW DRAFT; published versions immutable |
| Quotations→Administration | Quotations | No | — | — | one-at-a-time document workflow; import not implemented by design |
| Quotations→Administration | Service Orders | No | — | — | draft created from quotations; import not implemented |
| Quotations→Administration | Service Charges | No | — | — | calculated lines; import not implemented |
| Quotations→Administration | Financial Documents / Journals | No | — | — | posted financial history; import forbidden |
| Quotations→Administration | Chart of Accounts / Accounts / Periods / Posting Rules | No | — | — | finance-critical; import disabled pending explicit domain command |
| Quotations→Administration | Users / RBAC / Sequences / Secrets | No | — | — | not importable (security: no password hashes, no tokens, no numbering) |

Formats: xlsx for all; csv/json for the single-sheet modules above (three-module
component config + configuration versions are xlsx-only workbooks).

## 17. Verification Legend

- **VERIFIED CODE** — read directly from checked-out backend/frontend source files.
- **VERIFIED DATABASE** — <none>: PostgreSQL catalog could not be read in this
  environment (no local psycopg2/DB reachability). No migrations or data touched.
- **INFERRED** — reasoning pattern without author's verification, needs confirmation.
- **NOT VERIFIED** — could not confirm.

## 18. Post-Review Resolution Log (2026-11-10, code-verified follow-up)

| Review finding | Outcome |
|----------------|---------|
| `quotation_conversions.service_order_id` had no FK | **FIXED**: ORM now declares `ForeignKey("service_orders.id", ondelete="RESTRICT")`; migration `c3d5f7a9b1e2` adds it with an orphan pre-check (fails loudly, deletes nothing); the order-delete service clears the ledger row in the same transaction, preserving existing API behaviour and the quotation-cleanup workflow. Verified on isolated PostgreSQL 16 (upgrade head, FK RESTRICT enforced, orphan insert refused, downgrade/re-upgrade). |
| `financial_document_postings` uniqueness only app-level | **ALREADY CORRECT**: `uq_fin_doc_postings (financial_document_id, journal_entry_id)` exists in the model; posting also holds row locks, checks `DUPLICATE_POSTING` and period status. |
| Configuration-version references from operational records | **ALREADY CORRECT**: `service_orders.configuration_version_id` declares `ForeignKey("configuration_versions.id", ondelete="SET NULL")`. |
| Published-version uniqueness | **ALREADY CORRECT**: partial unique index `uq_configuration_versions_published` on `status = 'PUBLISHED'`. |
| Business party role duplication | **LEGACY MIRROR ONLY**: the generic Spec writes only `business_party_roles`; the `roles` JSON column is a read-compat mirror for old clients. |
| Backup / restore capability | **EXTENDED**: a separate full DR workflow (`backup/dr.py`, `scripts/full_backup.py`, `POST /backup/full*`) now produces pg_dump-based encrypted archives with attachments, manifest and SHA-256 verification; the logical Sheets/R2 engine is preserved. Isolated pg_dump→pg_restore round-trip verified. |
| Attachment entity type validation | **IMPROVED**: new links must use a supported collection (`ATTACHMENT_ENTITY_TYPES`); unknown values are refused. Existence checks for each collection remain a follow-up (needs a generated collection→model contract). |
