# LCS Freight Forwarding — legacy → 47-table migration analysis

**Status:** Phase 1 deliverable (analysis only). No schema has been changed by this
document.

**Reference inputs**

| File | Role |
|---|---|
| `docs/lcs_complete_postgresql_reference.sql` | Proposed 47-table DDL (new/EMPTY database only) |
| `docs/lcs_complete_drawdb_47.sql` | DrawDB diagram of the same 47 tables |
| `docs/lcs_schema_smoke_tests.sql` | Post-load assertions (47 tables, ≥6 views, `is_active` on every table) |
| `docs/lcs_implementation_guide.md` | Author's own scoping and limitations |

**Authoritative inputs actually used for the mapping** (the reference files are
design artifacts, not migration scripts):

| Source | How it was inspected |
|---|---|
| Live PostgreSQL database | `information_schema` dump of every table/column + all 113 foreign keys |
| Current Alembic head | `a2b3c4d5e6f7` — as inspected for this analysis. Later revisions were added; the current head and the revision inventory live in `docs/15_migration_and_rollback_guide.md` §1 |
| Migration history | 18 revisions in `backend/alembic/versions/` as inspected |
| SQLAlchemy models | `backend/app/modules/*/models.py` (8 model modules) |
| Application code | `app/modules/*/{router,service,repository}.py`, `app/core/*` |
| Frontend | `frontend/app/**` (Nuxt 4 static SPA) |
| Generated schema doc | `docs/06_database_design.sql` (59 tables) |

> **Headline finding.** The current system is **not** a 59-table design that needs
> rebuilding into 47 tables. It is a *59-table design that already implements the
> majority of the 47-table design's intent*, with four genuinely missing
> capabilities (`currencies`, `currency_rates`, `app_settings`,
> `configuration_versions`), several **richer** structures than the proposal, and
> a handful of proposal tables that would **destroy working features** if
> adopted literally. The correct migration is therefore **additive**, not a
> rewrite.

---

## 1. Measured current state

Live database, `information_schema`:

- Base tables: **60** (59 application tables + `alembic_version`)
- Views: **0**
- Foreign keys: **113**
- Alembic revision: `a2b3c4d5e6f7` (= head, no pending migrations)

**Data volume in the live development database** — this matters for blast radius:

| Table | Rows |
|---|---|
| `role_permissions` | 188 |
| `permissions` | 128 |
| `audit_events` | 14 |
| `document_sequences` | 8 |
| `user_sessions` | 7 |
| `users` / `user_credentials` / `user_role_assignments` | 3 each |
| `roles`, `fee_types`, `component_*` | 1–2 each |
| `business_parties`, `places`, `component_tabs`, `container_types`, `trade_directions`, `transport_types` | 1 each |
| `module_records`, `archive_records`, `password_reset_tokens` | 1–3 |
| **all financial / operational tables** | **0** |

There are **no quotations, service orders, financial documents, journal entries,
payments or allocations** in the live dev database. This means the migrations
below can be exercised end-to-end here **without data-loss risk**, but they are
written to be correct *with* data because production may not be empty.

---

## 2. Disposition matrix

Legend:

- **KEEP** — retained as-is; target requirements already met.
- **EXTEND** — retained; additive columns/tables/object added.
- **RENAME** — physical rename with a compatibility plan.
- **MAP** — target table is an *alternative representation* of an existing
  structure; no physical change, documented equivalence instead.
- **ADD** — genuinely missing; new table created and backfilled.
- **KEEP-BEYOND-TARGET** — not in the 47-table proposal, but holds live data or
  powers a shipped feature. Explicitly **not** dropped (see §6).

### 2.1 Identity, RBAC and session

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 1 | `roles` | `roles` | KEEP | Already has `code`, `name`, `description`, `is_system_role`, `status` |
| 2 | `permissions` | `roles.permissions` JSONB | **KEEP-BEYOND-TARGET** | 128-row permission catalog. Flattening into a JSONB blob loses referential integrity and the ability to audit grants. **Do not adopt.** |
| 3 | `role_permissions` | `roles.permissions` JSONB | **KEEP-BEYOND-TARGET** | 188 grants. Same reasoning. |
| 4 | `users` | `users` | KEEP | Current has `user_code`, `locale`, `timezone`, `token_version`, `system_identity` — all used |
| 5 | `user_credentials` | `users.password_hash` | **KEEP-BEYOND-TARGET** | Splitting the credential out of `users` is a *security improvement* over the proposal (the reference guide itself warns "avoid exposing password hashes"). Also holds `failed_attempt_count`/`locked_until`. |
| 6 | `user_role_assignments` | `users.role_id` | **KEEP-BEYOND-TARGET** | Enforces one *active* role via partial unique index **and** keeps role history. `users.role_id` would lose history. |
| 7 | `user_sessions` | `user_sessions` | KEEP | Current adds `user_agent`, `remember_me` |
| 8 | `password_reset_tokens` | — | **KEEP-BEYOND-TARGET** | Live password-reset feature |
| 9 | `business_parties` | `business_parties` | KEEP | `roles` JSONB ≡ `party_roles`; `legal_name` ≡ `name`; `vat_tin` ≡ `tax_number`; adds `display_name`, `contact_person`, soft-delete |
| 10 | `places` | `places` | KEEP | `status` ≡ `place_type` carrier; adds soft-delete |

### 2.2 Master data

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 11 | — | `currencies` | **ADD** | **Real gap.** Currency is a `VARCHAR(3)` string on 9 tables; there is no currency master, no FX history |
| 12 | — | `currency_rates` | **ADD, dropped, re-added** | Added in `b3c4d5e6f7a8`, dropped as unused by `c1d2e3f4a5b7`, then re-added by `d2e3f4a5b6c8` as the approved-rate store documents actually resolve from (ISO-code pairs, effective date, PENDING/APPROVED/INACTIVE, one row per pair and date). This closes the gap this row records: a document in another currency now resolves and stores a rate |
| 13 | `container_types` | `container_types` | KEEP | Current is richer (ISO code, dimensions, max gross weight) |
| 14 | `transport_types` | `transport_types` | KEEP | |
| 15 | `transport_assets` | `transport_assets` | KEEP | Current adds `identity`, `identity_type`, `operator_party_id` |
| 16 | `fee_types` | `fee_types` | KEEP | |
| 17 | `trade_directions` | `trade_directions` | KEEP | |
| 18 | `customer_customs_accounts` | — | **KEEP-BEYOND-TARGET** | Explicit gap in the reference guide ("does not preserve all customer customs credentials"). Encrypted credential store; `customs_credential.retrieve` permission exists. |
| 19 | `module_records` | — | KEEP (legacy), **partially superseded** | Generic JSON record store; currently backs `settings` (`__app_config__`/`__app_info__`). Those two move to `app_settings`; remaining rows are legacy master-data records. |
| 20 | — | `app_settings` | **ADD** | **Real gap.** Settings live in `module_records` JSON blobs rather than a keyed settings table |
| 21 | `chart_of_accounts` | `chart_of_accounts` | KEEP | `parent_account_id` ≡ `parent_id`, `status` ≡ `is_active` |
| 22 | `financial_accounts` | `financial_accounts` | KEEP | `account_id` ≡ `ledger_account_id` (both point at `chart_of_accounts`) |
| 23 | `accounting_periods` | `accounting_periods` | KEEP | Month-granular (`period_year`,`period_month`) with unique constraint — stronger than the proposal's free-form `period_code` |
| 24 | `document_sequences` | `document_sequences` | KEEP | Same shape; created per `(document_type, period_year)` |
| 25 | `posting_rules` | `posting_rules` | KEEP | Identical semantics |

### 2.3 Quotations

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 26 | `quotations` | `quotations` | KEEP | `customer_party_id` ≡ `customer_id`; `current_revision_no` is a counter, target's `current_version_id` is a pointer |
| 27 | `quotation_revisions` | `quotation_versions` | **RENAME** | Semantics identical: `revision_no` ≡ `version_no`, `status` set is a superset |
| 28 | `quotation_revision_lines` | `quotation_lines` | **RENAME** | Current has discount/tax split columns instead of the proposal's single `amount`; **richer, keep the current shape** |
| 29 | `quotation_revision_places` | — | **KEEP-BEYOND-TARGET** | Multi-leg route per revision. Explicit gap ("full multi-leg itinerary documents"). Proposal keeps only `origin_place_id`/`destination_place_id` on the version header — a **data-loss** trade. |
| 30 | `quotation_revision_containers` | — | **KEEP-BEYOND-TARGET** | Explicit gap ("quotation container requirements"). Referenced by `service_order_container_requirements.source_quotation_container_id`. |
| 31 | `quotation_conversions` | — | **KEEP-BEYOND-TARGET** | The proposal relies on `service_orders.quotation_version_id`. Keeping conversions preserves the **duplicate-conversion guard** (unique on both `revision_id` and `service_order_id`) and the `idempotency_key`. |

### 2.4 Operations (service orders)

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 32 | `service_orders` | `service_orders` | EXTEND | Add `configuration_version_id` |
| 33 | `service_order_places` | — | **KEEP-BEYOND-TARGET** | Multi-leg route + `is_actual` + `free_text`. Proposal replaces with two header FKs — **data-loss**. |
| 34 | `service_order_container_requirements` | — | **KEEP-BEYOND-TARGET** | Planned vs actual containers. Referenced by actual containers. |
| 35 | `service_order_containers` | `service_order_containers` | KEEP | Current adds `container_requirement_id`, weights, pickup/return dates, `data` JSON |
| 36 | `service_order_pricing` | — | **KEEP-BEYOND-TARGET** | Pricing **header** (subtotal/discount/tax/total/currency) per order. Proposal folds the header away and attaches lines directly to the order — would lose the order-level totals row. |
| 37 | `service_order_pricing_lines` | `service_order_pricing_lines` | KEEP | Current hangs off the pricing header rather than the order; semantically equivalent via the 1:1 header |
| 38 | `service_order_charges` | `service_order_charges` | **KEEP-BEYOND-TARGET** | Document-style charge header (number, date, status, totals) driving the finance invoice pipeline |
| 39 | `service_order_charge_lines` | `service_order_charges` (flat, `charge_type`) | **KEEP-BEYOND-TARGET** | Proposal flattens header+lines into one table with `charge_type='REVENUE'|'COST'`. Flattening would break `issue_charge` → `create_invoice_from_charge` and the `charge_no` sequence. |
| 40 | `service_order_movements` | `service_order_movements` | KEEP + **wire up** | Table and model exist; **no service/router/API**. Phase-required capability ("manage movements") is missing. |
| 41 | `service_order_milestones` | `service_order_milestones` | KEEP + **wire up** | Same as above |
| 42 | `service_order_component_rows` | `service_order_component_rows` | EXTEND | Add `config_version_id`; `values` JSONB ≡ `field_values` |
| 43 | `component_attributes` | `component_attributes` | KEEP | `status` ≡ `is_active`; adds `default_value`, `placeholder`, `width` |
| 44 | `component_groups` | `component_groups` | KEEP | Adds `display_order`, `is_archived` |
| 45 | `component_tabs` | `component_tabs` | EXTEND | Add `config_version_id`; already has `trade_direction_id` (the dynamic-tab driver) |
| 46 | `component_group_attributes` | `component_group_attributes` | KEEP | `is_required` ≡ `required_override` |
| 47 | `component_tab_groups` | `component_tab_groups` | KEEP | |
| 48 | — | `configuration_versions` | **ADD** | **Real gap.** No published-config snapshots; historical orders cannot be pinned to the config they were captured under |

### 2.5 Finance

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 49 | `financial_documents` | `financial_documents` | KEEP | Superset: adds `posting_date`, `exchange_rate`, `paid_amount`, `posted_*`, `reversed_document_id`, `data` |
| 50 | `financial_document_lines` | `financial_document_lines` | KEEP | Adds tax/discount split, container link, `account_id` override |
| 51 | — | `payments` | **MAP** | Payments are already `financial_documents` with `document_type ∈ {CUSTOMER_RECEIPT, SUPPLIER_PAYMENT}`. Creating a parallel `payments` table would **duplicate the cash ledger** and break the working posting engine. Documented equivalence; no physical change. |
| 52 | `financial_document_allocations` | `payment_allocations` | **MAP** | Same relationship (`payment_document_id` ≡ `payment_id`, `target_document_id` ≡ `financial_document_id`). Current also stores `allocated_currency_code`, `exchange_rate` and an `idempotency_key` — the reference guide lists FX allocation as an *unresolved* limitation. **Richer; keep.** |
| 53 | `journal_entries` | `journal_entries` | KEEP | `entry_no` ≡ `journal_no`, `accounting_period_id` ≡ `period_id`, `source_document_id` ≡ `document_id`. Adds `entry_type`, `reversal_of_journal_entry_id`, `posted_*`, debit/credit totals |
| 54 | `journal_entry_lines` | `journal_entry_lines` | KEEP | `debit_amount`/`credit_amount` ≡ `debit`/`credit`. Current **also** stores `currency_code`, `exchange_rate`, `base_debit_amount`, `base_credit_amount` — the proposal's own guide lists missing base-currency amounts as a critical gap. **Richer; keep.** |
| 55 | `financial_document_postings` | `journal_entries.document_id` | **KEEP-BEYOND-TARGET** | Duplicate-posting guard + `posting_role`. Folding into the journal FK loses the explicit 1:1 posting record. |
| 56 | `financial_document_sources` | — | **KEEP-BEYOND-TARGET** | Idempotency for invoice generation (`SERVICE_ORDER`, `SERVICE_ORDER_CHARGE`) |

### 2.6 Platform, audit, archive, backup

| # | Current table | Target | Disposition | Notes |
|---|---|---|---|---|
| 57 | `audit_events` | `audit_events` | KEEP + harden | Proposal adds an append-only trigger — **adopt** |
| 58 | `archive_records` | `archive_records` | KEEP | Current tracks restore + hard-delete actors/timestamps |
| 59 | `attachments` | `attachments` | KEEP | Current adds `storage_provider`, `uploaded_at`, `is_deleted` |
| 60 | `attachment_links` | `attachment_links` | KEEP | |
| 61 | `backup_runs` | `backup_runs` | KEEP | Current is richer (row counters, scan stats, `trigger`) |
| 62 | `backup_states` | `backup_states` | KEEP | |
| 63 | `backup_records` | `backup_records` | KEEP | |
| 64 | `backup_logs` | — | **KEEP-BEYOND-TARGET** | Per-run log lines (explicit gap: "granular original backup logs") |

**Tally**

| Disposition | Count |
|---|---|
| KEEP / EXTEND | 34 |
| MAP (documented equivalence, no physical change) | 3 |
| KEEP-BEYOND-TARGET (retained deliberately) | 20 |
| RENAME | 2 |
| ADD (new) | 4 |
| **Physical tables dropped** | **0** |

---

## 3. Column mappings for renamed / merged structures

### 3.1 `quotation_revisions` → `quotation_versions`

| Target column | Current source | Transformation |
|---|---|---|
| `id` | `id` | direct — **IDs preserved** |
| `quotation_id` | `quotation_id` | direct |
| `version_no` | `revision_no` | direct |
| `currency_id` | `currency_code` | resolve/create `currencies.code`, store FK; keep `currency_code` for compatibility |
| `trade_direction_id` | *(from `quotations.trade_direction_id`)* | denormalise on write |
| `quotation_date` | `quotation_date` | direct |
| `valid_until` | `valid_until` | direct |
| `status` | `status` | direct (superset set kept) |
| `notes` | `notes` / `description` | direct |
| `change_note` | *(new)* | backfilled with an explanatory string |
| `created_by` | `created_by_user_id` | direct |
| `approved_by` / `approved_at` | *(from `accepted_at`)* | `approved_at = accepted_at`, `approved_by = created_by_user_id` when absent |
| `is_active` | *(new)* | `TRUE`; derived from soft-delete where present |
| `created_at` / `updated_at` | same | **preserved verbatim** |

`quotation_revision_places` and `quotation_revision_containers` are **not**
collapsed into `origin_place_id`/`destination_place_id` — they carry multi-leg
data the proposal would drop.

### 3.2 `quotation_revision_lines` → `quotation_lines`

| Target column | Current source | Transformation |
|---|---|---|
| `id` | `id` | direct — IDs preserved |
| `quotation_version_id` | `quotation_revision_id` | rename only |
| `fee_type_id` | `fee_type_id` | direct |
| `description` | `service_description` | rename only |
| `quantity` | `quantity` | direct |
| `unit_price` | `unit_price` | direct |
| `amount` | `line_total` | direct |
| `sort_order` | `line_no` | direct |
| `is_active` | *(new)* | `TRUE` |

The proposal's `CHECK (amount = ROUND(quantity * unit_price, 4))` is **rejected**
as a constraint: the current model applies a line-level discount and tax
(`line_subtotal − line_discount + line_tax = line_total`), so the identity does
not hold. The current line values are authoritative and must not be recomputed.

### 3.3 `service_order_charge_lines` → flat `service_order_charges`

**Not migrated.** The equivalence is `charge_type='REVENUE'` ⟺
`service_order_charges.document_type='SERVICE_NOTE'`. Flattening would need to
re-derive `charge_no`, `document_type`, `document_date` and status per line and
would invalidate `financial_document_sources(source_type='SERVICE_ORDER_CHARGE', source_id=charge.id)`.

### 3.4 `payments` / `payment_allocations`

| Target | Current equivalent | Rule |
|---|---|---|
| `payments.id` | `financial_documents.id` where `document_type IN ('CUSTOMER_RECEIPT','SUPPLIER_PAYMENT')` | read-only compatibility view |
| `payments.payment_no` | `financial_documents.document_no` | |
| `payments.payment_direction` | derived: `CUSTOMER_RECEIPT` → `IN`, `SUPPLIER_PAYMENT` → `OUT` | |
| `payments.payment_date` | `financial_documents.document_date` | |
| `payments.financial_account_id` | `financial_documents.financial_account_id` | already present |
| `payments.amount` | `financial_documents.total_amount` | |
| `payment_allocations.payment_id` | `financial_document_allocations.payment_document_id` | |
| `payment_allocations.financial_document_id` | `financial_document_allocations.target_document_id` | |
| `payment_allocations.allocated_amount` | `financial_document_allocations.allocated_amount` | |

Compatibility views `vw_payments` / `vw_payment_allocations` are created so
reporting can be written against either naming.

---

## 4. Data transformation requirements

| # | Transformation | Direction | Notes |
|---|---|---|---|
| T1 | Discover every distinct currency string across `financial_documents`, `financial_accounts`, `journal_entry_lines`, `quotations`→revisions, `service_orders`, `service_order_pricing`, `service_order_charges`, `service_order_pricing_lines`, `settings.localization.summaryCurrency`, and seed `currencies` | backfill | Include the 9 ISO defaults from `core/localization.SUPPORTED_CURRENCIES` so every existing code resolves |
| T2 | Snapshot the live dynamic-tab configuration into `configuration_versions` v1 (`PUBLISHED`) and stamp `component_tabs`, `service_order_component_rows`, `service_orders` | backfill | Publishes a reproducible baseline; nothing is recomputed |
| T3 | Move `module_records('__app_config__'|'__app_info__')` payloads into `app_settings` rows, one per setting group | backfill | Existing JSON payloads preserved byte-for-byte inside `setting_value` |
| T4 | Create the 6 reporting views + 2 payment-compat views | additive | No data change |
| T5 | Install integrity triggers | additive | See §5 |

All five are **idempotent** and safe to re-run.

---

## 5. Integrity hardening (adopt from the proposal)

The proposal encodes several invariants in the database that the application
currently enforces only in Python. Those are worth adopting because they protect
against privileged/direct writes. Assessment per trigger:

| Proposal trigger | Verdict | Reason |
|---|---|---|
| `fn_guard_journal_entry` (posted journals immutable) | **ADOPT** | Verified: no code path updates or deletes a POSTED journal. `post_journal` only performs DRAFT→POSTED. |
| `fn_guard_journal_line` (no line edits on posted journals) | **ADOPT** | Verified: lines are written only while the entry is DRAFT. |
| `fn_validate_journal_post` (balanced, open period, date inside period) | **ADOPT** | Mirrors `post_journal`/`post_document`; defence in depth. Must not block the DRAFT→POSTED transition. |
| `fn_audit_append_only` | **ADOPT** | Verified: `audit_events` is insert/select only; the hard-delete path explicitly skips it. |
| `fn_guard_payment_allocation` — over-allocation guard | **ADOPT (INSERT/UPDATE only)** | The proposal forbids DELETE, but `reverse_document` legitimately deletes allocations as part of the reversal workflow (tested behaviour). Guarding only INSERT/UPDATE keeps the invariant without regressing reversal. |
| `fn_guard_payment_allocation` — "allocations are immutable, use a reversing record" | **REJECT** | Contradicts shipped, tested reversal behaviour. Changing it would be a functional regression, not a hardening. |
| `fn_guard_quotation_line` / `fn_guard_quotation_version` | **ADOPT in application layer** | Implemented in the service layer where the richer current status set (`SENT/ACCEPTED/CONVERTED/…`) is understood. A DB trigger hard-coding `'DRAFT'` would fight the existing lifecycle. |
| `fn_touch_updated_at` | **ADOPT** | Harmless; keeps `updated_at` correct for raw SQL writes. |
| `uq_configuration_version_published` (one PUBLISHED config) | **ADOPT** | Required by the versioning design. |
| Proposal `CHECK (quantity > 0)` on `quotation_lines` | **REJECT** | Current lines may legitimately carry `quantity`/`amount` of 0 for informational lines; adding the check could reject historical rows. |

---

## 6. Data-loss risks (explicit)

Adopting the 47-table DDL **literally** would cause the following losses. Each is
avoided by the additive plan.

| Risk | Cause | Mitigation |
|---|---|---|
| **R1** Loss of 188 role→permission grants and the 128-entry catalog | `permissions` + `role_permissions` → `roles.permissions` JSONB | Keep relational RBAC; expose `permissions` JSONB as a read-only projection if required |
| **R2** Loss of role-assignment history and the one-active-role guarantee | `user_role_assignments` → `users.role_id` | Keep the table |
| **R3** Multi-leg quotation routes lost | `quotation_revision_places` dropped | Keep the table |
| **R4** Quotation container requirements lost (and the `service_order_container_requirements.source_quotation_container_id` FK orphaned) | `quotation_revision_containers` dropped | Keep the table |
| **R5** Duplicate-conversion guard lost | `quotation_conversions` dropped | Keep the table |
| **R6** Service-order multi-leg places + planned-vs-actual containers lost | `service_order_places`, `service_order_container_requirements` dropped | Keep the tables |
| **R7** Order-level pricing totals lost | `service_order_pricing` header dropped | Keep the header |
| **R8** Charge document numbers / status / invoice-source links lost | flat `service_order_charges` | Keep header+lines |
| **R9** Cash sub-ledger duplicated or broken | new `payments` table beside `financial_documents` | Documented equivalence + compatibility views; no new table |
| **R10** Historical FX spread on allocations lost | `payment_allocations` without FX columns | Keep `financial_document_allocations` |
| **R11** Base-currency journal amounts lost | `journal_entry_lines` without base amounts | Keep current columns |
| **R12** Backup run telemetry and granular logs lost | `backup_logs` dropped | Keep the table |
| **R13** Customer customs credentials lost | `customer_customs_accounts` dropped | Keep the table |
| **R14** Document numbering collisions | `document_sequences` recreated with a different key | Keep the existing `(document_type, period_year)` unique constraint and `last_value` counters |
| **R15** Financial rounding drift | Proposal's `CHECK (amount = ROUND(quantity*unit_price,4))` and `NUMERIC(19,4)` recomputation | Never recompute historical amounts; no such constraint added |

**Irreversible operations identified:** none are required by this plan. Every
migration is additive or a rename. No table is dropped, no column is dropped, no
type is narrowed.

---

## 7. Required application changes

| Area | Change | Phase |
|---|---|---|
| `currencies` | new model + master-data CRUD at `/api/v1/currencies`, with `decimal_places` as the currency's own precision. The `/api/v1/currency-rates` companion was removed by `c1d2e3f4a5b7` and re-added by `d2e3f4a5b6c8` as the `currencyRates` rate store a document resolves from | 3, 5 |
| `app_settings` | new model; `settings` service switches storage with read-through fallback to `module_records` | 3, 4 |
| `configuration_versions` | new model; publish/preview/retire service + endpoints; stamp tabs, rows, orders; attribute-code rename guard | 4, 5 |
| Movements / milestones | service + router + permissions + validation for the two existing but unwired tables | 5 |
| Quotations | `SELECT … FOR UPDATE` on the quotation row when allocating the next revision; version-compare endpoint; immutable issued revisions; `rejected_at` handling | 6 |
| Finance | DB-level journal/allocation guards; posting-rule completeness check; reporting views | 7 |
| Reports | Service Order register/status, container register/status, trial balance, P&L, balance sheet, cash flow on top of the new views | 8 |
| Security | permission codes for every new endpoint; audit events on config publish and revision creation | 9, 10 |
| Frontend | register new endpoint constants + collections; keep `test_frontend_api_contract.py` green | 5, 11 |
| Docs | regenerate `docs/06b_database_design_annotated.sql`; migration + rollback guide | 13, 17 |

---

## 8. Rollback strategy

Because every migration is additive:

1. **Per-revision downgrade.** Each Alembic revision implements a real
   `downgrade()` that reverses only its own additive steps (drop the new table /
   column / view / trigger). Existing rows and IDs are untouched by both
   directions.
2. **Trigger/route isolation.** The integrity triggers are PostgreSQL-only and
   guarded by `bind.dialect.name`, so SQLite (the test database) is unaffected.
   Dropping a trigger restores the previous behaviour exactly.
3. **No destructive downgrade.** No `downgrade()` drops a pre-existing table,
   column or row. `downgrade()` never deletes business data.
4. **Forward-only backfills.** `app_settings` and `currencies` backfills copy
   data; `module_records` rows and the `VARCHAR(3)` currency columns are left in
   place, so downgrading loses nothing.
5. **Point-in-time restore.** Before any production run:
   `pg_dump -Fc` a base backup plus WAL archiving; rehearse restore into a
   staging database and run `docs/lcs_schema_smoke_tests.sql` plus
   `uv run pytest` against it.
6. **Cutover gate.** Application code must be deployable *before* its migration
   (read-through fallbacks) so a rollback of the app alone is always possible.

---

## 9. Verification plan

| Check | Command / artifact |
|---|---|
| Schema loads, 47-table smoke assertions | `psql -f docs/lcs_schema_smoke_tests.sql` against a disposable DB |
| FK integrity, 0 orphans | `information_schema` + `pg_constraint` query in §10 |
| Row-count reconciliation | pre/post counts in `docs/15_migration_and_rollback_guide.md` |
| Financial reconciliation | trial balance `SUM(debit) = SUM(credit)` post-migration |
| Revision numbering race | concurrency test in `backend/tests/` |
| Contract test | `uv run python -m pytest tests/test_frontend_api_contract.py -q` |
| Full suite | `uv run python -m pytest -q` |

---

## 10. Standing integrity queries

```sql
-- Every FK must resolve (0 rows expected).
SELECT tc.table_name, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    WHERE c.conname = tc.constraint_name AND c.convalidated
  );

-- Trial balance must net to zero.
SELECT SUM(debit_amount) - SUM(credit_amount) AS imbalance
FROM journal_entry_lines l
JOIN journal_entries j ON j.id = l.journal_entry_id
WHERE j.status = 'POSTED';

-- Duplicate revision numbers must not exist.
SELECT quotation_id, revision_no, COUNT(*)
FROM quotation_revisions GROUP BY 1, 2 HAVING COUNT(*) > 1;

-- Orphaned service orders (no customer).
SELECT COUNT(*) FROM service_orders so
LEFT JOIN business_parties bp ON bp.id = so.customer_party_id
WHERE bp.id IS NULL;
```
