"""Human-readable descriptions for every table and column in the schema.

This module is the single source of truth for the prose that
``scripts/generate_schema_docs.py`` renders into
``docs/06_database_design.sql``. Keeping the text here — instead of
hand-editing the generated SQL — means the documentation can be regenerated
after any model change with::

    uv run python scripts/generate_schema_docs.py

Resolution order for a column description (first match wins):

1. ``COLUMN_DESCRIPTIONS[table][column]`` — table-specific text.
2. ``COMMON_COLUMNS[column]`` — text that is genuinely identical everywhere.
3. ``describe_column()`` suffix rules — mechanical columns such as ``*_by_user_id``.
4. The SQLAlchemy comment on the column, if any.
5. Empty, which the generator reports so the gap is visible.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Module -> human-readable section title
# --------------------------------------------------------------------------

MODULE_TITLES: dict[str, str] = {
    "app.modules.archive.models": "Archive & Retention",
    "app.modules.audit.models": "Audit Trail",
    "app.modules.auth.models": "Authentication & Access Control",
    "app.modules.backup.models": "Google Sheets Backup",
    "app.modules.finance.models": "Double-Entry Finance",
    "app.modules.master_data.models": "Master Data",
    "app.modules.operations.models": "Service Operations",
    "app.modules.quotations.models": "Quotations",
    "app.modules.settings.models": "Application Settings",
}

# --------------------------------------------------------------------------
# Table descriptions
# --------------------------------------------------------------------------

TABLE_DESCRIPTIONS: dict[str, str] = {
    # -- master data ------------------------------------------------------
    "place_roles": (
        "Administrator-managed vocabulary of roles a route stop can play (Pickup, Origin,\n"
        "Customs Clearance, ...). Configuration data, not a physical location: the same\n"
        "place can be a loading stop on one document and a destination on another. The\n"
        "initial rows are seeded as data, and a role in use is deactivated rather than\n"
        "deleted so historical routes keep their reference."
    ),
    "party_roles": (
        "Administrator-managed vocabulary of roles a business party can hold (Customer,\n"
        "Supplier, Company, or any role the organisation adds). Replaces the hardcoded\n"
        "dropdown; a role still assigned to a party is deactivated instead of deleted."
    ),
    "business_party_roles": (
        "Many-to-many assignment of party roles to business parties. The unique pair\n"
        "prevents the same role being assigned twice, and the role FK is RESTRICT so an\n"
        "assigned role cannot be hard-deleted."
    ),
    "currencies": (
        "Currency master data. Monetary columns keep their ISO code string for backward\n"
        "compatibility, but every configured code resolves to a row here, so a typo can no\n"
        "longer create a currency nobody can report on. decimal_places is the currency's own\n"
        "precision, used to round every converted (base-currency) amount."
    ),
    "currency_rates": (
        "Approved currency conversion rates, versioned by effective date. A document in\n"
        "another currency resolves its rate from the newest APPROVED row for the pair (in\n"
        "either direction) and copies it onto the document, so a later rate change can never\n"
        "move an amount that was already posted."
    ),
    "trade_directions": (
        "Direction of trade (import, export, domestic). Scopes service-order workflows and\n"
        "decides which component tabs are shown."
    ),
    "container_types": (
        "Shipping container type and its ISO 6346 physical dimensions, referenced by\n"
        "quotation container requirements and by actual containers on a service order."
    ),
    "transport_types": "Mode of transport (sea, air, road, rail, multimodal).",
    "fee_types": (
        "Catalogue of chargeable services (freight, handling, THC, duty, delivery) used to\n"
        "classify every priced line in quotations, service-order pricing and charges."
    ),
    "business_parties": (
        "Counterparty master record for any legal entity the platform trades with —\n"
        "customer, supplier, carrier or agent. One row may carry several roles."
    ),
    "transport_assets": (
        "Physical transport asset (truck, vessel, aircraft) owned or operated by a business\n"
        "party and assigned to a movement leg."
    ),
    "customer_customs_accounts": (
        "Credentials for a customer's portal on an external customs/declaration system,\n"
        "stored so declarations can be filed without re-entering logins."
    ),
    "component_attributes": (
        "Reusable dynamic-form attribute (field) in the global catalog. Attributes are\n"
        "defined once and then referenced by one or more component groups, so a field such\n"
        "as \"Container No.\" can be reused everywhere."
    ),
    "component_groups": (
        "A reusable group of attributes. render_mode is the legacy default; the effective\n"
        "layout (form_only, table_only or form_and_table) is configured per tab assignment on\n"
        "component_tab_groups, so the same group can render differently in different tabs."
    ),
    "component_group_attributes": (
        "Membership of a reusable attribute in a component group, with per-group overrides of\n"
        "the required flag and width."
    ),
    "component_tabs": (
        "A Service Order tab composed of component groups, optionally shown for one trade\n"
        "direction only."
    ),
    "configuration_versions": (
        "A published snapshot of the dynamic Service Order configuration. Tabs, groups and\n"
        "attributes are edited in place, so without a snapshot a historical Service Order\n"
        "could no longer be rendered the way it was filled in. Exactly one version may be\n"
        "PUBLISHED at a time; RETIRED keeps a snapshot readable after it stops being current.\n"
        "The snapshot is data only - nothing in it is executed."
    ),
    "app_settings": (
        "One keyed application-configuration document per setting group. Settings used to\n"
        "live as a single JSON blob in module_records; a keyed table lets one group be read,\n"
        "validated and written without rewriting the whole document, and lets each row carry\n"
        "its own description and last writer. Payload shape and validation stay in code."
    ),
    "component_tab_groups": (
        "Membership of a component group in a component tab, including the display layout for\n"
        "that assignment (mode, cardinality, form columns, title/read-only/collapse flags)."
    ),
    "module_records": (
        "Generic record store backing metadata-driven frontend collections. Used for\n"
        "secondary/legacy collections that the frontend renders from its module schema (for\n"
        "example companies, shipments, customs and documents) without a dedicated relational\n"
        "table. The full configured payload lives in data; the key columns support scoping,\n"
        "listing and filtering."
    ),
    # -- quotations -------------------------------------------------------
    "quotations": (
        "Quotation header. Holds the customer, trade direction and a pointer to the current\n"
        "revision; all commercial detail lives in the revisions so history is never\n"
        "overwritten."
    ),
    "quotation_revisions": (
        "One version of a quotation's commercial terms. Editing an issued quotation creates a\n"
        "new revision instead of mutating this row, so what the customer accepted is always\n"
        "recoverable."
    ),
    "quotation_revision_places": "Routing stop of a quotation revision (origin, destination, pickup, delivery).",
    "quotation_revision_containers": "Container requirement line of a quotation revision.",
    "quotation_revision_lines": "Chargeable price line of a quotation revision.",
    "quotation_conversions": (
        "Record of a quotation revision being converted into a service order. Both unique\n"
        "constraints make conversion idempotent — a revision yields at most one service order\n"
        "and an order originates from at most one revision."
    ),
    # -- operations -------------------------------------------------------
    "service_orders": (
        "Service order header — the operational job opened for a customer. Containers,\n"
        "routing, movements, milestones, pricing and charges all hang off this row."
    ),
    "service_order_places": "Routing stop attached to a service order.",
    "service_order_container_requirements": "Container the customer has booked, before actual units are assigned to the job.",
    "service_order_containers": (
        "An actual physical container on the job, with its seal, weights and pickup/return\n"
        "dates."
    ),
    "service_order_pricing": (
        "Pricing summary of a service order. Exactly one row per order, enforced by the\n"
        "unique constraint on service_order_id."
    ),
    "service_order_pricing_lines": "Individual priced line of a service order.",
    "service_order_component_rows": (
        "One row of a table-mode component group, or the single record of a form-mode group.\n"
        "Values are stored as JSON keyed by the attribute code, so changing a group's\n"
        "attributes never requires a schema migration."
    ),
    "service_order_movements": "Planned versus actual movement leg of a service order.",
    "service_order_milestones": "Checkpoint on a service order's timeline (booking confirmed, gate-in, loaded, arrived).",
    "service_order_charges": "Customer-facing invoice or service note raised from a service order.",
    "service_order_charge_lines": "Chargeable line of a service order charge.",
    "attachments": (
        "Metadata for a file held in object storage (MinIO/S3). File bytes never live in\n"
        "PostgreSQL."
    ),
    "attachment_links": "Polymorphic link attaching a stored file to any business record.",
    # -- finance ----------------------------------------------------------
    "chart_of_accounts": (
        "Chart of accounts. A self-referencing tree of general-ledger accounts; is_postable\n"
        "marks the leaf accounts that journal lines may actually reference."
    ),
    "financial_accounts": (
        "Bank or cash account used for settlement, linked to the general-ledger account that\n"
        "carries its balance."
    ),
    "accounting_periods": (
        "Accounting month used to close the books. Posting is refused into a CLOSED period."
    ),
    "document_sequences": (
        "Per-type, per-year counter behind every human-facing document number (SO-000123,\n"
        "INV-000045). Provisioned for the current year during first-run setup."
    ),
    "financial_documents": (
        "Financial document header (tax invoice, proforma, credit note, receipt, payment).\n"
        "Holds the monetary totals and the link to the journal entry produced when it is\n"
        "posted."
    ),
    "financial_document_lines": "Line of a financial document.",
    "financial_document_sources": (
        "Tracks which business record generated a financial document, so a service order or\n"
        "quotation can be traced to the invoices it produced."
    ),
    "financial_document_allocations": (
        "Applies part of a payment document to an open invoice (or a payment against a\n"
        "credit). This is what makes partial settlement and multi-invoice payments possible."
    ),
    "posting_rules": (
        "Rule mapping a document type and fee type to the debit and credit general-ledger\n"
        "accounts applied when a document is posted."
    ),
    "journal_entries": (
        "Journal entry header. Every posted financial document produces one. Entries are\n"
        "immutable once posted and are corrected by reversal, never by editing."
    ),
    "journal_entry_lines": (
        "Debit or credit line of a journal entry. Amounts are held both in the transaction\n"
        "currency and in the base currency, so the ledger stays balanced across currencies."
    ),
    "financial_document_postings": (
        "Links a financial document to the journal entries it produced, so a reversal entry\n"
        "stays attached to the document it corrects."
    ),
    # -- auth -------------------------------------------------------------
    "users": (
        "Application user account — one row per person who can sign in. Authorization is\n"
        "granted through user_role_assignments (at most one active role) and the permissions\n"
        "that role carries."
    ),
    "user_credentials": (
        "Password material for a user, split from users so credential attributes can be\n"
        "locked down independently. user_id is both the primary key and the foreign key, so\n"
        "there is at most one credential row per user."
    ),
    "user_sessions": (
        "A refresh-token session, one row per issued refresh token. The token itself is\n"
        "stored only as a SHA-256 hash, so a database leak cannot be replayed."
    ),
    "roles": (
        "Named role bundling a set of permissions. The catalog is code-defined in\n"
        "app/core/permissions.py and synchronised on startup; administrators grant these\n"
        "roles through the Roles & Permissions screen."
    ),
    "permissions": (
        "Atomic capability in the code-defined permission catalog (for example\n"
        "service_orders.create), synchronised on startup. Rows are never edited by hand."
    ),
    "role_permissions": (
        "Join row granting one permission to one role. The composite primary key makes a\n"
        "duplicate grant impossible."
    ),
    "user_role_assignments": (
        "Assignment of a role to a user. Replacing a role expires the previous row instead of\n"
        "deleting it, so history is preserved while the partial unique index\n"
        "uq_user_role_assignments_active_user keeps at most one active assignment per user."
    ),
    "password_reset_tokens": (
        "One-time password reset code. Only the hash of the code is stored; rows are retained\n"
        "after use for audit purposes."
    ),
    # -- archive ----------------------------------------------------------
    "archive_records": (
        "Archive/restore journal for soft-deleted business records. The row outlives a hard\n"
        "deletion, so a removed record stays traceable and — where a snapshot exists —\n"
        "recoverable."
    ),
    # -- audit ------------------------------------------------------------
    "audit_events": (
        "Append-only audit trail of security- and money-relevant actions. Application code\n"
        "never updates or deletes these rows."
    ),
    # -- backup -----------------------------------------------------------
    "backup_runs": (
        "One execution of the Google Sheets backup job (manual or scheduled) with its\n"
        "counters and outcome. Runs are kept for operational history."
    ),
    "backup_records": (
        "One immutable version of one database row. Append-only: a complete history of every\n"
        "change is preserved and can be replayed after data loss."
    ),
    "backup_states": (
        "Latest known hash per row, letting the backup job skip unchanged rows without\n"
        "reading the whole table."
    ),
    "backup_logs": "Structured log lines emitted per table while a backup run executes.",
}

# --------------------------------------------------------------------------
# Column descriptions that mean exactly the same thing on every table
# --------------------------------------------------------------------------

COMMON_COLUMNS: dict[str, str] = {
    "id": "Surrogate primary key. BIGSERIAL sequence-backed and never reused.",
    "created_at": (
        "Row creation timestamp (UTC, timezone-aware). Written once; server default now()."
    ),
    "updated_at": (
        "Last modification timestamp (UTC, timezone-aware). Refreshed by the application on\n"
        "every update."
    ),
    "deleted_at": (
        "Soft-deletion timestamp. A non-NULL value means the row is archived: it is excluded\n"
        "from listings and uniqueness checks but stays in place."
    ),
    "line_no": (
        "Sequential line number within the parent document, 1-based and displayed in order."
    ),
    "unit_code": (
        "Unit of measure code for quantity (e.g. SET, CONTAINER, BL, KG, PERCENT)."
    ),
    "currency_code": (
        "ISO 4217 alphabetic currency code (e.g. USD, KHR). Monetary amounts on the row are\n"
        "denominated in this currency."
    ),
    "display_order": (
        "Sort position within its group or list. Lower values are rendered first; ties are\n"
        "broken by code."
    ),
    "is_active": "TRUE when the record is enabled and offered to users.",
    "is_archived": (
        "TRUE when the record has been withdrawn. Archived records are hidden from pickers but\n"
        "retained so historical documents still resolve."
    ),
}

# --------------------------------------------------------------------------
# Mechanical suffix rules, applied after COMMON_COLUMNS
# --------------------------------------------------------------------------

_SUFFIX_RULES: dict[str, str] = {
    "_by_user_id": (
        "Identifier of the user who {action} this record. NULL when the action was performed\n"
        "by the system, or set to NULL by ON DELETE SET NULL once the user is removed."
    ),
}

_SUFFIX_ACTIONS: dict[str, str] = {
    "assigned": "assigned",
    "closed": "closed the accounting period for",
    "converted": "converted",
    "created": "created",
    "deleted": "archived",
    "hard_deleted": "permanently deleted",
    "posted": "posted",
    "restored": "restored",
    "triggered": "triggered",
    "updated": "last updated",
    "uploaded": "uploaded",
}


def describe_column(table_name: str, column_name: str) -> str | None:
    """Return the documented meaning of a column, or None when undocumented.

    Lookup order: table-specific text, then the shared common text, then the
    mechanical suffix rules.
    """
    specific = COLUMN_DESCRIPTIONS.get(table_name, {}).get(column_name)
    if specific:
        return specific
    common = COMMON_COLUMNS.get(column_name)
    if common:
        return common
    for suffix, template in _SUFFIX_RULES.items():
        if column_name.endswith(suffix):
            prefix = column_name[: -len(suffix)]
            action = _SUFFIX_ACTIONS.get(prefix)
            if action:
                return template.format(action=action)
    return None


# --------------------------------------------------------------------------
# Table-specific column descriptions
# --------------------------------------------------------------------------

COLUMN_DESCRIPTIONS: dict[str, dict[str, str]] = {
    # -- users ------------------------------------------------------------
    "users": {
        "user_code": "Stable business identifier for the user (e.g. EMP-0001). Unique and never reused.",
        "username": "Login name used to sign in. Unique across all users.",
        "email": (
            "Primary email address. Unique, and the delivery target for password reset codes\n"
            "and notifications."
        ),
        "display_name": (
            "Human-readable name shown in the UI, the audit trail and on printed documents."
        ),
        "status": (
            "Account lifecycle state (ACTIVE, INACTIVE, LOCKED). A non-ACTIVE user cannot\n"
            "authenticate."
        ),
        "locale": (
            "Default UI language for this user (en, km, zh). A user may override it per\n"
            "session."
        ),
        "timezone": "IANA timezone name used to render dates and times for this user.",
        "system_identity": (
            "Immutable machine identity for built-in accounts (e.g. DEFAULT_SYSTEM_ADMIN).\n"
            "Never accepted from an API payload and never changed by user management."
        ),
        "last_login_at": "Timestamp of the most recent successful authentication.",
        "token_version": (
            "Counter embedded in issued access tokens. Incrementing it invalidates every\n"
            "outstanding token for the user, making revocation immediate despite stateless JWTs."
        ),
    },
    # -- user_credentials -------------------------------------------------
    "user_credentials": {
        "user_id": (
            "Owning user. Primary key and foreign key to users.id, so at most one credential row\n"
            "exists per user."
        ),
        "password_hash": (
            "Argon2id password digest. The plaintext password is never stored or logged."
        ),
        "password_algorithm": (
            "Hashing algorithm that produced password_hash (argon2id). Kept explicit so the\n"
            "algorithm can be upgraded without invalidating existing hashes."
        ),
        "password_changed_at": "Timestamp of the last successful password change.",
        "must_change_password": (
            "True when the password was chosen by somebody other than its owner. While set,\n"
            "every API route except changing the password answers 403, so a temporary\n"
            "password cannot be kept in use indefinitely. Cleared by change_password."
        ),
        "failed_attempt_count": (
            "Consecutive failed sign-in attempts since the last success. Reset to zero on a\n"
            "successful authentication."
        ),
        "locked_until": (
            "Instant until which sign-in is refused after too many failed attempts. NULL when\n"
            "the account is not locked."
        ),
    },
    # -- user_sessions ----------------------------------------------------
    "user_sessions": {
        "user_id": "Session owner.",
        "refresh_token_hash": (
            "SHA-256 hash of the refresh token. Unique. Token rotation replaces this value, so\n"
            "a stolen copy of the old token is rejected after first use."
        ),
        "device_name": "Friendly device or browser label shown in the user's active-session list.",
        "ip_address": "IP address the session was created from, retained for audit and anomaly detection.",
        "user_agent": "Raw User-Agent header captured at sign-in.",
        "last_used_at": "Timestamp of the most recent request authenticated by this session.",
        "expires_at": "Hard expiry enforced by the server; the session is invalid after this instant.",
        "revoked_at": "Set when the session is logged out or revoked. NULL while the session is valid.",
        "remember_me": (
            "TRUE for \"Remember me\" sessions: a persistent cookie plus the full configured\n"
            "lifetime, instead of a browser-session cookie with a short deadline."
        ),
    },
    # -- roles / permissions ---------------------------------------------
    "roles": {
        "code": "Stable machine code for the role (e.g. FINANCE_MANAGER). Unique.",
        "name": "Display name shown in the Roles & Permissions matrix.",
        "description": "Human-readable explanation of what the role is allowed to do.",
        "is_system_role": (
            "TRUE for built-in roles that must not be renamed or deleted (for example the\n"
            "Platform Administrator and the zero-permission migrated-users role)."
        ),
        "status": "Role lifecycle state (ACTIVE, INACTIVE). An inactive role grants nothing.",
    },
    "permissions": {
        "code": (
            "Fully-qualified permission code in the form <resource>.<action> (for example\n"
            "service_orders.create). This is the value every authorization check matches on."
        ),
        "name": "Display name for the permission.",
        "resource": "Resource segment of the code — the page or entity the action applies to.",
        "action": (
            "Action segment of the code (create, read, update, delete, approve, export, print,\n"
            "reset, restore, manage...)."
        ),
        "description": "Explanation of what the action allows.",
    },
    "role_permissions": {
        "role_id": "Role that receives the grant.",
        "permission_id": "Permission being granted to the role.",
    },
    "user_role_assignments": {
        "user_id": "User the role is assigned to.",
        "role_id": "Role held by the user. Single-role RBAC: only the active row counts.",
        "starts_at": "Moment the assignment becomes effective.",
        "expires_at": (
            "Expiry of a temporary assignment. NULL means active and permanent; the partial\n"
            "unique index uq_user_role_assignments_active_user covers exactly these rows and is\n"
            "the database-level one-user/one-active-role guarantee."
        ),
    },
    "password_reset_tokens": {
        "user_id": "User the reset code was issued for.",
        "email": "Email address the reset code was delivered to.",
        "code_hash": "SHA-256 hash of the reset code. Only this digest is stored and compared.",
        "expires_at": "Instant after which the code is rejected.",
        "used_at": "Set once the code has been redeemed. NULL while the code is still unused.",
        "created_at": "Request timestamp for this reset code.",
    },
    # -- master data ------------------------------------------------------
    "place_roles": {
        "code": (
            "Stable role code (e.g. PICKUP). Unique among non-archived rows and stored on a\n"
            "route stop as its printable snapshot."
        ),
        "name": "Display name shown in the route-stop dropdown and on the document.",
        "description": "Free-text explanation of when the role applies.",
        "sort_order": (
            "Administrator-controlled display order in the Place Roles page and in every\n"
            "route-stop dropdown; ties break by name."
        ),
        "status": "Record status (ACTIVE, INACTIVE). A new route stop may only select an ACTIVE role.",
    },
    "party_roles": {
        "code": "Stable role code (e.g. CUSTOMER). Unique among non-archived rows.",
        "name": "Display name shown in the Business Parties form and in lists.",
        "description": "Free-text explanation of when the role applies.",
        "status": "Record status (ACTIVE, INACTIVE). Only an ACTIVE role is offered on a new assignment.",
    },
    "business_party_roles": {
        "business_party_id": "Party holding the role. CASCADE when the party is purged.",
        "party_role_id": "Assigned role. RESTRICT so an assigned role cannot be hard-deleted.",
    },
    "trade_directions": {
        "code": "Short direction code (e.g. EXPORT). Unique among non-archived rows.",
        "name": "Display name of the trade direction.",
        "description": "Free-text notes about the trade direction.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "container_types": {
        "code": "Container type code (e.g. 20GP, 40HC). Unique among non-archived rows.",
        "name": "Display name of the container type.",
        "container_size": "Nominal size class, for example 20GP, 40HC or 45HC.",
        "container_kind": "Equipment kind: general purpose, reefer, open top, flat rack, tank.",
        "iso_code": "ISO 6346 size and type code, for example 22G1 for a 20-foot general purpose box.",
        "length_feet": "External length in feet (NUMERIC(6,2)).",
        "width_millimeter": "External width in millimetres (NUMERIC(8,2)).",
        "height_millimeter": "External height in millimetres (NUMERIC(8,2)).",
        "max_gross_weight_kg": "Maximum gross weight in kilograms (NUMERIC(12,3)).",
        "description": "Free-text notes about the container type.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "transport_types": {
        "code": "Short transport-mode code (e.g. SEA). Unique among non-archived rows.",
        "name": "Display name of the transport mode.",
        "description": "Free-text notes about the transport mode.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "fee_types": {
        "code": "Short fee code (e.g. THC). Unique among non-archived rows.",
        "name": "Display name of the chargeable service.",
        "description": "Free-text notes about the fee.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "business_parties": {
        "party_code": "Stable business identifier for the party (e.g. CUST-0001).",
        "legal_name": "Registered legal name. Printed on tax invoices.",
        "display_name": (
            "Short name used in lists and dropdowns when it differs from the legal name."
        ),
        "vat_tin": (
            "VAT / tax identification number. Unique among non-archived rows so a party cannot\n"
            "be duplicated by re-entering the same tax number."
        ),
        "contact_person": "Primary contact name.",
        "phone": "Primary contact phone number.",
        "email": "Primary contact email address.",
        "address": "Registered or operating address.",
        "roles": (
            "Legacy JSON snapshot of the party's role names. Assignments are read from\n"
            "business_party_roles, so a role rename is reflected without rewriting this column."
        ),
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "transport_assets": {
        "asset_code": "Fleet or internal asset number (e.g. VH-118).",
        "transport_type_id": "Transport mode this asset belongs to.",
        "identity": "Registration number, IMO number or tail number identifying the asset.",
        "identity_type": "What identity represents: License Plate, IMO Number, Flight Number or Other.",
        "owner_party_id": "Business party that owns the asset.",
        "operator_party_id": "Business party that operates the asset; may differ from the owner.",
        "description": "Free-text notes about the asset.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "customer_customs_accounts": {
        "party_id": (
            "Customer the account belongs to. Deleting the party cascades the account row away."
        ),
        "system_name": (
            "External system the credentials belong to, for example a customs declaration\n"
            "portal."
        ),
        "username": "Username on the external system.",
        "password_secret_reference": (
            "Reference to the secret-store entry holding the password. Preferred over\n"
            "storing the secret inline."
        ),
        "encrypted_password": (
            "Encrypted password, used only when no secret-store reference is available. The\n"
            "plaintext is never stored."
        ),
        "last_verified_at": (
            "Timestamp of the last successful automated verification against the external\n"
            "system."
        ),
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "component_attributes": {
        "code": (
            "Attribute code. Also the JSON key under which the value is stored in\n"
            "service_order_component_rows.values, so changing it orphans existing values."
        ),
        "label": "English label rendered in the UI.",
        "label_km": (
            "Admin-managed Khmer label. This is user-defined data, not a parallel copy of\n"
            "label — copy shipped in code is resolved through the i18n bundles instead."
        ),
        "data_type": "Storage and logic type: text, number, date, boolean, select, reference.",
        "input_type": "UI widget override, used when it differs from the widget implied by data_type.",
        "reference_type": (
            "Master-data collection a reference-type attribute points at, for example\n"
            "business_parties or container_types."
        ),
        "is_required": "Default required flag. An individual component group may override it.",
        "default_value": "Value pre-filled when a new row is created.",
        "placeholder": "Hint shown inside the empty input.",
        "width": "Rendered column width hint for table-mode groups.",
        "options": "JSON array of selectable values for a select-type attribute.",
        "validation_rules": "JSON object of validation rules (min, max, pattern, required, ...).",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "component_groups": {
        "code": "Group code. Unique and referenced by component_tab_groups.",
        "name": "Display name of the group.",
        "name_km": "Admin-managed Khmer name.",
        "description": "Free-text explanation of what the group collects.",
        "render_mode": (
            "Legacy default only: 'table' or 'form'. The effective layout is\n"
            "component_tab_groups.display_mode; NULL there inherits this value."
        ),
        "is_active": "TRUE when the group is enabled for new service orders.",
    },
    "component_group_attributes": {
        "group_id": "Component group the attribute belongs to. CASCADE on group deletion.",
        "attribute_id": "Attribute catalog entry being included. CASCADE on attribute deletion.",
        "is_required": "Group-level override of the required flag. NULL inherits the attribute default.",
        "width": "Group-level width override. NULL inherits the attribute default.",
        "is_visible": "FALSE hides the field in every tab that uses this group. Values already saved are kept.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "component_tabs": {
        "code": "Tab code. Unique and referenced by the frontend tab registry.",
        "name": "Display name of the tab.",
        "description": "Free-text explanation of what the tab holds.",
        "trade_direction_id": (
            "Trade direction the tab applies to. NULL means the tab is shown for every\n"
            "direction."
        ),
        "is_active": "TRUE when the tab is enabled on the Service Order form.",
        "config_version_id": (
            "Published configuration version this tab participated in. NULL for a tab created\n"
            "after the last publish; set by the next publish."
        ),
    },
    "component_tab_groups": {
        "tab_id": "Component tab the group belongs to. CASCADE on tab deletion.",
        "group_id": "Component group shown on the tab. CASCADE on group deletion.",
        "display_mode": (
            "How this group renders in this tab: form_only, table_only or\n"
            "form_and_table. NULL inherits component_groups.render_mode."
        ),
        "data_cardinality": (
            "Whether the group holds a single record or multiple records in this tab.\n"
            "NULL inherits component_groups.render_mode."
        ),
        "form_columns": "Number of form columns (1-4) for form layouts. NULL inherits the default of 3.",
        "show_group_title": "Whether the group heading is rendered. NULL defaults to TRUE.",
        "editable": "FALSE renders the group read-only and makes the save endpoint refuse writes. NULL defaults to TRUE.",
        "collapsible": "Whether the group can be collapsed by the user. NULL defaults to FALSE.",
        "default_expanded": "Initial expanded state of a collapsible group. NULL defaults to TRUE.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "module_records": {
        "collection": (
            "Frontend collection this record belongs to (for example 'shipments'). Indexed\n"
            "for list filtering."
        ),
        "record_no": "Business reference number of the record within its collection.",
        "status": "Workflow status of the record.",
        "data": "JSONB payload holding every configured field of the collection.",
    },
    # -- quotations -------------------------------------------------------
    "quotations": {
        "quotation_no": "Human-facing quotation number, allocated from document_sequences. Unique.",
        "customer_party_id": "Business party the quotation is issued to.",
        "trade_direction_id": "Trade direction the quotation covers.",
        "current_revision_no": (
            "Revision number currently treated as the live offer. Revisions are never deleted,\n"
            "so superseded numbers stay reachable for audit."
        ),
        "status": (
            "Quotation lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED, CONVERTED)."
        ),
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "quotation_revisions": {
        "quotation_id": "Quotation this revision belongs to. CASCADE on quotation deletion.",
        "revision_no": (
            "Sequential revision number within the quotation, 1-based. Unique per quotation\n"
            "together with quotation_id."
        ),
        "status": (
            "Revision lifecycle state (DRAFT, SENT, ACCEPTED, REJECTED, EXPIRED, SUPERSEDED,\n"
            "CONVERTED)."
        ),
        "quotation_date": "Date printed on the quotation.",
        "valid_until": (
            "Last date the offer is honoured. Past this date the revision is treated as\n"
            "EXPIRED."
        ),
        "description": "Short summary of the quotation.",
        "notes": "Terms and conditions printed with the quotation.",
        "subtotal_amount": "Sum of line subtotals before discount and tax.",
        "discount_amount": "Total discount applied across all lines.",
        "tax_amount": "Total tax (VAT) charged across all lines.",
        "total_amount": "Payable total: subtotal minus discount plus tax.",
        "sent_at": "Timestamp this revision was sent to the customer.",
        "accepted_at": (
            "Timestamp the customer accepted this revision. The acceptance locks the commercial\n"
            "terms; further changes require a new revision."
        ),
        "rejected_at": "Timestamp the customer rejected this revision.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "quotation_revision_places": {
        "quotation_revision_id": "Revision the routing stop belongs to. CASCADE on revision deletion.",
        "place_role_id": (
            "Configured Place Role the stop plays. SET NULL only if the role row is purged;\n"
            "the place_role text snapshot keeps the historical label."
        ),
        "place_role": (
            "Text snapshot of the role (the role name at save time). Preserved so a route\n"
            "still prints after the role is renamed or deactivated."
        ),
        "sequence_no": (
            "Position of this stop within the route. Unique per revision; the server\n"
            "renumbers from the submitted row order."
        ),
        "planned_at": "Planned date/time for the stop.",
        "free_text": "Free-text location typed for the stop, kept for printing and history.",
        "notes": "Free-text notes about this stop.",
    },
    "quotation_revision_containers": {
        "quotation_revision_id": "Revision the requirement belongs to. CASCADE on revision deletion.",
        "container_type_id": "Container type being quoted.",
        "quantity": "Number of containers of this type quoted (NUMERIC(12,3)).",
        "gross_weight_kg": "Quoted gross weight per container in kilograms.",
        "description": "Short description of the container requirement.",
        "remarks": "Free-text remarks shown on the quotation.",
    },
    "quotation_revision_lines": {
        "quotation_revision_id": "Revision the price line belongs to. CASCADE on revision deletion.",
        "fee_type_id": "Catalogue fee this line prices.",
        "container_requirement_id": (
            "Container requirement this line prices. Set for per-container charges, NULL for\n"
            "document-level charges."
        ),
        "service_description": "Description printed on the quotation for this line.",
        "quantity": "Billed quantity (NUMERIC(12,3)).",
        "unit_price": "Price per unit in currency_code, before discount and tax.",
        "discount_rate": (
            "Discount applied to the line as a rate (NUMERIC(7,4); 0.0500 means 5%)."
        ),
        "tax_rate": "Tax/VAT rate applied to the line (NUMERIC(7,4); 0.1000 means 10%).",
        "line_subtotal": "quantity multiplied by unit_price, before discount and tax.",
        "line_discount": "Absolute discount deducted from line_subtotal.",
        "line_tax": "Absolute tax charged on the discounted amount.",
        "line_total": "Final payable amount for this line.",
    },
    "quotation_conversions": {
        "quotation_revision_id": (
            "Revision that was converted. UNIQUE, so a revision can produce at most one\n"
            "service order."
        ),
        "service_order_id": (
            "Service order created from the revision. UNIQUE, so an order originates from at\n"
            "most one revision."
        ),
        "converted_at": "Timestamp the conversion was performed.",
        "notes": "Free-text notes recorded at conversion time.",
        "idempotency_key": (
            "Client-supplied key that makes a repeated conversion request a no-op. UNIQUE."
        ),
    },
    # -- operations -------------------------------------------------------
    "service_orders": {
        "service_order_no": (
            "Human-facing order number allocated from document_sequences. Unique."
        ),
        "quotation_revision_id": (
            "Quotation revision this order was converted from. NULL for orders entered\n"
            "directly."
        ),
        "customer_party_id": "Business party the job is performed for.",
        "trade_direction_id": "Trade direction the job covers.",
        "status": (
            "Order lifecycle state (DRAFT, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED).\n"
            "Indexed because the order list filters on it."
        ),
        "description": "Short summary of the job.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
        "configuration_version_id": (
            "Published configuration version this order was created under. Pins the order to the\n"
            "dynamic form it was filled in, so publishing a new configuration cannot\n"
            "re-interpret its saved component rows."
        ),
    },
    "service_order_places": {
        "service_order_id": "Service order the stop belongs to. CASCADE on order deletion.",
        "place_role_id": (
            "Configured Place Role the stop plays. Copied from the quotation on conversion,\n"
            "then independent; SET NULL only if the role row is purged."
        ),
        "place_role": (
            "Text snapshot of the role at save time. Preserved so a route still prints after\n"
            "the role is renamed or deactivated."
        ),
        "sequence_no": (
            "Position of this stop within the route. Unique per order; the server renumbers\n"
            "from the submitted row order."
        ),
        "planned_at": "Planned date/time for the stop.",
        "actual_at": "Actual date/time the stop was served, when known.",
        "free_text": "Free-text location typed for the stop, kept for printing and history.",
        "is_actual": (
            "TRUE when actual_at is set, i.e. the stop has actually been served. Kept for\n"
            "reports written before actual_at existed."
        ),
        "notes": "Free-text notes about this stop.",
    },
    "service_order_container_requirements": {
        "service_order_id": "Service order the requirement belongs to. CASCADE on order deletion.",
        "source_quotation_container_id": (
            "Quotation container requirement this line was converted from, or NULL when it was\n"
            "added directly."
        ),
        "container_type_id": "Container type being booked.",
        "quantity": "Number of containers of this type booked (NUMERIC(12,3)).",
        "gross_weight_kg": "Expected gross weight per container in kilograms.",
        "description": "Short description of the requirement.",
        "remarks": "Free-text remarks about the requirement.",
    },
    "service_order_containers": {
        "service_order_id": "Service order the container belongs to. CASCADE on order deletion.",
        "container_requirement_id": (
            "Booked requirement this actual container fulfils, or NULL when it was not planned."
        ),
        "container_type_id": "Container type of the actual unit.",
        "container_number": (
            "ISO 6346 container number printed on the box. UNIQUE across the system, so a unit\n"
            "cannot be booked twice."
        ),
        "seal_serial": "Seal number recorded at stuffing or gate-in.",
        "status": (
            "Container lifecycle state (EXPECTED, STUFFED, GATE_IN, GATE_OUT, DEVOURED,\n"
            "RETURNED)."
        ),
        "net_weight_kg": "Net (cargo) weight in kilograms (NUMERIC(12,3)).",
        "gross_weight_kg": "Gross (tare plus cargo) weight in kilograms (NUMERIC(12,3)).",
        "pickup_date": "Date the container is collected.",
        "return_date": "Date the empty container is returned.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "service_order_pricing": {
        "service_order_id": (
            "Service order this summary belongs to. UNIQUE, so an order always has exactly one\n"
            "pricing summary."
        ),
        "subtotal_amount": "Sum of line subtotals before discount and tax.",
        "discount_amount": "Total discount applied across all pricing lines.",
        "tax_amount": "Total tax (VAT) charged across all pricing lines.",
        "total_amount": "Payable total: subtotal minus discount plus tax.",
    },
    "service_order_pricing_lines": {
        "service_order_pricing_id": "Pricing summary the line belongs to. CASCADE on summary deletion.",
        "source_quotation_line_id": (
            "Quotation price line this line was converted from, or NULL when priced directly."
        ),
        "fee_type_id": "Catalogue fee priced by this line.",
        "description": "Description printed on the order for this line.",
        "quantity": "Billed quantity (NUMERIC(12,3)).",
        "unit_price": "Price per unit in currency_code, before discount and tax.",
        "discount_rate": "Discount applied to the line as a rate (NUMERIC(7,4)).",
        "tax_rate": "Tax/VAT rate applied to the line (NUMERIC(7,4)).",
        "line_total": "Final payable amount for this line.",
    },
    "service_order_component_rows": {
        "service_order_id": "Service order the row belongs to. CASCADE on order deletion.",
        "group_id": "Component group this row renders. CASCADE on group deletion.",
        "row_no": "Position of this row within its group. NULL for rows written directly.",
        "values": (
            "JSONB map of attribute code to entered value. Keyed by component_attributes.code so\n"
            "that changing a group's attributes needs no migration."
        ),
        "config_version_id": (
            "Configuration version in force when the row was written, so a later configuration\n"
            "change never invalidates a saved row: it is still interpreted against the layout and\n"
            "rules it was captured under."
        ),
    },
    "service_order_movements": {
        "service_order_id": "Service order the movement leg belongs to. CASCADE on order deletion.",
        "sequence_no": "Order of this leg along the shipment itinerary.",
        "transport_type_id": "Mode of transport used for this leg.",
        "transport_asset_id": "Specific vehicle, vessel or aircraft performing the leg.",
        "planned_departure": "Scheduled departure (UTC, timezone-aware).",
        "actual_departure": "Recorded departure. NULL until the leg actually departs.",
        "planned_arrival": "Scheduled arrival (UTC, timezone-aware).",
        "actual_arrival": "Recorded arrival. NULL until the leg actually arrives.",
        "status": "Movement lifecycle state (PLANNED, IN_TRANSIT, ARRIVED, CANCELLED).",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "service_order_milestones": {
        "service_order_id": "Service order the milestone belongs to. CASCADE on order deletion.",
        "milestone_code": (
            "Stable machine code for the checkpoint (e.g. GATE_IN), used to drive progress\n"
            "reporting."
        ),
        "milestone_name": "Display name of the checkpoint as printed on the order.",
        "sequence_no": "Order of this checkpoint along the timeline.",
        "planned_at": "Scheduled time of the checkpoint (UTC, timezone-aware).",
        "actual_at": "Recorded time the checkpoint was reached.",
        "status": "Checkpoint state (PENDING, DONE, MISSED, SKIPPED).",
        "notes": "Free-text notes about the checkpoint.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "service_order_charges": {
        "service_order_id": "Service order the charge belongs to. CASCADE on order deletion.",
        "charge_no": (
            "Document number allocated from document_sequences. UNIQUE across all charges."
        ),
        "document_type": (
            "Document kind (SERVICE_NOTE, PROFORMA_INVOICE, TAX_INVOICE, CREDIT_NOTE)."
        ),
        "document_date": "Date printed on the document.",
        "status": (
            "Charge lifecycle state (DRAFT, ISSUED, SENT, PAID, VOID). Indexed because the\n"
            "charges list filters on it."
        ),
        "subtotal_amount": "Sum of line amounts before discount and tax.",
        "discount_amount": "Total discount applied across all charge lines.",
        "tax_amount": "Total tax (VAT) charged across all charge lines.",
        "total_amount": "Payable total: subtotal minus discount plus tax.",
        "remark": "Free-text remark printed at the foot of the document.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "service_order_charge_lines": {
        "service_order_charge_id": "Charge document the line belongs to. CASCADE on deletion.",
        "fee_type_id": "Catalogue fee billed by this line.",
        "service_order_container_id": (
            "Container this charge is attributed to, for per-container billing. NULL for\n"
            "document-level charges."
        ),
        "description": "Description printed on the charge for this line.",
        "quantity": "Billed quantity (NUMERIC(12,3)).",
        "unit_price": "Price per unit in currency_code, before discount and tax.",
        "discount_amount": "Absolute discount deducted from the line subtotal.",
        "tax_rate": "Tax/VAT rate applied to the line (NUMERIC(7,4)).",
        "tax_amount": "Absolute tax charged on this line.",
        "line_amount": "Final payable amount for this line.",
    },
    "attachments": {
        "file_name": "Original file name as uploaded.",
        "storage_key": (
            "Object key inside the storage bucket. UNIQUE and the canonical identifier of the\n"
            "stored blob."
        ),
        "mime_type": "MIME type detected at upload time.",
        "file_size_bytes": "Size of the stored object in bytes.",
        "checksum": "Digest used to detect duplicates and corruption.",
        "storage_provider": "Storage backend holding the object: local or minio.",
        "document_version": "Version number, incremented when several revisions of one document are stored.",
        "uploaded_at": "Timestamp the object was written to storage.",
        "is_deleted": (
            "Soft-delete marker for this metadata row. The stored object is removed separately,\n"
            "so the row remains as a tombstone."
        ),
    },
    "attachment_links": {
        "attachment_id": "Attachment being linked. CASCADE on attachment deletion.",
        "entity_type": "Table name of the linked record, for example 'service_orders'.",
        "entity_id": (
            "Primary key of the linked record, resolved together with entity_type. Deliberately\n"
            "not a foreign key, because a link may point at any table."
        ),
        "attachment_role": (
            "Purpose of the attachment: ATTACHMENT, INVOICE, POD (proof of delivery), CUSTOMS\n"
            "DECLARATION, BILL_OF_LADING and similar."
        ),
        "is_primary": (
            "TRUE for the one file that represents the record, for example the signed proof of\n"
            "delivery."
        ),
        "created_at": "Timestamp the link was created.",
    },
    # -- finance ----------------------------------------------------------
    "chart_of_accounts": {
        "account_code": "Account number as printed in the trial balance. Unique.",
        "account_name": "Name of the account.",
        "account_type": "Top-level classification: ASSET, LIABILITY, EQUITY, REVENUE or EXPENSE.",
        "parent_account_id": "Parent account in the hierarchy. NULL for a top-level account.",
        "normal_balance": "DEBIT or CREDIT — the side on which the account normally increases.",
        "is_postable": (
            "TRUE when journal lines may post to this account. FALSE for headers and roll-up\n"
            "accounts."
        ),
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "financial_accounts": {
        "account_id": (
            "General-ledger account holding this bank or cash balance. UNIQUE, so one GL\n"
            "account maps to at most one financial account."
        ),
        "account_name": "Display name of the bank or cash account.",
        "account_type": "Instrument type: BANK, CASH, CARD or MOBILE_WALLET.",
        "bank_name": "Name of the bank or provider.",
        "account_number_masked": (
            "Masked account number such as ****1234. The full number is never stored in the\n"
            "database."
        ),
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "accounting_periods": {
        "period_year": "Calendar year of the accounting month.",
        "period_month": "Month number, 1 to 12.",
        "start_date": "First day of the accounting month.",
        "end_date": "Last day of the accounting month.",
        "status": (
            "Period state (OPEN, CLOSING, CLOSED). Indexed because every posting resolves the\n"
            "period by status."
        ),
        "closed_at": "Timestamp the period was closed. NULL while it is still open.",
    },
    "document_sequences": {
        "document_type": "Document family the counter serves, for example SERVICE_ORDER or TAX_INVOICE.",
        "period_year": (
            "Calendar year the counter belongs to. Sequences restart each year, and the unique\n"
            "constraint on (document_type, period_year) is what keeps them independent."
        ),
        "prefix": "Literal prefix emitted before the number, for example 'SO-'.",
        "last_value": (
            "Highest number already issued. Incremented while holding a row lock so concurrent\n"
            "requests cannot produce duplicates or reuse a number."
        ),
        "padding_length": "Zero-padding width of the numeric part, so numbers sort lexically.",
        "status": "Record status (ACTIVE, INACTIVE).",
    },
    "financial_documents": {
        "document_no": "Document number allocated from document_sequences. UNIQUE.",
        "document_type": (
            "Document kind: TAX_INVOICE, PROFORMA_INVOICE, CREDIT_NOTE, DEBIT_NOTE, RECEIPT or\n"
            "PAYMENT."
        ),
        "document_date": "Date of the document as printed.",
        "posting_date": (
            "Date the document was posted to the ledger. This, not document_date, selects the\n"
            "accounting period it lands in."
        ),
        "status": (
            "Document lifecycle state (DRAFT, POSTED, PAID, PARTIALLY_PAID, CANCELLED,\n"
            "REVERSED). Indexed because document lists filter on it."
        ),
        "party_id": "Business party the document is issued to or received from.",
        "service_order_id": "Service order the document bills.",
        "exchange_rate": (
            "Rate applied to convert currency_code into base_currency_code (NUMERIC(19,8)):\n"
            "base amount = amount * rate. Always 1 when the document is already in the base\n"
            "currency, and snapshotted here so the conversion survives a rate change."
        ),
        "description": "Short description of the document.",
        "reference_number": "External reference, for example the customer's PO or our own proforma number.",
        "due_date": "Date payment falls due.",
        "payment_method_code": "How the payment was or will be made (CASH, BANK_TRANSFER, CARD).",
        "financial_account_id": "Bank or cash account a payment receipt was booked against.",
        "value_date": (
            "Bank value date of a payment document. Kept separate from document_date because\n"
            "the two often differ by a day or two."
        ),
        "subtotal_amount": "Sum of line amounts before discount and tax.",
        "discount_amount": "Total discount applied across all lines.",
        "tax_amount": "Total tax (VAT) charged across all lines.",
        "total_amount": "Document total: subtotal minus discount plus tax.",
        "base_currency_code": (
            "Base currency this document converts into, taken from the company's configured\n"
            "base currency when the document is saved. NULL on rows written before\n"
            "multi-currency existed, when the base currency was a setting that may since have\n"
            "changed."
        ),
        "base_subtotal_amount": "subtotal_amount converted into base_currency_code at exchange_rate.",
        "base_discount_amount": "discount_amount converted into base_currency_code at exchange_rate.",
        "base_tax_amount": "tax_amount converted into base_currency_code at exchange_rate.",
        "base_total_amount": (
            "total_amount converted into base_currency_code at exchange_rate, rounded with the\n"
            "document currency's precision. Re-derived when the document posts, so it always\n"
            "agrees with the journal lines it writes."
        ),
        "paid_amount": "Amount already settled through financial_document_allocations.",
        "posted_at": "Timestamp the document was posted to the ledger.",
        "reversed_document_id": (
            "Document that this row reverses. Set on the reversing row and NULL on originals, so\n"
            "a reversal is always traceable in both directions."
        ),
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "financial_document_lines": {
        "financial_document_id": "Document the line belongs to. CASCADE on document deletion.",
        "description": "Description printed on the document for this line.",
        "fee_type_id": "Catalogue fee billed by this line.",
        "quantity": "Billed quantity (NUMERIC(12,3)).",
        "unit_price": "Price per unit in currency_code, before discount and tax.",
        "discount_amount": "Absolute discount deducted from the line subtotal.",
        "tax_rate": "Tax/VAT rate applied to the line (NUMERIC(7,4)).",
        "tax_amount": "Absolute tax charged on this line.",
        "line_amount": "Final payable amount for this line.",
        "service_order_id": "Service order the line is attributed to.",
        "service_order_container_id": "Container the line is attributed to, for per-container billing.",
        "account_id": (
            "General-ledger account this line posts to. When set it overrides the posting rule,\n"
            "which is how ad-hoc accounts are supported."
        ),
    },
    "financial_document_sources": {
        "financial_document_id": "Document generated from the source record. CASCADE on deletion.",
        "source_type": "Table name of the source record, for example 'service_orders'.",
        "source_id": (
            "Primary key of the source record, resolved together with source_type. Deliberately\n"
            "not a foreign key, because the source may live in any table."
        ),
        "relationship_type": "How the source relates to the document: GENERATED_FROM, REFERENCES or SUPERSEDES.",
        "created_at": "Timestamp the link was created.",
    },
    "financial_document_allocations": {
        "payment_document_id": "Payment or receipt document that holds the money.",
        "target_document_id": "Open document the money is applied to (an invoice or a credit).",
        "allocated_amount": "Amount of the payment applied to target_document_id.",
        "allocated_currency_code": "ISO 4217 code of allocated_amount, which may differ from either document.",
        "exchange_rate": "Rate used to convert allocated_currency_code into the base currency.",
        "allocated_at": "Timestamp the allocation was applied.",
        "idempotency_key": (
            "UNIQUE key that makes a repeated allocation request a no-op. This is what stops a\n"
            "retried request from double-settling an invoice."
        ),
    },
    "posting_rules": {
        "document_type": "Document type the rule applies to.",
        "fee_type_id": (
            "Fee type the rule applies to. NULL makes it the fallback rule for the whole\n"
            "document type."
        ),
        "debit_account_id": "General-ledger account debited when a matching document is posted.",
        "credit_account_id": "General-ledger account credited when a matching document is posted.",
        "tax_account_id": "General-ledger account that accumulates the tax charged. NULL when no tax is posted.",
        "status": "Record status (ACTIVE, INACTIVE).",
        "priority": (
            "Orders rules that match the same document and fee type. The resolver\n"
            "takes the highest; two rules sharing the top priority are an ambiguity\n"
            "error rather than an arbitrary winner. Defaults to 0."
        ),
        "description": "Administrator's note about why this rule exists.",
    },
    "journal_entries": {
        "entry_no": "Journal entry number allocated from document_sequences. Unique.",
        "entry_type": "MANUAL, or the document type that generated the entry automatically.",
        "entry_date": "Date the entry is recorded as having occurred.",
        "posting_date": "Date the entry hit the ledger; selects the accounting period.",
        "accounting_period_id": "Accounting period the entry was posted into.",
        "status": "Entry state (DRAFT, POSTED, REVERSED). Indexed because posting filters on it.",
        "description": "Narrative describing the entry.",
        "source_document_id": "Financial document that generated this entry automatically.",
        "posting_rule_id": (
            "Posting rule that resolved this entry's accounts, snapshotted at post time.\n"
            "Has no ON DELETE action: a rule that posted something may be deactivated but\n"
            "never deleted, or the attribution would be lost. NULL for a manual journal."
        ),
        "reversal_of_journal_entry_id": (
            "Entry being reversed. Set on the reversing entry and NULL on originals."
        ),
        "posted_at": "Timestamp the entry was posted to the ledger.",
        "debit_total": (
            "Sum of debit lines. Must equal credit_total before the entry may be posted — this\n"
            "is the double-entry balance check."
        ),
        "credit_total": "Sum of credit lines. Must equal debit_total before posting.",
        "data": "JSONB payload for module-specific fields not covered by dedicated columns.",
    },
    "journal_entry_lines": {
        "journal_entry_id": "Journal entry the line belongs to. CASCADE on entry deletion.",
        "account_id": (
            "General-ledger account debited or credited. Must reference a postable account."
        ),
        "party_id": "Business party the line relates to, for party-level reporting.",
        "service_order_id": "Service order the line relates to, for operational reporting.",
        "financial_document_id": "Financial document the line was generated from.",
        "description": "Narrative printed on the line.",
        "debit_amount": "Debit amount in currency_code. Zero on a pure credit line.",
        "credit_amount": "Credit amount in currency_code. Zero on a pure debit line.",
        "exchange_rate": "Rate used to convert the amounts into the base currency.",
        "base_debit_amount": "debit_amount converted to the base currency. Summed for the trial balance.",
        "base_credit_amount": "credit_amount converted to the base currency. Summed for the trial balance.",
    },
    "financial_document_postings": {
        "financial_document_id": "Document that produced the entry.",
        "journal_entry_id": "Journal entry produced by posting the document.",
        "posting_role": "Whether this is the ORIGINAL_POSTING, its REVERSAL, or an ADJUSTMENT.",
        "created_at": "Timestamp the link was created.",
    },
    # -- archive ----------------------------------------------------------
    "archive_records": {
        "entity_type": "Table name of the archived record, for example 'service_orders'.",
        "entity_id": "Primary key the archived record had in its own table.",
        "record_reference": (
            "Human-facing reference captured at archive time (for example SO-000123). Kept so\n"
            "the record is still identifiable after the source row is gone."
        ),
        "status": "Lifecycle of the archived row: ARCHIVED, RESTORED or HARD_DELETED.",
        "original_owner_user_id": (
            "Owner recorded at archive time, so ownership can be reinstated if the row is\n"
            "restored."
        ),
        "deleted_at": "Timestamp the record was archived. Indexed for retention sweeps.",
        "restored_at": "Timestamp the record was restored. NULL while it remains archived.",
        "hard_deleted_at": "Timestamp the record was permanently purged. NULL while it is recoverable.",
        "snapshot_json": (
            "JSONB copy of the row taken when it was archived. This is what makes review and\n"
            "restoration possible after the source row is gone."
        ),
    },
    # -- audit ------------------------------------------------------------
    "audit_events": {
        "actor_user_id": "User responsible for the action. NULL for system-initiated events.",
        "event_type": "Event category, for example AUTH, RBAC or POSTING.",
        "entity_type": "Table name of the affected record.",
        "entity_id": "Primary key of the affected record.",
        "action": "Action performed, for example LOGIN, UPDATE or POST.",
        "result": "SUCCESS or FAILURE.",
        "reason": "Explanation recorded for failures and permission denials.",
        "request_id": (
            "Request id from the API error envelope. Ties the event to the application logs."
        ),
        "correlation_id": "Correlation id shared by every event belonging to one logical operation.",
        "ip_address": "Client IP address the action came from.",
        "user_agent": "Client User-Agent header.",
        "before_json": "JSON snapshot of the record before the change.",
        "after_json": "JSON snapshot of the record after the change.",
        "metadata_json": "Additional structured context for the event.",
        "amount": "Monetary amount involved, recorded on financial events.",
        "occurred_at": "Timestamp the event occurred (UTC, timezone-aware).",
    },
    # -- backup -----------------------------------------------------------
    "backup_runs": {
        "trigger": "What started the run: scheduled or manual.",
        "status": "Run outcome (running, success, partial, failed). Indexed for the runs list.",
        "started_at": "Timestamp the run started.",
        "finished_at": "Timestamp the run completed. NULL while the run is still running.",
        "duration_ms": "Wall-clock runtime in milliseconds.",
        "tables_total": "Number of tables the job planned to process.",
        "tables_processed": "Tables actually finished before the run ended.",
        "rows_scanned": "Rows examined during the run.",
        "rows_inserted": "New versions written to the spreadsheet.",
        "rows_updated": "Changed rows pushed to the spreadsheet.",
        "rows_skipped": "Rows unchanged since the last backup and therefore skipped.",
        "rows_failed": "Rows that could not be backed up.",
        "spreadsheet_id": "Google Sheets spreadsheet that received the data.",
        "message": "Human-readable summary of the run outcome.",
        "detail": "JSONB payload with structured run diagnostics.",
    },
    "backup_records": {
        "run_id": "Run that produced this version. Set to NULL when the run row is deleted.",
        "table_name": "Source table the row belongs to.",
        "record_id": (
            "Primary key of the source row, stored as text because not every table uses an\n"
            "integer key."
        ),
        "backup_version": "Monotonic version number for this row, incremented on every change.",
        "backup_at": "Timestamp this version was captured.",
        "change_kind": "How the row changed relative to the previous version: insert, update or delete.",
        "row_hash": "Deterministic hash of the row contents, used to detect changes.",
        "data": "JSONB snapshot of the row exactly as it was at backup_at.",
        "synced": "TRUE once this version has been written to the spreadsheet.",
        "synced_at": "Timestamp the version was written to the spreadsheet.",
    },
    "backup_states": {
        "table_name": "Source table the row belongs to. Indexed so the run can skip whole tables.",
        "record_id": "Primary key of the source row, stored as text.",
        "row_hash": (
            "Hash of the row as last backed up. Compared against the live row to decide whether a\n"
            "new version is needed."
        ),
        "backup_version": "Version number the row had when it was last backed up.",
        "last_backup_at": "Timestamp this row was last backed up.",
    },
    "backup_logs": {
        "run_id": "Run the log line belongs to. CASCADE, so deleting a run removes its log.",
        "level": "Log severity: debug, info, warning or error.",
        "table_name": "Table being processed when the line was written.",
        "message": "Human-readable log message.",
        "detail": "JSONB payload with structured context for the line.",
        "created_at": "Timestamp the log line was written (UTC, timezone-aware).",
    },
    # -- currencies ---------------------------------------------------------
    "currencies": {
        "code": (
            "ISO 4217 alphabetic code, stored upper-case. Unique among non-archived rows, so a\n"
            "deleted currency's code can be reused."
        ),
        "name": "Human-readable currency name (e.g. 'US Dollar').",
        "symbol": "Display symbol (e.g. '$', 'KHR'). Optional; used on printed documents.",
        "numeric_code": "ISO 4217 numeric code. Optional; kept for external-system interchange.",
        "decimal_places": (
            "Number of decimal places this currency is denominated in (0-6, default 2). Used to\n"
            "round every converted base-currency amount, so a whole-unit currency such as KHR\n"
            "is not given cents it does not have."
        ),
        "description": "Free-text notes about where and how this currency is used.",
        "status": "Lifecycle state. ACTIVE currencies may be selected on new documents.",
    },
    # -- currency rates ----------------------------------------------------
    "currency_rates": {
        "from_currency_code": (
            "Currency converted away from. With to_currency_code and effective_date it is unique\n"
            "among non-archived rows."
        ),
        "to_currency_code": "Currency converted into: the row reads '1 FROM = rate TO'.",
        "effective_date": (
            "Date this rate starts applying. A document resolves the newest APPROVED row whose\n"
            "effective date is on or before the document's own date."
        ),
        "rate": (
            "How many TO units one FROM unit is worth (NUMERIC(19,8)); CHECK rate > 0. A document\n"
            "stores the inverse when it is denominated in FROM, because the ledger computes\n"
            "base = amount * exchange_rate."
        ),
        "status": (
            "PENDING while an operator enters it, APPROVED once it may be applied to documents,\n"
            "INACTIVE to retire it without deleting the row."
        ),
        "source": "Where the rate came from, for example the bank or central-bank reference.",
        "description": "Free-text note explaining the rate, kept with the row as its audit context.",
    },
    # -- configuration versions --------------------------------------------
    "configuration_versions": {
        "version_no": "Sequential version number across the installation, starting at 1.",
        "scope": (
            "Scope this version freezes. GLOBAL today; direction-specific publishing can use the\n"
            "same column without a second version table."
        ),
        "origin": "PUBLISH for a new live configuration, ROLLBACK when the snapshot copies an older version.",
        "snapshot_schema_version": (
            "Shape version of config_snapshot, so a reader can detect a snapshot written by an\n"
            "older builder."
        ),
        "content_hash": "Hash of the normalised snapshot, used to compare versions without trusting JSON key order.",
        "source_version_id": "Version a ROLLBACK copied; NULL for an ordinary publish.",
        "activated_at": "When this version was last made active. The published_* fields stay the original event.",
        "activated_by_user_id": "User who last activated this version.",
        "status": (
            "DRAFT (never published), PUBLISHED (the live configuration) or RETIRED (superseded).\n"
            "A partial unique index allows only one PUBLISHED row."
        ),
        "change_note": "Why the configuration changed; shown in the version history.",
        "config_snapshot": (
            "JSONB capture of the tabs, groups and attributes in force at publish time. Read-only\n"
            "historical reference: nothing in it is executed and every submitted value is still\n"
            "validated against the live rules."
        ),
        "published_at": "Timestamp the version became the live configuration.",
        "published_by_user_id": "User who published this version.",
    },
    # -- app settings -------------------------------------------------------
    "app_settings": {
        "setting_key": (
            "Stable identifier the settings API addresses ('app_info', 'general', 'localization',\n"
            "'email', 'telegram', 'notifications', 'security', 'system', 'backup'). Unique."
        ),
        "setting_group": (
            "Grouping used to load the whole configuration; equals setting_key for configuration\n"
            "groups and 'app' for the app-info document."
        ),
        "setting_value": (
            "JSONB payload for the group. Shape and validation live in code; the table stores\n"
            "values and never defines or executes behaviour."
        ),
        "description": "What the group configures, shown in administration tooling.",
        "updated_by_user_id": "User who last wrote this group.",
    },
}