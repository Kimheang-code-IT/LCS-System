# Repository analysis — verified implementation status

**Purpose.** State what this repository actually implements, with evidence, so that
later work starts from fact rather than from a document's claim. A table, a model,
a route, or a doc section is not evidence that a feature works; each classification
below is backed by a traced code path and, where it exists, a passing test.

**Method.** Static inspection of every backend module and frontend page, the live
PostgreSQL schema (`information_schema`, not the migration files), the Alembic
chain, the test suites, and the infrastructure configuration. Behaviour claims were
confirmed by reading the service path end to end and by running the suites.

**Companion documents.**
`docs/14` (schema gap analysis and old→new mapping), `docs/15` (apply/rollback
procedure), `docs/16` (upgrade summary and outstanding risks),
`docs/18` (per-feature checklist and remaining work).

---

## 1. Inventory

### Backend — 12 modules, 11 routers

| Module | Responsibility |
|---|---|
| `auth` | Users, roles, permissions, credentials, sessions, single-role assignment |
| `master_data` | Reference data, currencies and FX rates, dynamic component configuration, configuration versions |
| `quotations` | Quotations, revisions, pricing lines, containers, places, conversion |
| `operations` | Service orders, containers, movements, milestones, charges, attachments |
| `finance` | Chart of accounts, financial accounts, periods, sequences, posting rules, financial documents, journals |
| `status` | Shared record-status policy: which transitions are legal, who may run one, and the audit trail for a plain status write (owns no tables) |
| `reports` | Dashboard and report read models |
| `settings` | App info/config, localization, global search, data reset |
| `backup` | Google Sheets replication and its in-process scheduler |
| `audit` | Append-only audit event log |
| `archive` | Soft-delete tombstones, restore, hard delete |
| `setup` | First-run provisioning (invoked through `auth` routes) |

Cross-cutting: `app/core/` — permissions catalog, security, sequences,
localization, storage, cache, pagination, exceptions, database/session.

### Frontend — 73 pages, 49 specs

Master data (9 collections), service orders, service charges, quotations, finance
documents, journals, chart of accounts, financial accounts, accounting periods,
configuration (attributes, groups, tabs, versions), administration (users, roles,
document sequences, system settings, audit logs, archive), reports, print, auth
(login, setup, forget/reset password, verify code), dashboard.

### Database

63 application tables (plus `alembic_version`), 8 reporting views, 122 foreign
keys, 22 Alembic revisions at a single head. PostgreSQL guard triggers enforce the
financial invariants; see §5.

### Tests

26 backend test modules (220+ tests, in-memory SQLite) plus two SQL verification
scripts (`tests/sql/integrity_guards.sql`, `tests/sql/pre_migration_counts.sql`).
49 frontend Vitest specs, pure-function only. CI runs both gate sets plus a Docker
build check.

### Infrastructure

`infrastructure/docker-compose.yml` (frontend nginx, backend, PostgreSQL, Redis,
MinIO), `deploy/compose.yml` for the runtime host, `.github/workflows/dev-ci.yml`
and `production.yml`, `docs/12` for the operational procedure.

---

## 2. Feature classification

Legend: **✅ T** implemented and tested · **⚠️ V** implemented but not verified ·
**🟡 P** partially implemented · **❌ M** missing · **⛔ D** deprecated/obsolete.

| # | Feature | Status | Evidence / what is missing |
|---|---|---|---|
| 1 | Master data management | ✅ T | 9 `Spec`s in `master_data/service.py` + 8 generic collections; `tests/test_api_completeness.py`, `test_sorting.py` |
| 2 | User management | ✅ T | `auth/service.py`, `/users` CRUD; `tests/test_auth_rbac.py`, `test_create_admin.py` |
| 3 | Role-based access control | ✅ T | `core/permissions.py` catalog, synced on startup; `tests/test_role_permissions.py` |
| 4 | One active role per user | ✅ T | Partial unique index on `user_role_assignments(expires_at IS NULL)`; `tests/test_role_permissions.py` |
| 5 | Quotation version management | ✅ T | `quotations/service.py`; `tests/test_quotation_versions.py` (compare, reject, immutability, conversion) |
| 6 | Service orders | ✅ T | `operations/service.py`; `tests/test_workflows.py` |
| 7 | Dynamic tabs by trade direction | ✅ T | `component_tabs.bootstrap` filtered by `trade_direction_id`; `tests/test_config_versions.py`, `test_workflows.py` |
| 8 | Dynamic UI configuration | ✅ T | Attributes/groups/tabs CRUD + publish/preview/retire; `tests/test_config_versions.py` |
| 9 | Containers and transport operations | 🟡 P | Containers ✅ T (`test_workflows.py`). Movements and milestones ✅ T (`test_movements_and_milestones.py`) **but have no UI** |
| 10 | Service charges | ✅ T | `operations/service.py` charge lifecycle + auto invoice draft; `tests/test_finance_automation.py` |
| 11 | Financial documents | ✅ T | `finance/service.py`. One module covers all ten document types and is driven by the type: payment method, financial account and value date are read and stored only for a receipt or payment, a due date only for an invoice or bill (`_document_columns`), an unknown type is rejected on create, and a document keeps the type it was created with because its number came from that type's sequence. The payload carries what the tabs render — `date`, `customer`, `jobNo`, `outstanding`, `vat`, `paymentMethod`, `financialAccount`, `valueDate`, `remark`, the posted journal (`journalId`/`journalEntries`) and the allocations from both sides of the link — instead of relying on the echoed request body. A line's `accountCode` is derived through `AccountingPostingService.detail_account_code`, the same resolution posting uses; the column is read-only and the derived value is stripped from the save payload, so the rule in force at posting time decides. `tests/test_finance_automation.py`, `tests/test_financial_documents_module.py` (10 cases) |
| 11.1 | Multi-currency and exchange rates | ✅ T | One base currency per installation (the localization `currency` setting), a stored rate on every document, and one conversion implementation (`core/fx.py`). `currencies.decimal_places` gives each currency its precision; `currency_rates` holds APPROVED rates versioned by effective date and is resolved, in either direction, by `master_data/currency_rates.py`. A document in the base currency always stores rate 1, another currency must resolve an approved rate or take the operator's, and missing/zero/negative/non-finite rates are refused at the API boundary. The four `base_*_amount` columns are re-derived when the document posts, and `allocate_payment` reports the exchange difference between the two sides' valuations. `tests/test_multi_currency.py` (17 cases), `frontend/tests/multi-currency.spec.ts` (13) |
| 12 | Payments and payment allocations | ✅ T | Modelled as `financial_documents` of payment type + `financial_document_allocations`; `tests/test_finance_automation.py` |
| 13 | Double-entry accounting | ✅ T | Posting engine + 6 PostgreSQL guards; `tests/sql/integrity_guards.sql` (16/16 on PostgreSQL) and a live-stack smoke test that posts, reverses and re-balances against the running container |
| 14 | Automatic posting rules | ✅ T | `PostingRuleResolver` (`finance/posting_rules.py`) selects by document type, fee type and priority, with the partial unique index making one active rule per scope *and* priority a database guarantee; `AccountingPostingService` (`finance/posting.py`) builds a balanced `JournalDraft` from a per-document-type strategy table covering invoices, supplier bills, payments and credit notes. Management UI at `/finance/posting-rules` under `finance.posting_rules.view` / `posting_rule.manage`, with per-field validation, audit on create/update/delete and a delete guard protecting referenced or active rules. History: a read-only History tab on each rule (change diff + the journals it posted) and a `/finance/posting-rules/history` list of every change, both served from `audit_events` and `journal_entries.posting_rule_id` rather than a second copy of the data. `tests/test_posting_rules.py` (46 cases: selection, posting, validation, reversals, concurrency, history, usage) |
| 15 | Financial reports | ✅ T | AR/AP/profitability/ledger plus server-side trial balance, P&L, balance sheet and cash flow, reconciled in `tests/test_reporting_values.py`. The frontend still derives its own statements from `ledger-lines` and should be pointed at the new endpoints |
| 16 | Operational reports | ✅ T | Order count by status, quotation performance, and the container register with a status breakdown (`GET /api/v1/reports/container-register`) |
| 17 | Audit logs | ✅ T | Append-only `audit_events` + PostgreSQL append-only trigger. The list now carries `eventType` and `entityType`, so the screen says *what* changed and not only that something did; `tests/test_archive.py`, `test_auth_rbac.py`, `test_posting_rules.py` |
| 18 | Authentication and credentials | ✅ T | JWT access + rotating refresh, Argon2id hashing, lockout, one active role, protected system administrator. An administrator can set another account's password (`POST /users/{id}/password`, `user.manage`) — the only recovery path when a user cannot receive the reset email — and the resulting temporary password is refused everywhere except the change screen until its owner replaces it. **No screen can reveal an existing password**: only a digest is stored, and that is a deliberate limit rather than a missing feature. `tests/test_password_reset.py` (15 cases) |
| 18 | Archive management | ✅ T | Soft delete → tombstone → restore → guarded hard delete; `tests/test_archive.py` |
| 19 | File attachments | ✅ T | Presign, upload, list, download, content-signature validation, and a permission-gated soft delete that unlinks and stops serving the file; `tests/test_attachments.py`, `test_upload_policy.py` |
| 20 | Document sequences | ✅ T | `core/sequences.py` with a row lock; `tests/test_workflows.py`, frontend `sequence-allocation.spec.ts` |
| 21 | Backup and recovery | 🟡 P | Google Sheets replication ✅ T (`tests/test_backup.py`). Off-host PostgreSQL base backup + WAL archiving is a **documented operational requirement, not implemented in code** |
| 22 | Record activation and controlled deletion | ✅ T | Master data (`REFERENCE_ACTIVE` + archive) and finance (accounts, financial accounts, posting rules) both refuse to delete an active or still-referenced record, through the shared policy in `app/core/deletion.py`; `tests/test_deletion_policy.py` |
| 23 | Consistent inline form validation | ✅ T | One shared pipeline (`utils/validation/`, `useFormValidation`, `AppFormErrorSummary`, `data-field-key` + focus) covers document forms, repeatable tables, database-driven Service Order tabs and configuration dialogs. 139 assertions across 10 specs. Computed line-table cells carry the focus target but cannot show a message (they are not editable) |
| 24 | Success-only toast notifications | ✅ T | Validation errors and business-rule refusals are never toasts: they land on the field, or in a persistent form/page-level summary. `useApi` suppresses its own toast for 400/409/422, which the owning form renders. `validation-notification-policy.spec.ts` scans every toast call in `app/` so the rule cannot regress |
| 25 | Production deployment and monitoring | 🟡 P | Compose, CI/CD, runbook, rollback procedure ✅ V. **No monitoring, alerting, or health-dashboard implementation** |
| 26 | Google Sheets backup scheduler | ✅ T | In-process asyncio scheduler; `tests/test_backup.py` |
| 27 | Global search | ✅ T | Permission-gated across orders, quotations, documents, journals, parties; `tests/test_sorting.py` |
| 28 | First-run setup | ✅ T | `/auth/setup` gated on no users; `tests/test_setup.py` |
| 29 | Multi-language UI (en/km/zh) | ✅ T | 2919 keys × 3 locales, parity enforced; `tests/i18n-locales.spec.ts` |
| 30 | Bilingual print output | ✅ T | English + Khmer tax invoice/debit note; `tests/print-model.spec.ts` |
| 31 | Rate limiting | ✅ T | `tests/test_rate_limit.py` |
| 32 | Redis caching | ✅ T | Namespaced read-through with invalidation; `tests/test_redis_integration.py` |
| 33 | Record status management | ✅ T | One code-defined transition policy (`app/modules/status/policy.py`) served by `GET /{collection}/status-policy` and applied by `POST /{collection}/{id}/status`; status is no longer an editable form field, every change is audited with both statuses, and workflow transitions (posting, reversal, issuing, period close, quotations) stay on their own endpoints — the shared endpoint refuses them with `TRANSITION_REQUIRES_COMMAND`. `tests/test_record_status.py` (18 cases), `frontend/tests/record-status.spec.ts` (7) |

### Obsolete / superseded (⛔)

| Item | Why |
|---|---|
| `app/utils/freight/job-task-fields.ts` + `job-component-line-table.ts` | Genuinely dead: the second imports the first, nothing imports either. Belong to the pre-`component_tabs` template model |
| `ModuleRecord` generic collections | Superseded by real tables for `currencies`; still the storage for `companies`, `shipments`, `customs`, `documents`, `deliveries` |
| `Spec.before_delete` / `Spec.after_create` hooks | Declared in `master_data/service.py` but never assigned and `before_delete` is never called |
| `config_versions.STATUSES` | Unused constant; statuses are written as literals |
| Dashboard status names `OPEN`/`IN_PROGRESS`/`ON_HOLD`/`COMPLETED` | Predate the 3-state order lifecycle; **fixed** in this pass (§6) |

---

## 3. Documentation gap analysis

| Document | State | Action taken / needed |
|---|---|---|
| `01_business_requirements.md` | Current | none |
| `02_software_requirements_specification.md` | Current | none |
| `03_business_process_and_sop.md` | Current | none |
| `04_functional_design.md` | Current | none |
| `05_solution_architecture.md` | Table count corrected to 63 with a pointer to the mapping doc | updated |
| `06_database_design.sql` | **Generated**; was drifting with no generator | generator added, file regenerated |
| `06b_database_design_annotated.sql` | **Generated**; had been overwritten with the reference DDL | restored from the models |
| `07_entity_relationship_diagram.mmd` | Not verified against the 63-table schema | refresh needed |
| `08_data_flow_diagrams.mmd`, `09_process_flow_diagrams.mmd` | Not verified | refresh needed |
| `10_*` | **Missing entirely** — the numbering skips from 09 to 11 | either renumber or add the intended topic |
| `11_permissions_matrix.md` | Updated with `service_order_config.publish` | updated |
| `12_deployment_runbook.md` | Updated with the additive-migration pointer | updated |
| `13_security_hardening_runbook.md` | Present; not verified against current controls | review |
| `14_47_table_migration_analysis.md` | New: gap analysis and mapping | added |
| `15_migration_and_rollback_guide.md` | New: apply, verify, rollback, restore | added |
| `16_upgrade_summary_and_risks.md` | New: decisions, removed code, risks | added |
| `17_repository_analysis.md` | This document | added |
| `18_implementation_checklist.md` | New: per-feature status and remaining work | added |
| `LCS_API.postman_collection.json` | Does not include the endpoints added recently | regenerate from `/openapi.json` |
| `README.md` | Accurate for setup and operation | none |
| Testing strategy | **No standalone document**; strategy lives in `AGENTS.md` and the `testing-qa` skill | consider a short `docs/19_testing_strategy.md` |

### Documented-vs-actual contradictions found and resolved

| Claim in docs | Actual code | Resolution |
|---|---|---|
| "59 tables" | 63 tables in the current schema (`docs/06_database_design.sql`) | `docs/05` corrected |
| Dashboard reports open/in-progress/on-hold/awaiting-closure orders | Those statuses are never written; all four counters were 0 | fixed in code + regression test (§6) |
| `docs/06b` mirrored the models | It contained the unrelated 47-table reference DDL | restored |
| `docs/05` documents `UFormField :error` as the source of a field's invalid state | Every field on the Service Order Overview (and every dynamic component tab) rendered **permanently invalid** — red ring and `aria-invalid="true"` on clean fields, with no message. The renderers fell back to `error: ''`; `UFormField.error` is `[Boolean, String]` and Vue casts an empty string to `true` | fixed in code: "no error" is normalised to `undefined` through `app/utils/validation/form-field-error.ts`; guarded by `tests/form-field-error.spec.ts` (unit cases + a static scan that no `:error` binding falls back to `''`). Verified in a browser against the running stack: clean Overview fields compute `box-shadow: none`, `aria-invalid="false"`, and a real error still renders the ring plus the inline message |

### Contradictions still open

| Claim | Actual | Owner |
|---|---|---|
| The report catalogue implies server-side financial statements | Trial balance, P&L, balance sheet, cash flow and the container register are now served server-side and reconciled in tests. `ReportsView.vue` still derives its own statements from `ledger-lines` and has not been pointed at the new endpoints | frontend work, see `docs/18` |
| App config exposes `security.maintenanceMode` and `readOnlyMode` | The backend never reads them, so turning maintenance mode on has no effect | config work, see `docs/18` |

---

## 4. Hardcoded configuration register

For each item: is a **database row** able to override it at runtime? `DB` = yes,
with the table named; `CODE` = no override exists.

### Genuinely database-driven (a row wins)

| Constant | Overriding row | Note |
|---|---|---|
| `DEFAULT_ACCOUNTS` (finance) | `posting_rules` (+ `chart_of_accounts`) | Only a last-resort fallback; `PostingRuleResolver` queries rules first, takes the highest priority in the most specific matching tier, and raises `AMBIGUOUS_POSTING_RULE` on a priority tie. The resolved `PostingRuleAccounts.source` records which path was taken (`EXACT`, `DOCUMENT_DEFAULT`, `LEGACY_DEFAULT`) |
| `DEFAULT_PREFIXES` (sequences) | `document_sequences` | Editable via `/document-sequences`; re-seeded each year if a row is missing |
| `DEFAULT_LOCALIZATION` | `app_settings(localization)` | Selection constrained by code allow-lists |
| `DEFAULT_APP_INFO`, `DEFAULT_APP_CONFIG` (per group) | `app_settings(app_info, general, …)` | Deep-merged over the defaults; reset deletes the row |
| `ROLE_DEFINITIONS` | `roles` + `role_permissions` | Built-ins synced at startup; grants added in the DB persist; custom roles are DB-only |
| `DEFAULT_CURRENCY` | `app_settings(localization.currency)` | Value must exist in the `currencies` table |
| Master-data reference rows | their own tables | Codes, names, symbols, statuses, and ordering are all data |

### Hardcoded with no override

| Area | Constant | Location |
|---|---|---|
| Order lifecycle | `ORDER_STATUS`, `_LEGACY_INACTIVE`, `SERVICE_ORDER_LIFECYCLE` | `operations/service.py`, `reports/service.py` |
| Movement / milestone states | `MOVEMENT_STATUSES`, `MILESTONE_STATUSES` | `operations/service.py` |
| Quotation states | `STATUS_MAP`, `IMMUTABLE_STATUSES` | `quotations/service.py` |
| Finance document classes | `PAYMENT_TYPES`, `INVOICE_TYPES`, the detailed-posting type sets | `finance/service.py` |
| Component field system | `REFERENCE_TYPES`, `DATA_TYPES`, `RENDER_MODES` | `component_config.py`, duplicated in `operations/reference_options.py` |
| Login policy | `MAX_FAILED_ATTEMPTS`, `LOCKOUT_MINUTES` are the **defaults**; the effective values come from `app_settings('security')`, clamped to 3–100 attempts and 1–1440 minutes | `auth/service.py` |
| Uploads | `_UPLOAD_TYPES` (the validator's known types) and `UPLOAD_MAX_SIZE_MB` | `operations/service.py`, `core/config.py` |
| Localization allow-lists | `SUPPORTED_LANGUAGES`, `TIMEZONES`, `DATE_FORMATS`, `TIME_FORMATS`, `NUMBER_FORMATS`, `CURRENCIES`, `LOCALES` | `core/localization.py` |
| Aging buckets | `_AGING_BUCKETS` and the 30/60/90 thresholds | `reports/service.py` |
| Permission catalog and page mapping | `SOURCE_PERMISSIONS`, `PAGE_PERMISSIONS`, `MATRIX_PAGE_PERMISSIONS`, aliases, `ROLE_DEFINITIONS` | `core/permissions.py` |
| Collection registries | `SPECS`, `GENERIC_COLLECTIONS`, `ARCHIVABLE_GENERIC_COLLECTIONS` | `master_data/service.py`, `archive/service.py` |
| Record statuses and transitions | `STATUS_POLICIES` | `app/modules/status/policy.py` — code-defined by design (§4 assessment), but **exposed** through `GET /{collection}/status-policy`, which the row menu renders, so the UI cannot offer a transition the API would refuse |
| Secrets and redaction | password denylist, `SENSITIVE_FIELD_NAMES`, `SENSITIVE_HINTS` | `core/security.py`, `core/crypto.py`, `backup/service.py` |
| Model defaults | `SERVICE_NOTE`, `PLATE`, `EXPECTED`, `DEBIT`, `BANK`, `MANUAL`, `ORIGINAL_POSTING`, `GENERATED_FROM` | model definitions |

**Assessment.** The *reference data* an administrator manages day to day — trade
directions, transport and container types, fee types, currencies and rates, tabs,
groups, attributes, labels, options, ordering, document numbers, posting rules and
app settings — is already database-driven. What remains hardcoded is *behaviour*
(status machines, validation allow-lists, security policy). That split is
deliberate and should stay: moving a status machine or a lockout threshold into a
row would let a configuration mistake weaken validation or authorization, which the
brief explicitly forbids.

Two hardcoded values are worth revisiting because the database already stores a
counterpart that is silently ignored: the login-lockout policy and
`allowedUploadExtensions`. Both are tracked in `docs/18`.

---

## 5. Security risk register

Ranked by blast radius. "Open" means no code change was made in this pass.

| # | Risk | Severity | Status |
|---|---|---|---|
| S1 | **An RSA private key sits in the working tree** at `docs/lcssystem.pem` (EC2 deploy key). It is gitignored and untracked, so it has never been committed — but it is inside the repository, is readable by any process with filesystem access, and would be swept into a `git add -A` if the ignore rule were ever lost. | High | **Open — needs the owner's decision.** Recommend moving it outside the repo. Read access is denied by `opencode.jsonc`. Not deleted here because it may be the only copy. |
| S2 | `attachments` were stored with `is_deleted` never set and no delete endpoint, so removing a file left it readable forever under a guessed key. | Medium | **Fixed.** `DELETE /api/v1/attachments` soft-deletes, unlinks the attachment, removes the storage object on a best-effort basis, and the download route then returns 404. Covered by `tests/test_attachments.py` (4 cases, including the permission denial). |
| S3 | No monitoring or alerting. A failed posting, a locked account, or a broken backup scheduler produces no signal. | Medium | Open |
| S4 | `chart_of_accounts`, `financial_accounts` and `posting_rules` deleted with **no guard**, so a referenced account or rule could be removed and leave postings without their mapping. | Medium | **Fixed.** A reusable policy in `app/core/deletion.py` (`dependent_references`, `ensure_deletable`, `require_inactive`) refuses to delete an active record, or one still referenced by another table, and names the referencing tables. Applied to all three finance delete paths; the archive module now shares the same scan instead of its own copy. Covered by `tests/test_deletion_policy.py` (8 cases). |
| S5 | ADB owner can bypass the guard triggers via the documented purge escape hatch. Mitigated by least-privilege roles, which are a deployment task. | Low | Documented in `docs/16` §5 |
| S6 | PostgreSQL-only guards do not run in the SQLite test suite, so CI alone cannot prove them; `tests/sql/integrity_guards.sql` is a manual step not wired into CI. | Low | Open |
| S7 | **User deletion fails for any account that has ever been audited.** `audit_events.actor_user_id` references `users(id)` with `NO ACTION`, and `fn_audit_append_only` rejects deletes and updates on the audit table, so `DELETE /api/v1/users` raises a foreign-key error as soon as the account has a `LOGIN` event — which is every account after its first sign-in. Verified on the running stack: `begin; delete from users where id = …; rollback;` → `violates foreign key constraint "fk_audit_events_actor_user_id_users"`. There is no API or CLI path that removes such an account; deactivation is the only working alternative. | Medium | **Open.** Needs an additive migration: `audit_events.actor_user_id` with `ON DELETE SET NULL` (the audit row and its stored action/entity survive, only the actor link is cleared), matching how `archive_records` and the reference tables already behave. Until then, accounts must be deactivated, not deleted. |

Confirmed controls (verified present): JWT access token + rotating persisted
refresh session; one active role enforced by a partial unique index; protected
System Administrator that cannot be deleted or deactivated; last-Platform-Admin
guard; `token_version` revocation; append-only audit log with a database trigger;
masked sensitive fields; password strength policy with a denylist; rate-limited
login and reports; content-signature validation on uploads; no secret in a tracked
file except S1.

---

## 6. Financial-correctness risk register

Ranked by the size of a wrong number.

| # | Risk | Severity | Status |
|---|---|---|---|
| F1 | **Dashboard order KPIs counted statuses the application cannot write**, so all four cards reported 0 forever and the by-status chart rendered an empty series even with orders present. | Medium | **Fixed.** `_service_order_status_counts` now maps the four contract keys onto `ACTIVE`/`INACTIVE`/`FINISHED` and reports the real lifecycle in `byStatus`. Regression test: `tests/test_reports_dashboard.py`. **Residual:** the frontend KPI cards still deep-link with the old filter values (`?workflowStatus=OPEN`), which match nothing — tracked in `docs/18` (frontend owner). |
| F2 | **Charge tax rate was silently discarded.** The charge line editor writes the rate under `taxRate`; `save_charge` read only `tax` and recomputed the amount from it, so a typed rate was dropped. The form displayed a taxed total while the server stored zero tax, and the invoice created from that charge carried no tax at all. | **High** | **Fixed.** The rate is read from `taxRate`, falling back to `tax`, and an out-of-range rate is reported against the key the client actually sent. Regression test: `tests/test_charge_tax_round_trip.py` (6 cases, including the invoice carrying the tax). |
| F3 | `cashBankBalance` was hardcoded `0.0`, so the cash card read zero even with posted receipts and payments. | Medium | **Fixed.** Derived from the posted ledger lines of the accounts mapped in `financial_accounts`, so it follows the administrator's own chart rather than hardcoded codes. Covered in `tests/test_reporting_values.py`. |
| F4 | `GET /service-orders/{id}/invoice` looked only for a `SERVICE_ORDER` source record, but issuing a charge records `SERVICE_ORDER_CHARGE`. The lookup returned null for an existing invoice, and the create path then raised a misleading "already invoiced" error. | Medium | **Fixed.** Both link shapes are followed, order-level preferred. Covered in `tests/test_reporting_values.py`. |
| F5 | **Trial balance was computed in the browser** from a paginated `ledger-lines` response, so the control that proves the ledger balances was not a control. | Medium | **Partially fixed.** `GET /api/v1/reports/trial-balance` now aggregates server-side over POSTED journals and returns an explicit `balanced` flag. Reconciliation is asserted in tests, including that a reversal returns every account to its prior balance. Remaining: P&L, balance sheet and cash flow are still browser-derived (`docs/18`). |
| F6 | Report totals are not reconciled in CI. `docs/15` §4 has the queries but nothing runs them on every build. | Low | Open |
| F7 | A client-supplied line **amount** (for example `tax` on a financial document line) is silently ignored rather than rejected, because the server recomputes amounts from the rate and quantity. Ignoring is the correct financial behaviour; silently accepting an unknown key is not. | Low | Open. Behaviour is right; the missing piece is a validation warning for unrecognised line keys. |
| F8 | **Status was writable straight through the generic update endpoints.** `PUT /chart-of-accounts/{id}`, `/financial-accounts/{id}`, `/posting-rules/{id}`, `/document-sequences/{id}`, `/accounting-periods/{id}` and every reference collection accepted any `status` string with no transition check and **no audit row**, and the create/edit forms carried an editable Status select that wrote it. A lifecycle change could therefore be made with no trace and outside the policy that governs it. | Medium | **Fixed.** Status is stripped from every compiled form (`moduleDocumentTabs`), and a single endpoint (`POST /{collection}/{id}/status`) validates the transition against `app/modules/status/policy.py`, checks the transition's own permission, refuses workflow statuses with `TRANSITION_REQUIRES_COMMAND` (so posting/reversal/issuing/close keep running their engines) and writes one audit event with the previous status, the new status, the actor and the timestamp. `tests/test_record_status.py` (18 cases). The generic `PUT` remains permissive by design for compatibility; it is no longer reachable from the UI for a status change. |
| F9 | The period "Reopen" path stored the label `REOPENED` and left `closed_at`/`closed_by_user_id` in place — the server clears that stamp only when the new status is exactly `OPEN` — so a reopened period kept an attribution to the user who closed it, and a status value the posting checks treat as open but the list and filters do not otherwise produce. | Low | **Fixed.** `finance.service.reopen_period` stores `OPEN`, clears the closure stamp and is audited as `PERIOD_REOPENED`; it is the transition the row menu offers from `CLOSED` (and from an existing `REOPENED` record). |
| F10 | The quotation **Reject** and **Cancel** handlers wrote the header status through the store's fire-and-forget save, leaving the revision in `DRAFT`/`SENT`: the screen showed a decision the workflow never applied, and no audit row was written. The path was also unreachable — the record page replaces the configured quotation actions with its own send/accept/convert set. | Low | **Fixed.** `reject_revision` and the new `cancel_revision` are the real transitions (audited as `QUOTATION_REJECTED` / `QUOTATION_CANCELLED`, reason recorded on the revision), offered from the status menu; the local status write and the dead handler are gone. `tests/test_record_status.py` exercises cancel → audit → "cannot be sent afterwards". |

Verified financial controls: debit equals credit enforced in the service layer *and*
by a deferred constraint trigger at COMMIT; posting is atomic; closed periods
reject postings; duplicate posting impossible via unique
`financial_document_postings`; posted journals and their lines immutable with
reversal as the only correction; allocation cannot exceed either side's remaining
balance and requires matching party and currency; money is `NUMERIC`/`Decimal`;
each posting snapshots its own exchange rate and base-currency amounts;
`tests/sql/integrity_guards.sql` exercises all 16 guard scenarios and the trial
balance reconciles.

---

## 7. Test coverage gaps

| Gap | Impact |
|---|---|
| No test for the PostgreSQL guards inside CI — `tests/sql/integrity_guards.sql` is manual | A trigger could regress silently. This already bit once: `post_document` and `reverse_document` queued the lines and the `status = "POSTED"` update in one flush, so SQLAlchemy emitted the header UPDATE first and `fn_guard_journal_line` rejected **every** posting on PostgreSQL. SQLite has no triggers, so the suite passed. Both functions now flush the lines while the header is still DRAFT, `tests/test_posting_rules.py` pins that ordering, and a 30-check smoke test against the live container exercises it end to end — but neither runs in CI, so the class of defect is still only caught by hand |
| No browser-level (E2E) test of the inline-validation flow | The Vue rendering, tab reveal and focus behaviour is verified at the unit and static-source level only; `focus.ts` is exercised against a DOM stand-in rather than a real browser |
| No unsaved-changes guard on document navigation | Requirement 13's "confirm before leaving a dirty form" is not implemented |
| Computed line-table cells cannot render an inline error | They are not editable, so the message would have no input to attach to; the cell is skipped during validation |
| P&L, balance sheet and cash flow have no server-side test | F5 remainder |
| No container register/status report or test | Feature 16 gap |
| Movements/milestone UI absent, so no end-to-end test of the operational itinerary | Feature 9 gap |
| No test for attachment delete (no endpoint) | Feature 19 gap |
| No test that an unrecognised line key is reported (F7) | A typo in a client payload stays silent |
| Concurrency of `post_document` is not raced in CI | The in-memory SQLite test database ignores `SELECT ... FOR UPDATE`, so the row lock that serialises two concurrent posts cannot be exercised. The duplicate-posting guard behind it is tested directly, and the invariant holds in production through that lock plus the unique `financial_document_postings` link |
| `uq_posting_rules_active_priority` is verified by SQLite `create_all`, not by a PostgreSQL run in CI | The index DDL is dialect-specific (an expression index); it was applied and reverted by hand against PostgreSQL 16 and the generated DDL is compared, but a CI-only regression would not be caught automatically |

Test coverage is named per feature in the table above (the "Test coverage" column
gives the file or spec for each one), and every run performed — with its command
and observed result — is recorded in `docs/18_implementation_checklist.md` →
Verification log. This section deliberately keeps no third copy of the counts,
which is why it no longer quotes them.

---

## 8. Recommended order of work

The ordered work queue, its owners and its live status are maintained in
`docs/18_implementation_checklist.md` → "Current work queue". This analysis
records status and risk, not the plan: keeping one copy stops a finished item
from looking outstanding here while the checklist says it is done.
