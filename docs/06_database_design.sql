-- Freight Forwarding, Service Operations, and Double-Entry Finance
-- Consolidated PostgreSQL schema (design reference).
--
-- Generated from the live SQLAlchemy models in
--   backend/app/core/database.py + backend/app/modules/*/models.py
-- The Alembic migrations in backend/alembic/ remain the migration source of
-- truth; this file mirrors the resulting schema for design/reference use.
--
-- 63 tables. The database ships empty after migration. First-run provisioning
-- seeds only the permission catalog, the built-in Platform Administrator role,
-- the current-year document sequences and the default app info/config records.
--
-- NOTE: Organizations and branches are NOT part of this schema. Multi-tenancy
-- was removed (migration b7f1c2a9d4e0_remove_organization_and_branch.py); access
-- is governed entirely by users, roles and permissions. Status-like columns are
-- plain VARCHAR values (no SQL enum types).

CREATE TABLE backup_states (
	table_name VARCHAR(128) NOT NULL, 
	record_id VARCHAR(255) NOT NULL, 
	row_hash VARCHAR(64) NOT NULL, 
	backup_version BIGINT NOT NULL, 
	last_backup_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_backup_states PRIMARY KEY (id), 
	CONSTRAINT uq_backup_states_record UNIQUE (table_name, record_id)
);
CREATE INDEX ix_backup_states_table_name ON backup_states (table_name);

CREATE TABLE business_parties (
	party_code VARCHAR(50) NOT NULL, 
	legal_name VARCHAR(255) NOT NULL, 
	display_name VARCHAR(255), 
	vat_tin VARCHAR(64), 
	contact_person VARCHAR(255), 
	phone VARCHAR(64), 
	email VARCHAR(255), 
	address TEXT, 
	country_code VARCHAR(2), 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_business_parties PRIMARY KEY (id), 
	CONSTRAINT uq_business_parties_party_code UNIQUE (party_code), 
	CONSTRAINT uq_business_parties_vat_tin UNIQUE (vat_tin)
);

CREATE TABLE chart_of_accounts (
	account_code VARCHAR(32) NOT NULL, 
	account_name VARCHAR(255) NOT NULL, 
	account_type VARCHAR(20) NOT NULL, 
	parent_account_id BIGINT, 
	normal_balance VARCHAR(10) NOT NULL, 
	is_postable BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_chart_of_accounts PRIMARY KEY (id), 
	CONSTRAINT uq_coa_code UNIQUE (account_code), 
	CONSTRAINT fk_chart_of_accounts_parent_account_id_chart_of_accounts FOREIGN KEY(parent_account_id) REFERENCES chart_of_accounts (id)
);

CREATE TABLE component_groups (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	display_order INTEGER NOT NULL, 
	show_on_job_workspace BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_component_groups PRIMARY KEY (id), 
	CONSTRAINT uq_component_groups_code UNIQUE (code)
);

CREATE TABLE component_templates (
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	category VARCHAR(64), 
	version INTEGER NOT NULL, 
	is_required BOOLEAN NOT NULL, 
	is_repeatable BOOLEAN NOT NULL, 
	instance_mode VARCHAR(20) NOT NULL, 
	minimum_instances INTEGER, 
	maximum_instances INTEGER, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_component_templates PRIMARY KEY (id), 
	CONSTRAINT uq_component_templates_code_version UNIQUE (code, version)
);

CREATE TABLE container_types (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	container_size VARCHAR(32), 
	container_kind VARCHAR(32), 
	iso_code VARCHAR(16), 
	length_feet NUMERIC(6, 2), 
	width_millimeter NUMERIC(8, 2), 
	height_millimeter NUMERIC(8, 2), 
	max_gross_weight_kg NUMERIC(12, 3), 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_container_types PRIMARY KEY (id), 
	CONSTRAINT uq_container_types_code UNIQUE (code)
);

CREATE TABLE document_sequences (
	document_type VARCHAR(64) NOT NULL, 
	period_year INTEGER NOT NULL, 
	prefix VARCHAR(16) NOT NULL, 
	last_value BIGINT NOT NULL, 
	padding_length INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_document_sequences PRIMARY KEY (id), 
	CONSTRAINT uq_sequences_type_year UNIQUE (document_type, period_year)
);

CREATE TABLE fee_types (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_fee_types PRIMARY KEY (id), 
	CONSTRAINT uq_fee_types_code UNIQUE (code)
);

CREATE TABLE module_records (
	collection VARCHAR(64) NOT NULL, 
	record_no VARCHAR(64), 
	status VARCHAR(32), 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_module_records PRIMARY KEY (id)
);
CREATE INDEX ix_module_records_collection ON module_records (collection);

CREATE TABLE permissions (
	code VARCHAR(128) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	resource VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	description TEXT, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_permissions PRIMARY KEY (id), 
	CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE TABLE places (
	code VARCHAR(50), 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	place_category VARCHAR(64) NOT NULL, 
	parent_place_id BIGINT, 
	address TEXT, 
	country_code VARCHAR(2), 
	latitude NUMERIC(9, 6), 
	longitude NUMERIC(9, 6), 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_places PRIMARY KEY (id), 
	CONSTRAINT uq_places_code UNIQUE (code), 
	CONSTRAINT fk_places_parent_place_id_places FOREIGN KEY(parent_place_id) REFERENCES places (id)
);

CREATE TABLE roles (
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	is_system_role BOOLEAN NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_roles PRIMARY KEY (id), 
	CONSTRAINT uq_roles_code UNIQUE (code)
);

CREATE TABLE service_order_tab_configs (
	code VARCHAR(64) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	name_km VARCHAR(255), 
	description TEXT, 
	icon VARCHAR(64), 
	sort_order INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	allow_multiple_rows BOOLEAN NOT NULL, 
	is_archived BOOLEAN NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_tab_configs PRIMARY KEY (id), 
	CONSTRAINT uq_so_tab_configs_code UNIQUE (code)
);

CREATE TABLE trade_directions (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_trade_directions PRIMARY KEY (id), 
	CONSTRAINT uq_trade_directions_code UNIQUE (code)
);

CREATE TABLE transport_types (
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_transport_types PRIMARY KEY (id), 
	CONSTRAINT uq_transport_types_code UNIQUE (code)
);

CREATE TABLE users (
	user_code VARCHAR(50) NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
	phone VARCHAR(64), 
	status VARCHAR(20) NOT NULL, 
	locale VARCHAR(10) NOT NULL, 
	timezone VARCHAR(64) NOT NULL, 
	last_login_at TIMESTAMP WITH TIME ZONE, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_users PRIMARY KEY (id), 
	CONSTRAINT uq_users_user_code UNIQUE (user_code), 
	CONSTRAINT uq_users_username UNIQUE (username), 
	CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE TABLE accounting_periods (
	period_year INTEGER NOT NULL, 
	period_month INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	closed_by_user_id BIGINT, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_accounting_periods PRIMARY KEY (id), 
	CONSTRAINT uq_periods_year_month UNIQUE (period_year, period_month), 
	CONSTRAINT fk_accounting_periods_closed_by_user_id_users FOREIGN KEY(closed_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_accounting_periods_status ON accounting_periods (status);

CREATE TABLE attachments (
	file_name VARCHAR(512) NOT NULL, 
	storage_key VARCHAR(512) NOT NULL, 
	mime_type VARCHAR(128) NOT NULL, 
	file_size_bytes BIGINT NOT NULL, 
	checksum VARCHAR(128), 
	storage_provider VARCHAR(32) NOT NULL, 
	document_version INTEGER NOT NULL, 
	uploaded_by_user_id BIGINT, 
	uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	is_deleted BOOLEAN NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_attachments PRIMARY KEY (id), 
	CONSTRAINT uq_attachments_storage_key UNIQUE (storage_key), 
	CONSTRAINT fk_attachments_uploaded_by_user_id_users FOREIGN KEY(uploaded_by_user_id) REFERENCES users (id)
);

CREATE TABLE audit_events (
	actor_user_id BIGINT, 
	event_type VARCHAR(64) NOT NULL, 
	entity_type VARCHAR(64) NOT NULL, 
	entity_id BIGINT NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	result VARCHAR(32) NOT NULL, 
	reason TEXT, 
	request_id VARCHAR(64), 
	correlation_id VARCHAR(64), 
	ip_address VARCHAR(64), 
	user_agent TEXT, 
	before_json JSONB, 
	after_json JSONB, 
	metadata_json JSONB, 
	amount NUMERIC(19, 4), 
	occurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_audit_events PRIMARY KEY (id), 
	CONSTRAINT fk_audit_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id)
);
CREATE INDEX ix_audit_events_entity_id ON audit_events (entity_id);
CREATE INDEX ix_audit_events_entity_type ON audit_events (entity_type);
CREATE INDEX ix_audit_events_event_type ON audit_events (event_type);

CREATE TABLE backup_runs (
	trigger VARCHAR(16) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	duration_ms INTEGER, 
	tables_total INTEGER NOT NULL, 
	tables_processed INTEGER NOT NULL, 
	rows_scanned INTEGER NOT NULL, 
	rows_inserted INTEGER NOT NULL, 
	rows_updated INTEGER NOT NULL, 
	rows_skipped INTEGER NOT NULL, 
	rows_failed INTEGER NOT NULL, 
	spreadsheet_id VARCHAR(255), 
	triggered_by_user_id BIGINT, 
	message TEXT, 
	detail JSONB, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_backup_runs PRIMARY KEY (id), 
	CONSTRAINT fk_backup_runs_triggered_by_user_id_users FOREIGN KEY(triggered_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_backup_runs_status ON backup_runs (status);

CREATE TABLE customer_customs_accounts (
	party_id BIGINT NOT NULL, 
	system_name VARCHAR(128) NOT NULL, 
	username VARCHAR(255) NOT NULL, 
	password_secret_reference VARCHAR(255), 
	encrypted_password BYTEA, 
	last_verified_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_customer_customs_accounts PRIMARY KEY (id), 
	CONSTRAINT fk_customer_customs_accounts_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id) ON DELETE CASCADE
);

CREATE TABLE financial_accounts (
	account_id BIGINT NOT NULL, 
	account_name VARCHAR(255) NOT NULL, 
	account_type VARCHAR(32) NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	bank_name VARCHAR(255), 
	account_number_masked VARCHAR(64), 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_financial_accounts PRIMARY KEY (id), 
	CONSTRAINT uq_financial_accounts_account UNIQUE (account_id), 
	CONSTRAINT fk_financial_accounts_account_id_chart_of_accounts FOREIGN KEY(account_id) REFERENCES chart_of_accounts (id)
);

CREATE TABLE party_places (
	party_id BIGINT NOT NULL, 
	place_id BIGINT NOT NULL, 
	relationship_type VARCHAR(50) NOT NULL, 
	is_primary BOOLEAN NOT NULL, 
	CONSTRAINT pk_party_places PRIMARY KEY (party_id, place_id, relationship_type), 
	CONSTRAINT fk_party_places_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id) ON DELETE CASCADE, 
	CONSTRAINT fk_party_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id)
);

CREATE TABLE party_roles (
	party_id BIGINT NOT NULL, 
	role_type VARCHAR(50) NOT NULL, 
	is_primary BOOLEAN NOT NULL, 
	CONSTRAINT pk_party_roles PRIMARY KEY (party_id, role_type), 
	CONSTRAINT fk_party_roles_party_id_business_parties FOREIGN KEY(party_id) REFERENCES business_parties (id) ON DELETE CASCADE
);

CREATE TABLE password_reset_tokens (
	user_id BIGINT NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	code_hash VARCHAR(128) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id), 
	CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE posting_rules (
	document_type VARCHAR(32) NOT NULL, 
	fee_type_id BIGINT, 
	debit_account_id BIGINT NOT NULL, 
	credit_account_id BIGINT NOT NULL, 
	tax_account_id BIGINT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_posting_rules PRIMARY KEY (id), 
	CONSTRAINT fk_posting_rules_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id), 
	CONSTRAINT fk_posting_rules_debit_account_id_chart_of_accounts FOREIGN KEY(debit_account_id) REFERENCES chart_of_accounts (id), 
	CONSTRAINT fk_posting_rules_credit_account_id_chart_of_accounts FOREIGN KEY(credit_account_id) REFERENCES chart_of_accounts (id), 
	CONSTRAINT fk_posting_rules_tax_account_id_chart_of_accounts FOREIGN KEY(tax_account_id) REFERENCES chart_of_accounts (id)
);

CREATE TABLE quotations (
	quotation_no VARCHAR(50) NOT NULL, 
	customer_party_id BIGINT NOT NULL, 
	trade_direction_id BIGINT NOT NULL, 
	current_revision_no INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_quotations PRIMARY KEY (id), 
	CONSTRAINT uq_quotations_no UNIQUE (quotation_no), 
	CONSTRAINT fk_quotations_customer_party_id_business_parties FOREIGN KEY(customer_party_id) REFERENCES business_parties (id), 
	CONSTRAINT fk_quotations_trade_direction_id_trade_directions FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id)
);
CREATE INDEX ix_quotations_status ON quotations (status);

CREATE TABLE role_permissions (
	role_id BIGINT NOT NULL, 
	permission_id BIGINT NOT NULL, 
	CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
	CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE TABLE service_order_column_configs (
	tab_id BIGINT NOT NULL, 
	field_key VARCHAR(64) NOT NULL, 
	label VARCHAR(255) NOT NULL, 
	label_km VARCHAR(255), 
	field_type VARCHAR(32) NOT NULL, 
	reference_type VARCHAR(32), 
	is_required BOOLEAN NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	is_archived BOOLEAN NOT NULL, 
	show_in_summary BOOLEAN NOT NULL, 
	width VARCHAR(16), 
	sort_order INTEGER NOT NULL, 
	default_value VARCHAR(255), 
	placeholder VARCHAR(255), 
	validation_rules JSONB NOT NULL, 
	options JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_column_configs PRIMARY KEY (id), 
	CONSTRAINT uq_so_column_configs_tab_key UNIQUE (tab_id, field_key), 
	CONSTRAINT fk_service_order_column_configs_tab_id_service_order_ta_f143 FOREIGN KEY(tab_id) REFERENCES service_order_tab_configs (id) ON DELETE CASCADE
);
CREATE INDEX ix_service_order_column_configs_tab_id ON service_order_column_configs (tab_id);

CREATE TABLE template_attributes (
	template_id BIGINT NOT NULL, 
	code VARCHAR(64) NOT NULL, 
	label VARCHAR(255) NOT NULL, 
	data_type VARCHAR(32) NOT NULL, 
	input_type VARCHAR(32), 
	is_required BOOLEAN NOT NULL, 
	is_repeatable BOOLEAN NOT NULL, 
	display_order INTEGER NOT NULL, 
	validation_rules JSONB NOT NULL, 
	reference_type VARCHAR(64), 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_template_attributes PRIMARY KEY (id), 
	CONSTRAINT uq_template_attributes_template_code UNIQUE (template_id, code), 
	CONSTRAINT fk_template_attributes_template_id_component_templates FOREIGN KEY(template_id) REFERENCES component_templates (id) ON DELETE CASCADE
);

CREATE TABLE trade_direction_components (
	trade_direction_id BIGINT NOT NULL, 
	component_group_id BIGINT NOT NULL, 
	component_template_id BIGINT NOT NULL, 
	display_order INTEGER NOT NULL, 
	is_required BOOLEAN NOT NULL, 
	is_repeatable BOOLEAN NOT NULL, 
	instance_mode_override VARCHAR(20) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_trade_direction_components PRIMARY KEY (id), 
	CONSTRAINT uq_tdc_direction_template UNIQUE (trade_direction_id, component_template_id), 
	CONSTRAINT fk_trade_direction_components_trade_direction_id_trade__ae96 FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id), 
	CONSTRAINT fk_trade_direction_components_component_group_id_compon_9598 FOREIGN KEY(component_group_id) REFERENCES component_groups (id), 
	CONSTRAINT fk_trade_direction_components_component_template_id_com_18ca FOREIGN KEY(component_template_id) REFERENCES component_templates (id)
);

CREATE TABLE transport_assets (
	asset_code VARCHAR(50) NOT NULL, 
	transport_type_id BIGINT NOT NULL, 
	identity VARCHAR(128) NOT NULL, 
	identity_type VARCHAR(64) NOT NULL, 
	registration_country_code VARCHAR(2), 
	owner_party_id BIGINT, 
	operator_party_id BIGINT, 
	description TEXT, 
	status VARCHAR(20) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_transport_assets PRIMARY KEY (id), 
	CONSTRAINT uq_transport_assets_type_identity UNIQUE (transport_type_id, identity), 
	CONSTRAINT uq_transport_assets_asset_code UNIQUE (asset_code), 
	CONSTRAINT fk_transport_assets_transport_type_id_transport_types FOREIGN KEY(transport_type_id) REFERENCES transport_types (id), 
	CONSTRAINT fk_transport_assets_owner_party_id_business_parties FOREIGN KEY(owner_party_id) REFERENCES business_parties (id), 
	CONSTRAINT fk_transport_assets_operator_party_id_business_parties FOREIGN KEY(operator_party_id) REFERENCES business_parties (id)
);

CREATE TABLE user_credentials (
	user_id BIGINT NOT NULL, 
	password_hash TEXT NOT NULL, 
	password_algorithm VARCHAR(32) NOT NULL, 
	password_changed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	failed_attempt_count INTEGER NOT NULL, 
	locked_until TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_user_credentials PRIMARY KEY (user_id), 
	CONSTRAINT fk_user_credentials_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE user_role_assignments (
	user_id BIGINT NOT NULL, 
	role_id BIGINT NOT NULL, 
	assigned_by_user_id BIGINT, 
	starts_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_user_role_assignments PRIMARY KEY (id), 
	CONSTRAINT fk_user_role_assignments_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT fk_user_role_assignments_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id), 
	CONSTRAINT fk_user_role_assignments_assigned_by_user_id_users FOREIGN KEY(assigned_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_user_role_assignments_user_id ON user_role_assignments (user_id);

CREATE TABLE user_sessions (
	user_id BIGINT NOT NULL, 
	refresh_token_hash VARCHAR(128) NOT NULL, 
	device_name VARCHAR(255), 
	ip_address VARCHAR(64), 
	user_agent TEXT, 
	last_used_at TIMESTAMP WITH TIME ZONE, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_user_sessions PRIMARY KEY (id), 
	CONSTRAINT fk_user_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT uq_user_sessions_refresh_token_hash UNIQUE (refresh_token_hash)
);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

CREATE TABLE attachment_links (
	attachment_id BIGINT NOT NULL, 
	entity_type VARCHAR(64) NOT NULL, 
	entity_id BIGINT NOT NULL, 
	attachment_role VARCHAR(64) NOT NULL, 
	is_primary BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_attachment_links PRIMARY KEY (id), 
	CONSTRAINT uq_attachment_links_target UNIQUE (attachment_id, entity_type, entity_id, attachment_role), 
	CONSTRAINT fk_attachment_links_attachment_id_attachments FOREIGN KEY(attachment_id) REFERENCES attachments (id) ON DELETE CASCADE
);
CREATE INDEX ix_attachment_links_attachment_id ON attachment_links (attachment_id);

CREATE TABLE backup_logs (
	run_id BIGINT, 
	level VARCHAR(16) NOT NULL, 
	table_name VARCHAR(128), 
	message TEXT NOT NULL, 
	detail JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_backup_logs PRIMARY KEY (id), 
	CONSTRAINT fk_backup_logs_run_id_backup_runs FOREIGN KEY(run_id) REFERENCES backup_runs (id) ON DELETE CASCADE
);
CREATE INDEX ix_backup_logs_run_id ON backup_logs (run_id);

CREATE TABLE backup_records (
	run_id BIGINT, 
	table_name VARCHAR(128) NOT NULL, 
	record_id VARCHAR(255) NOT NULL, 
	backup_version BIGINT NOT NULL, 
	backup_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	change_kind VARCHAR(16) NOT NULL, 
	row_hash VARCHAR(64) NOT NULL, 
	data JSONB NOT NULL, 
	synced BOOLEAN NOT NULL, 
	synced_at TIMESTAMP WITH TIME ZONE, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_backup_records PRIMARY KEY (id), 
	CONSTRAINT uq_backup_records_version UNIQUE (table_name, record_id, row_hash), 
	CONSTRAINT fk_backup_records_run_id_backup_runs FOREIGN KEY(run_id) REFERENCES backup_runs (id) ON DELETE SET NULL
);
CREATE INDEX ix_backup_records_synced ON backup_records (synced);
CREATE INDEX ix_backup_records_table_name ON backup_records (table_name);
CREATE INDEX ix_backup_records_table_record ON backup_records (table_name, record_id);

CREATE TABLE quotation_revisions (
	quotation_id BIGINT NOT NULL, 
	revision_no INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	quotation_date DATE NOT NULL, 
	valid_until DATE, 
	currency_code VARCHAR(3) NOT NULL, 
	description TEXT, 
	notes TEXT, 
	subtotal_amount NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	total_amount NUMERIC(19, 4) NOT NULL, 
	created_by_user_id BIGINT, 
	sent_at TIMESTAMP WITH TIME ZONE, 
	accepted_at TIMESTAMP WITH TIME ZONE, 
	rejected_at TIMESTAMP WITH TIME ZONE, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_quotation_revisions PRIMARY KEY (id), 
	CONSTRAINT uq_quotation_revisions_no UNIQUE (quotation_id, revision_no), 
	CONSTRAINT fk_quotation_revisions_quotation_id_quotations FOREIGN KEY(quotation_id) REFERENCES quotations (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quotation_revisions_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_quotation_revisions_quotation_id ON quotation_revisions (quotation_id);
CREATE INDEX ix_quotation_revisions_status ON quotation_revisions (status);

CREATE TABLE quotation_conversions (
	quotation_revision_id BIGINT NOT NULL, 
	service_order_id BIGINT NOT NULL, 
	converted_by_user_id BIGINT, 
	converted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	notes TEXT, 
	idempotency_key VARCHAR(128), 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_quotation_conversions PRIMARY KEY (id), 
	CONSTRAINT uq_quotation_conversions_quotation_revision_id UNIQUE (quotation_revision_id), 
	CONSTRAINT fk_quotation_conversions_quotation_revision_id_quotatio_6c51 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id), 
	CONSTRAINT uq_quotation_conversions_service_order_id UNIQUE (service_order_id), 
	CONSTRAINT fk_quotation_conversions_converted_by_user_id_users FOREIGN KEY(converted_by_user_id) REFERENCES users (id), 
	CONSTRAINT uq_quotation_conversions_idempotency_key UNIQUE (idempotency_key)
);

CREATE TABLE quotation_revision_containers (
	quotation_revision_id BIGINT NOT NULL, 
	container_type_id BIGINT NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	gross_weight_kg NUMERIC(12, 3), 
	description TEXT, 
	remarks TEXT, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_quotation_revision_containers PRIMARY KEY (id), 
	CONSTRAINT fk_quotation_revision_containers_quotation_revision_id__e5b2 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quotation_revision_containers_container_type_id_cont_3afe FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_quotation_revision_containers_quotation_revision_id ON quotation_revision_containers (quotation_revision_id);

CREATE TABLE quotation_revision_places (
	quotation_revision_id BIGINT NOT NULL, 
	place_id BIGINT, 
	place_role VARCHAR(32) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	free_text TEXT, 
	notes TEXT, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_quotation_revision_places PRIMARY KEY (id), 
	CONSTRAINT fk_quotation_revision_places_quotation_revision_id_quot_f0f2 FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quotation_revision_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id)
);
CREATE INDEX ix_quotation_revision_places_quotation_revision_id ON quotation_revision_places (quotation_revision_id);

CREATE TABLE service_orders (
	service_order_no VARCHAR(50) NOT NULL, 
	quotation_revision_id BIGINT, 
	customer_party_id BIGINT NOT NULL, 
	trade_direction_id BIGINT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	description TEXT, 
	created_by_user_id BIGINT, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_orders PRIMARY KEY (id), 
	CONSTRAINT uq_service_orders_no UNIQUE (service_order_no), 
	CONSTRAINT fk_service_orders_quotation_revision_id_quotation_revisions FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id), 
	CONSTRAINT fk_service_orders_customer_party_id_business_parties FOREIGN KEY(customer_party_id) REFERENCES business_parties (id), 
	CONSTRAINT fk_service_orders_trade_direction_id_trade_directions FOREIGN KEY(trade_direction_id) REFERENCES trade_directions (id), 
	CONSTRAINT fk_service_orders_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_orders_status ON service_orders (status);

CREATE TABLE financial_documents (
	document_no VARCHAR(50) NOT NULL, 
	document_type VARCHAR(32) NOT NULL, 
	document_date DATE NOT NULL, 
	posting_date DATE, 
	status VARCHAR(20) NOT NULL, 
	party_id BIGINT, 
	service_order_id BIGINT, 
	currency_code VARCHAR(3) NOT NULL, 
	exchange_rate NUMERIC(19, 8) NOT NULL, 
	description TEXT, 
	reference_number VARCHAR(128), 
	due_date DATE, 
	payment_method_code VARCHAR(64), 
	financial_account_id BIGINT, 
	value_date DATE, 
	subtotal_amount NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	total_amount NUMERIC(19, 4) NOT NULL, 
	paid_amount NUMERIC(19, 4) NOT NULL, 
	created_by_user_id BIGINT, 
	posted_by_user_id BIGINT, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	reversed_document_id BIGINT, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
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

CREATE TABLE quotation_revision_lines (
	quotation_revision_id BIGINT NOT NULL, 
	line_no INTEGER NOT NULL, 
	fee_type_id BIGINT, 
	container_requirement_id BIGINT, 
	service_description TEXT NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	unit_code VARCHAR(32), 
	unit_price NUMERIC(19, 4) NOT NULL, 
	discount_rate NUMERIC(7, 4) NOT NULL, 
	tax_rate NUMERIC(7, 4) NOT NULL, 
	line_subtotal NUMERIC(19, 4) NOT NULL, 
	line_discount NUMERIC(19, 4) NOT NULL, 
	line_tax NUMERIC(19, 4) NOT NULL, 
	line_total NUMERIC(19, 4) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_quotation_revision_lines PRIMARY KEY (id), 
	CONSTRAINT uq_quotation_revision_lines_no UNIQUE (quotation_revision_id, line_no), 
	CONSTRAINT fk_quotation_revision_lines_quotation_revision_id_quota_6e8c FOREIGN KEY(quotation_revision_id) REFERENCES quotation_revisions (id) ON DELETE CASCADE, 
	CONSTRAINT fk_quotation_revision_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id), 
	CONSTRAINT fk_quotation_revision_lines_container_requirement_id_qu_27b0 FOREIGN KEY(container_requirement_id) REFERENCES quotation_revision_containers (id)
);
CREATE INDEX ix_quotation_revision_lines_quotation_revision_id ON quotation_revision_lines (quotation_revision_id);

CREATE TABLE service_order_charges (
	service_order_id BIGINT NOT NULL, 
	charge_no VARCHAR(50) NOT NULL, 
	document_type VARCHAR(32) NOT NULL, 
	document_date DATE NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	subtotal_amount NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	total_amount NUMERIC(19, 4) NOT NULL, 
	remark TEXT, 
	created_by_user_id BIGINT, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_charges PRIMARY KEY (id), 
	CONSTRAINT uq_service_order_charges_no UNIQUE (charge_no), 
	CONSTRAINT fk_service_order_charges_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_charges_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_order_charges_service_order_id ON service_order_charges (service_order_id);
CREATE INDEX ix_service_order_charges_status ON service_order_charges (status);

CREATE TABLE service_order_components (
	service_order_id BIGINT NOT NULL, 
	trade_direction_component_id BIGINT, 
	component_group_id BIGINT, 
	component_template_id BIGINT NOT NULL, 
	template_code VARCHAR(64) NOT NULL, 
	template_version INTEGER NOT NULL, 
	component_status VARCHAR(20) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	is_required BOOLEAN NOT NULL, 
	is_repeatable BOOLEAN NOT NULL, 
	instance_mode VARCHAR(20) NOT NULL, 
	occurred_at TIMESTAMP WITH TIME ZONE, 
	created_by_user_id BIGINT, 
	completed_by_user_id BIGINT, 
	completed_at TIMESTAMP WITH TIME ZONE, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_components PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_components_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_components_trade_direction_component_i_c1d3 FOREIGN KEY(trade_direction_component_id) REFERENCES trade_direction_components (id), 
	CONSTRAINT fk_service_order_components_component_group_id_component_groups FOREIGN KEY(component_group_id) REFERENCES component_groups (id), 
	CONSTRAINT fk_service_order_components_component_template_id_compo_71d7 FOREIGN KEY(component_template_id) REFERENCES component_templates (id), 
	CONSTRAINT fk_service_order_components_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	CONSTRAINT fk_service_order_components_completed_by_user_id_users FOREIGN KEY(completed_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_order_components_component_status ON service_order_components (component_status);
CREATE INDEX ix_service_order_components_service_order_id ON service_order_components (service_order_id);

CREATE TABLE service_order_container_requirements (
	service_order_id BIGINT NOT NULL, 
	source_quotation_container_id BIGINT, 
	container_type_id BIGINT NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	gross_weight_kg NUMERIC(12, 3), 
	description TEXT, 
	remarks TEXT, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_service_order_container_requirements PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_container_requirements_service_order_i_2728 FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_container_requirements_source_quotatio_1946 FOREIGN KEY(source_quotation_container_id) REFERENCES quotation_revision_containers (id), 
	CONSTRAINT fk_service_order_container_requirements_container_type__3695 FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_service_order_container_requirements_service_order_id ON service_order_container_requirements (service_order_id);

CREATE TABLE service_order_milestones (
	service_order_id BIGINT NOT NULL, 
	milestone_code VARCHAR(64) NOT NULL, 
	milestone_name VARCHAR(255) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	planned_at TIMESTAMP WITH TIME ZONE, 
	actual_at TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(20) NOT NULL, 
	notes TEXT, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_milestones PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_milestones_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE
);
CREATE INDEX ix_service_order_milestones_service_order_id ON service_order_milestones (service_order_id);

CREATE TABLE service_order_movements (
	service_order_id BIGINT NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	transport_type_id BIGINT, 
	transport_asset_id BIGINT, 
	origin_place_id BIGINT, 
	destination_place_id BIGINT, 
	planned_departure TIMESTAMP WITH TIME ZONE, 
	actual_departure TIMESTAMP WITH TIME ZONE, 
	planned_arrival TIMESTAMP WITH TIME ZONE, 
	actual_arrival TIMESTAMP WITH TIME ZONE, 
	status VARCHAR(32) NOT NULL, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_movements PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_movements_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_movements_transport_type_id_transport_types FOREIGN KEY(transport_type_id) REFERENCES transport_types (id), 
	CONSTRAINT fk_service_order_movements_transport_asset_id_transport_assets FOREIGN KEY(transport_asset_id) REFERENCES transport_assets (id), 
	CONSTRAINT fk_service_order_movements_origin_place_id_places FOREIGN KEY(origin_place_id) REFERENCES places (id), 
	CONSTRAINT fk_service_order_movements_destination_place_id_places FOREIGN KEY(destination_place_id) REFERENCES places (id)
);
CREATE INDEX ix_service_order_movements_service_order_id ON service_order_movements (service_order_id);

CREATE TABLE service_order_places (
	service_order_id BIGINT NOT NULL, 
	place_id BIGINT, 
	place_role VARCHAR(32) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	free_text TEXT, 
	is_actual BOOLEAN NOT NULL, 
	notes TEXT, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_service_order_places PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_places_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_places_place_id_places FOREIGN KEY(place_id) REFERENCES places (id)
);
CREATE INDEX ix_service_order_places_service_order_id ON service_order_places (service_order_id);

CREATE TABLE service_order_pricing (
	service_order_id BIGINT NOT NULL, 
	subtotal_amount NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	total_amount NUMERIC(19, 4) NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_pricing PRIMARY KEY (id), 
	CONSTRAINT uq_service_order_pricing_service_order_id UNIQUE (service_order_id), 
	CONSTRAINT fk_service_order_pricing_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE
);

CREATE TABLE service_order_tab_rows (
	service_order_id BIGINT NOT NULL, 
	tab_config_id BIGINT NOT NULL, 
	tab_code VARCHAR(64) NOT NULL, 
	row_no INTEGER NOT NULL, 
	is_archived BOOLEAN NOT NULL, 
	values JSONB NOT NULL, 
	created_by_user_id BIGINT, 
	updated_by_user_id BIGINT, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_tab_rows PRIMARY KEY (id), 
	CONSTRAINT fk_service_order_tab_rows_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_tab_rows_tab_config_id_service_order_t_54e2 FOREIGN KEY(tab_config_id) REFERENCES service_order_tab_configs (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_tab_rows_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	CONSTRAINT fk_service_order_tab_rows_updated_by_user_id_users FOREIGN KEY(updated_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_service_order_tab_rows_service_order_id ON service_order_tab_rows (service_order_id);
CREATE INDEX ix_service_order_tab_rows_tab_config_id ON service_order_tab_rows (tab_config_id);

CREATE TABLE financial_document_allocations (
	payment_document_id BIGINT NOT NULL, 
	target_document_id BIGINT NOT NULL, 
	allocated_amount NUMERIC(19, 4) NOT NULL, 
	allocated_currency_code VARCHAR(3) NOT NULL, 
	exchange_rate NUMERIC(19, 8) NOT NULL, 
	allocated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	created_by_user_id BIGINT, 
	idempotency_key VARCHAR(128), 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_financial_document_allocations PRIMARY KEY (id), 
	CONSTRAINT fk_financial_document_allocations_payment_document_id_f_f494 FOREIGN KEY(payment_document_id) REFERENCES financial_documents (id), 
	CONSTRAINT fk_financial_document_allocations_target_document_id_fi_faa8 FOREIGN KEY(target_document_id) REFERENCES financial_documents (id), 
	CONSTRAINT fk_financial_document_allocations_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	CONSTRAINT uq_financial_document_allocations_idempotency_key UNIQUE (idempotency_key)
);
CREATE INDEX ix_financial_document_allocations_payment_document_id ON financial_document_allocations (payment_document_id);
CREATE INDEX ix_financial_document_allocations_target_document_id ON financial_document_allocations (target_document_id);

CREATE TABLE financial_document_sources (
	financial_document_id BIGINT NOT NULL, 
	source_type VARCHAR(64) NOT NULL, 
	source_id BIGINT NOT NULL, 
	relationship_type VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_financial_document_sources PRIMARY KEY (id), 
	CONSTRAINT uq_fin_doc_sources UNIQUE (financial_document_id, source_type, source_id, relationship_type), 
	CONSTRAINT fk_financial_document_sources_financial_document_id_fin_5efa FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id) ON DELETE CASCADE
);
CREATE INDEX ix_financial_document_sources_financial_document_id ON financial_document_sources (financial_document_id);

CREATE TABLE journal_entries (
	entry_no VARCHAR(50) NOT NULL, 
	entry_type VARCHAR(64) NOT NULL, 
	entry_date DATE NOT NULL, 
	posting_date DATE NOT NULL, 
	accounting_period_id BIGINT, 
	status VARCHAR(20) NOT NULL, 
	description TEXT, 
	source_document_id BIGINT, 
	reversal_of_journal_entry_id BIGINT, 
	created_by_user_id BIGINT, 
	posted_by_user_id BIGINT, 
	posted_at TIMESTAMP WITH TIME ZONE, 
	debit_total NUMERIC(19, 4) NOT NULL, 
	credit_total NUMERIC(19, 4) NOT NULL, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_journal_entries PRIMARY KEY (id), 
	CONSTRAINT uq_journal_entries_no UNIQUE (entry_no), 
	CONSTRAINT fk_journal_entries_accounting_period_id_accounting_periods FOREIGN KEY(accounting_period_id) REFERENCES accounting_periods (id), 
	CONSTRAINT fk_journal_entries_source_document_id_financial_documents FOREIGN KEY(source_document_id) REFERENCES financial_documents (id), 
	CONSTRAINT fk_journal_entries_reversal_of_journal_entry_id_journal_entries FOREIGN KEY(reversal_of_journal_entry_id) REFERENCES journal_entries (id), 
	CONSTRAINT fk_journal_entries_created_by_user_id_users FOREIGN KEY(created_by_user_id) REFERENCES users (id), 
	CONSTRAINT fk_journal_entries_posted_by_user_id_users FOREIGN KEY(posted_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_journal_entries_status ON journal_entries (status);

CREATE TABLE service_component_values (
	component_id BIGINT NOT NULL, 
	template_attribute_id BIGINT NOT NULL, 
	value_text TEXT, 
	value_number NUMERIC(19, 6), 
	value_date DATE, 
	value_datetime TIMESTAMP WITH TIME ZONE, 
	value_boolean BOOLEAN, 
	value_reference_type VARCHAR(64), 
	value_reference_id BIGINT, 
	value_json JSONB, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_component_values PRIMARY KEY (id), 
	CONSTRAINT uq_service_component_values_attr UNIQUE (component_id, template_attribute_id), 
	CONSTRAINT fk_service_component_values_component_id_service_order__9cda FOREIGN KEY(component_id) REFERENCES service_order_components (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_component_values_template_attribute_id_templ_e7b6 FOREIGN KEY(template_attribute_id) REFERENCES template_attributes (id)
);
CREATE INDEX ix_service_component_values_component_id ON service_component_values (component_id);

CREATE TABLE service_order_containers (
	service_order_id BIGINT NOT NULL, 
	container_requirement_id BIGINT, 
	container_type_id BIGINT NOT NULL, 
	container_number VARCHAR(32) NOT NULL, 
	seal_serial VARCHAR(64), 
	status VARCHAR(32) NOT NULL, 
	net_weight_kg NUMERIC(12, 3), 
	gross_weight_kg NUMERIC(12, 3), 
	pickup_date DATE, 
	return_date DATE, 
	data JSONB NOT NULL, 
	id BIGSERIAL NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_service_order_containers PRIMARY KEY (id), 
	CONSTRAINT uq_service_order_containers_number UNIQUE (container_number), 
	CONSTRAINT fk_service_order_containers_service_order_id_service_orders FOREIGN KEY(service_order_id) REFERENCES service_orders (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_containers_container_requirement_id_se_2d3c FOREIGN KEY(container_requirement_id) REFERENCES service_order_container_requirements (id), 
	CONSTRAINT fk_service_order_containers_container_type_id_container_types FOREIGN KEY(container_type_id) REFERENCES container_types (id)
);
CREATE INDEX ix_service_order_containers_service_order_id ON service_order_containers (service_order_id);

CREATE TABLE service_order_pricing_lines (
	service_order_pricing_id BIGINT NOT NULL, 
	line_no INTEGER NOT NULL, 
	source_quotation_line_id BIGINT, 
	fee_type_id BIGINT, 
	description TEXT NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	unit_code VARCHAR(32), 
	unit_price NUMERIC(19, 4) NOT NULL, 
	discount_rate NUMERIC(7, 4) NOT NULL, 
	tax_rate NUMERIC(7, 4) NOT NULL, 
	line_total NUMERIC(19, 4) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_service_order_pricing_lines PRIMARY KEY (id), 
	CONSTRAINT uq_so_pricing_lines_no UNIQUE (service_order_pricing_id, line_no), 
	CONSTRAINT fk_service_order_pricing_lines_service_order_pricing_id_b7cf FOREIGN KEY(service_order_pricing_id) REFERENCES service_order_pricing (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_pricing_lines_source_quotation_line_id_9a37 FOREIGN KEY(source_quotation_line_id) REFERENCES quotation_revision_lines (id), 
	CONSTRAINT fk_service_order_pricing_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id)
);
CREATE INDEX ix_service_order_pricing_lines_service_order_pricing_id ON service_order_pricing_lines (service_order_pricing_id);

CREATE TABLE financial_document_lines (
	financial_document_id BIGINT NOT NULL, 
	line_no INTEGER NOT NULL, 
	description TEXT NOT NULL, 
	fee_type_id BIGINT, 
	quantity NUMERIC(12, 3) NOT NULL, 
	unit_code VARCHAR(32), 
	unit_price NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_rate NUMERIC(7, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	line_amount NUMERIC(19, 4) NOT NULL, 
	service_order_id BIGINT, 
	service_order_container_id BIGINT, 
	account_id BIGINT, 
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

CREATE TABLE financial_document_postings (
	financial_document_id BIGINT NOT NULL, 
	journal_entry_id BIGINT NOT NULL, 
	posting_role VARCHAR(32) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_financial_document_postings PRIMARY KEY (id), 
	CONSTRAINT uq_fin_doc_postings UNIQUE (financial_document_id, journal_entry_id), 
	CONSTRAINT fk_financial_document_postings_financial_document_id_fi_9505 FOREIGN KEY(financial_document_id) REFERENCES financial_documents (id), 
	CONSTRAINT fk_financial_document_postings_journal_entry_id_journal_entries FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id)
);

CREATE TABLE journal_entry_lines (
	journal_entry_id BIGINT NOT NULL, 
	line_no INTEGER NOT NULL, 
	account_id BIGINT NOT NULL, 
	party_id BIGINT, 
	service_order_id BIGINT, 
	financial_document_id BIGINT, 
	description TEXT, 
	debit_amount NUMERIC(19, 4) NOT NULL, 
	credit_amount NUMERIC(19, 4) NOT NULL, 
	currency_code VARCHAR(3) NOT NULL, 
	exchange_rate NUMERIC(19, 8) NOT NULL, 
	base_debit_amount NUMERIC(19, 4) NOT NULL, 
	base_credit_amount NUMERIC(19, 4) NOT NULL, 
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

CREATE TABLE service_order_charge_lines (
	service_order_charge_id BIGINT NOT NULL, 
	line_no INTEGER NOT NULL, 
	fee_type_id BIGINT, 
	service_order_container_id BIGINT, 
	description TEXT NOT NULL, 
	quantity NUMERIC(12, 3) NOT NULL, 
	unit_code VARCHAR(32), 
	unit_price NUMERIC(19, 4) NOT NULL, 
	discount_amount NUMERIC(19, 4) NOT NULL, 
	tax_rate NUMERIC(7, 4) NOT NULL, 
	tax_amount NUMERIC(19, 4) NOT NULL, 
	line_amount NUMERIC(19, 4) NOT NULL, 
	id BIGSERIAL NOT NULL, 
	CONSTRAINT pk_service_order_charge_lines PRIMARY KEY (id), 
	CONSTRAINT uq_service_order_charge_lines_no UNIQUE (service_order_charge_id, line_no), 
	CONSTRAINT fk_service_order_charge_lines_service_order_charge_id_s_b0ca FOREIGN KEY(service_order_charge_id) REFERENCES service_order_charges (id) ON DELETE CASCADE, 
	CONSTRAINT fk_service_order_charge_lines_fee_type_id_fee_types FOREIGN KEY(fee_type_id) REFERENCES fee_types (id), 
	CONSTRAINT fk_service_order_charge_lines_service_order_container_i_e64b FOREIGN KEY(service_order_container_id) REFERENCES service_order_containers (id)
);
CREATE INDEX ix_service_order_charge_lines_service_order_charge_id ON service_order_charge_lines (service_order_charge_id);

-- Archive / recycle-bin additions (migration e3f4a5b6c7d8).
-- Supported source tables also carry nullable deleted_at and
-- deleted_by_user_id -> users.id columns, each indexed.
CREATE TABLE archive_records (
    id BIGSERIAL NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id BIGINT NOT NULL,
    record_reference VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    deleted_by_user_id BIGINT,
    original_owner_user_id BIGINT,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    restored_by_user_id BIGINT,
    restored_at TIMESTAMP WITH TIME ZONE,
    hard_deleted_by_user_id BIGINT,
    hard_deleted_at TIMESTAMP WITH TIME ZONE,
    snapshot_json JSON NOT NULL,
    CONSTRAINT pk_archive_records PRIMARY KEY (id),
    CONSTRAINT uq_archive_records_entity UNIQUE (entity_type, entity_id),
    CONSTRAINT fk_archive_records_deleted_by_user_id_users FOREIGN KEY(deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_original_owner_user_id_users FOREIGN KEY(original_owner_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_restored_by_user_id_users FOREIGN KEY(restored_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_archive_records_hard_deleted_by_user_id_users FOREIGN KEY(hard_deleted_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_archive_records_entity_type ON archive_records (entity_type);
CREATE INDEX ix_archive_records_entity_id ON archive_records (entity_id);
CREATE INDEX ix_archive_records_status ON archive_records (status);
CREATE INDEX ix_archive_records_deleted_by_user_id ON archive_records (deleted_by_user_id);
CREATE INDEX ix_archive_records_deleted_at ON archive_records (deleted_at);

