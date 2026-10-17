# Implementation checklist

Live per-feature status. Update the row you touch, in the same change that touches
the code — this file is the handover artifact and must not go stale.

**Status values:** `Done` (implemented, tested, gates green) · `Verify` (implemented,
no test proves it) · `Partial` (name the gap) · `Missing` · `Obsolete` ·
`Blocked` (name the blocker).

**Owner column:** `BE` backend, `FE` frontend, `DB` database/migration, `OPS`
deployment. A row with a `FE` gap cannot be closed while another session holds the
frontend tree.

---

## 1. Master data and configuration

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| master_data | 9 reference collections (parties, places, directions, containers, transport, assets, fee types, currencies, FX rates) | Done | — | `master_data/service.py` `SPECS` | `test_api_completeness.py`, `test_sorting.py` | `pytest` green | — | BE |
| master_data | Generic collections (companies, shipments, customs, documents, deliveries) | Done | — | `master_data/service.py` | `test_api_completeness.py` | green | `module_records` JSON store; not relational | BE |
| master_data | Archive codes reusable after soft delete | Done | — | `active_unique_index` in `master_data/models.py` | `test_archive.py` | green | — | DB |
| master_data | Delete policy: active rows cannot be deleted | Done | — | `delete_reference` (`REFERENCE_ACTIVE`) | `test_archive.py` | green | Applies to master data only | BE |
| finance | Deletion policy for accounts, financial accounts, posting rules | Done | — | `app/core/deletion.py` + the three finance delete paths | `test_deletion_policy.py` (8 cases) | green | Active rows refused (`RECORD_ACTIVE`); referenced rows refused naming the referencing tables (`DELETE_BLOCKED_BY_REFERENCES`); a refused multi-id request deletes nothing | BE |
| settings | App info and config, per-group rows | Done | — | `settings/service.py`, `settings/models.py` | `test_localization_settings.py` | green | — | BE |
| settings | Localization (en/km/zh, tz, formats) | Done | — | `core/localization.py` | `test_localization_settings.py`, `i18n-locales.spec.ts` | green | Selection constrained by code allow-lists by design | BE/FE |
| settings | Login lockout from app config | Done | — | `lockout_policy` in `auth/service.py` reads `app_settings('security')` | `test_lockout_policy.py` (4 cases) | green | Stored values honoured and clamped (`maxLoginAttempts` 3–100, `accountLockMinutes` 1–1440) so a bad value cannot remove the control | BE |
| settings | Upload extension allow-list from app config | Done | — | `effective_upload_extensions` in `operations/service.py` | `test_upload_policy.py` (4 cases) | green | The stored list can only narrow the environment list, never widen it, so it cannot enable an extension the content validator cannot inspect | BE |
| settings | Data reset | Done | — | `core/bootstrap.py::reset_all_data` | `test_setup.py` | green; opens the audited purge hatch on PostgreSQL | — | BE |

## 2. Users, roles, security

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| auth | Login / refresh / logout with rotation | Done | — | `auth/service.py` | `test_auth_rbac.py`, `test_auth_remember_me.py` | green | — | BE |
| auth | Remember-me lifetime | Done | — | `auth/models.py`, `auth/service.py` | `test_auth_remember_me.py` | green | — | BE |
| auth | Password reset by code | Done | — | `auth/service.py` | `test_auth_rbac.py` | green | Self-service only; needs an email the user can actually receive, which is why the administrative reset exists | BE |
| auth | Password strength policy | Done | — | `core/security.py` | `test_auth_rbac.py`, `password-policy.spec.ts` | green | Mirrored in the frontend so a weak password is refused before the round trip; the server re-validates and its refusal wins | BE/FE |
| auth | Administrative password reset with a forced change | Done | — | `set_user_password`, `must_change_password`, `POST /users/{id}/password` | `test_password_reset.py` (15 cases) | green | Gated on `user.manage`: creating a user already means choosing its password, so this is a recovery path rather than a wider capability. Revokes every session; clears any lockout. The password is never returned, and no screen can show an existing one — only an Argon2id digest is stored | BE |
| auth | Password handover and reveal-on-copy | Done | — | `UserPasswordDialog.vue`, `POST /users/{id}/password` | `password-reset.spec.ts`, live smoke test | green | Shown once after creating an account, and never afterwards | FE |
| auth | User CRUD with last-admin and self-delete guards | Done | — | `auth/service.py` | `test_auth_rbac.py` | green | — | BE |
| auth | Role CRUD, duplicate, permission matrix | Done | — | `auth/service.py` | `test_role_permissions.py` | green | — | BE |
| auth | One active role per user | Done | — | partial unique index on `user_role_assignments` | `test_role_permissions.py` | green | — | DB |
| auth | Protected System Administrator | Done | — | `auth/service.py`, `core/bootstrap.py` | `test_auth_rbac.py` | green | — | BE |
| auth | Token revocation via `token_version` | Done | — | `auth/service.py`, `core/deps.py` | `test_auth_rbac.py` | green | — | BE |
| audit | Append-only audit log | Done | — | `audit/service.py` + `fn_audit_append_only` | `test_archive.py`, `test_posting_rules.py`, `tests/sql/integrity_guards.sql` | 16/16 guards pass on PostgreSQL | Not enforced in the SQLite suite. The list now carries `eventType`/`entityType` (added so a rule change says *what* changed, not only that something did); the `before`/`after` images stay on the row and are read from there | BE/DB |
| auth | Sensitive-field masking | Done | — | `core/crypto.py` | `test_security_hardening.py` | green | — | BE |
| auth | Passwords are one-way only — no screen can reveal one | Done | — | `hash_password` (Argon2id); `user_payload` never returns a credential | `test_password_reset.py::test_an_administrator_can_set_a_password_and_never_sees_it_back` | green | Deliberate. A recoverable password would hand every account over in a database dump, a backup, or the Google Sheets mirror; the supported answer is an administrative reset plus a forced change | BE |

## 3. Quotations

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| quotations | Create quotation + V1 | Done | — | `quotations/service.py` | `test_quotations.py` | green | — | BE |
| quotations | Edit draft revision in place | Done | — | `save_quotation` | `test_quotations.py` | green | — | BE |
| quotations | New revision on edit of an issued revision | Done | — | `_clone_revision` | `test_quotation_versions.py` | green | Copy-on-write, source untouched | BE |
| quotations | Race-safe revision numbering | Done | — | `_clone_revision` row lock | `test_quotation_versions.py` (serialisation) | green | `FOR UPDATE` is a no-op on SQLite; the lock itself is unproven in tests | BE |
| quotations | Send / submit | Done | — | `send_revision`, `submit_revision` | `test_quotations.py` | green | — | BE |
| quotations | Accept with competing-revision supersede | Done | — | `accept_revision` | `test_quotations.py` | green | — | BE |
| quotations | Reject with `rejected_at` | Done | — | `reject_revision` | `test_quotation_versions.py` | green | — | BE |
| quotations | Compare two revisions | Done | No comparison UI | `compare_revisions` | `test_quotation_versions.py` | green | API only | BE/FE |
| quotations | Convert accepted revision to service order | Done | — | `convert_revision` | `test_quotation_versions.py` | green | Preserves `quotation_revision_id` | BE |
| quotations | Duplicate-conversion guard | Done | — | `quotation_conversions` unique constraints | `test_quotation_versions.py` | green | — | DB |
| quotations | Immutable revision content | Done | — | `IMMUTABLE_STATUSES` + clone-on-edit | `test_quotation_versions.py` | green | Application-level; no DB trigger | BE |
| quotations | Reject / cancel a revision (audited, reachable from the menu) | Done | — | `reject_revision`, `cancel_revision`, `POST /quotation-revisions/{id}/reject|cancel` | `test_record_status.py`, `test_quotation_versions.py` | green | Previously the menu handler wrote the header status through a fire-and-forget save and the revision stayed `DRAFT`/`SENT` (F10); both transitions are now real, audited and only offered where the status allows them | BE/FE |

## 4. Operations

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| operations | Service order CRUD and lifecycle | Done | — | `operations/service.py` | `test_workflows.py` | green | `DRAFT` model default is unreachable; runtime default is `ACTIVE` | BE |
| operations | Containers (add, list, uniqueness) | Done | — | `operations/service.py` | `test_workflows.py` | green | Container `status` accepts any string (not normalised) | BE |
| operations | Container requirements from quotation | Done | — | `create_service_order_from_quotation` | `test_workflows.py` | green | — | BE |
| operations | Movements (list, save, delete) | Done | No UI; delete has no status guard | `operations/service.py` | `test_movements_and_milestones.py` | green | — | BE |
| operations | Milestones (list, save, delete) | Done | No UI; delete has no status guard | `operations/service.py` | `test_movements_and_milestones.py` | green | Code change rejected once created | BE |
| operations | Charges: draft → issue → invoice draft | Done | — | `operations/service.py` | `test_finance_automation.py`, `test_charge_tax_round_trip.py` | green | Tax rate read from `taxRate` with a `tax` fallback; the invoice carries the tax | BE |
| operations | Attachments: presign, upload, list, download | Done | — | `operations/service.py` | `test_security_hardening.py` | green | — | BE |
| operations | Attachment delete | Done | — | `delete_attachments` in `operations/service.py` + `DELETE /attachments` (`attachment.delete`) | `test_attachments.py` | green | Soft-deletes, unlinks, removes the storage object best-effort, and stops serving the file | BE |
| operations | Service order ↔ invoice lookup | Done | — | `_service_order_invoice_documents` in `finance/service.py` | `test_reporting_values.py` | green | Follows both the `SERVICE_ORDER` and `SERVICE_ORDER_CHARGE` link shapes; the create path is idempotent instead of raising | BE |

## 5. Dynamic configuration

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| master_data | Attributes, groups, tabs CRUD | Done | — | `component_config.py` | `test_config_versions.py`, `component-config-tables.spec.ts` | green | Tab delete hard-deletes; group/attribute deactivate | BE/FE |
| master_data | Tabs scoped by trade direction, shared tabs via NULL | Done | — | `ComponentTab.trade_direction_id` | `test_config_versions.py` | green | — | BE |
| master_data | Runtime tab bootstrap and value validation | Done | — | `operations/component_tabs.py` | `test_workflows.py` | green | Row error keys are `"<1-based index>.<code>"`; the frontend registers `"{groupId}.{0-based index}.{code}"` — unmatched keys degrade to a page-level message | BE |
| master_data | Attribute code rename guard | Done | — | `_rename_attribute` (`ATTRIBUTE_CODE_IN_USE`) | `test_config_versions.py` | green | — | BE |
| master_data | Configuration versions: preview, publish, retire | Done | — | `config_versions.py` | `test_config_versions.py` | green | — | BE |
| master_data | Historical pinning (`configuration_version_id`) | Done | — | `stamp_service_order`, snapshot builder | `test_config_versions.py` | green | — | BE |
| master_data | Row-value preservation across config changes | Done | — | `service_order_component_rows.config_version_id` | `test_config_versions.py` | green | — | BE |

## 6. Finance

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| finance | Chart of accounts, financial accounts, periods, sequences | Done | — | `finance/service.py` | `test_workflows.py` | green | — | BE |
| finance | Multi-currency: base currency, approved rate store, per-document rate snapshot, converted amounts, precision | Done | Posting the allocation exchange difference through a configured account pair (the figures are computed and shown, not yet journalled); quotations, service orders and service charges carry a currency but no rate/base amounts of their own | `core/fx.py`; `master_data/currency_rates.py`; `master_data/models.py` (`CurrencyRate`, `Currency.decimal_places`); `finance/service.py` (`_document_currency_inputs`, `_allocation_fx`, `post_document`); `alembic/versions/d2e3f4a5b6c8_multi_currency.py`; frontend `utils/freight/fx.ts`, `document-tabs.ts` (`visibleWhen`), `document-calculations.ts` | `backend/tests/test_multi_currency.py` (17 cases); `frontend/tests/multi-currency.spec.ts` (13) | green | A document keeps the rate it was saved with, so an operator's rate is not silently re-resolved; only the APPROVED status is applied; `base_currency_code` is NULL on rows written before the feature, which the payload reports as the current base; the rate store has no sidebar page by owner request — the collection definition stays in `lcs-reference-modules.ts` for the API and option sources, and rates are maintained through `/api/v1/currencyRates` | FE + BE |
| finance | Financial document CRUD (draft only) | Done | — | `finance/service.py` | `test_finance_automation.py` | green | — | BE |
| finance | Financial documents module: type-driven fields, resolved accounts, complete payload | Done | A brand-new line shows its account code once the document is saved; there is no unsaved-preview endpoint | `finance/service.py` (`_document_columns`, `_line_account_id`, `_line_account_codes`, `_document_names`, `_document_detail_extras`, `document_payload`), `finance/posting.py` (`detail_account_code`) | `test_financial_documents_module.py` (20 cases: the scoping rules, the resolved and pinned account paths, the journal and the allocations, plus one create → read → post → balance run for **every** document type) | green | Save accepts both key spellings (`date`/`documentDate`, `referenceNo`/`referenceNumber`, `remark`/`description`, `financialAccountId` as an id or numeric string) because the form and the API client use different ones; a document keeps the type it was created with, since its number came from that type's sequence; reference ids leave as strings so the Master Data selects match their options | BE |
| finance | Posting with rule resolution | Done | — | `PostingRuleResolver` (`finance/posting_rules.py`), `AccountingPostingService` (`finance/posting.py`), `post_document` | `test_posting_rules.py`, `test_finance_automation.py` | green | A priority tie raises `AMBIGUOUS_POSTING_RULE`; `DEFAULT_ACCOUNTS` remains a last-resort fallback and the resolved `source` records which path was taken | BE |
| finance | Posting rules configuration UI | Done | — | `/finance/posting-rules`; `lcs-reference-modules.ts`, `useMenu.ts`, `role/permissions.ts` | `test_posting_rules.py` (46), `posting-rules-module.spec.ts` (14) | green | Credit-note document types need a number sequence; `CREDIT_NOTE`/`SUPPLIER_CREDIT_NOTE` are declared in `DEFAULT_PREFIXES`, so an existing install adds them via the Document Sequences page | BE/FE |
| finance | Posting rule history (changes + posting usage) | **Obsolete** | **Removed by owner request.** The history page, the rule-detail History tab, the per-rule and list endpoints, and their tests are gone. The audit events behind them are still written and still shown in Audit Logs. `posting_rules.priority` / `.description` and `journal_entries.posting_rule_id` are **kept**: they are the posting engine's resolution data, not history UI. Do not re-add the screens. | — | `tests/removed-features.spec.ts` (guards the removal), `test_posting_rules.py` | green | The history table never existed — the screen read `audit_events` | BE/FE |
| finance | Posting rules for invoices, bills, payments and credit notes | Done | — | `STRATEGIES` in `finance/posting.py` | `test_posting_rules.py` | green | `OTHER_INCOME`/`OTHER_EXPENSE`/`TRANSFER`/`ADJUSTMENT` still number from a derived prefix; unchanged by this work | BE |
| finance | Reversal with allocation unwind | Done | — | `reverse_document` | `test_finance_automation.py` | green | — | BE |
| finance | Payment allocation with over-allocation guard | Done | — | `allocate_payment`, `fn_guard_allocation` | `test_finance_automation.py`, `integrity_guards.sql` | 16/16 guards | — | BE |
| finance | Record status transitions (code policy, menu, audit) | Done | — | `app/modules/status/` (`policy.py`, `service.py`, `router.py`); `finance.service.reopen_period`; `operations.service.set_service_order_status` | `test_record_status.py` (18) | green | Status is not an editable form field anywhere; a workflow status (post, reverse, issue, close, quotation) is refused here with `TRANSITION_REQUIRES_COMMAND` and stays on its own endpoint; the generic `PUT` remains permissive for API compatibility and is no longer reachable from the UI for a status change; every plain transition writes one audit row with both statuses | BE |
| finance | Journal create / post / delete-draft | Done | — | `save_journal`, `post_journal` | `test_finance_automation.py` | green | — | BE |
| finance | Balanced, atomic, open-period posting | Done | — | `fn_validate_journal_post` (deferred) | `integrity_guards.sql`, `test_posting_rules.py`, live-stack smoke test | verified on PostgreSQL | Not enforced in the SQLite suite | DB |
| finance | Immutable posted journals | Done | — | `fn_guard_journal_entry`, `fn_guard_journal_line` | `integrity_guards.sql`, `test_posting_rules.py` | verified on PostgreSQL | Fixed in this pass: lines were flushed together with the `status = "POSTED"` update, so `fn_guard_journal_line` rejected every posting on PostgreSQL while SQLite stayed green. Both call sites now flush the lines while the header is DRAFT | DB/BE |
| finance | Multi-currency base amounts and rate snapshots | Done | No FX report translation yet | `journal_entry_lines`, `financial_documents` | `test_finance_automation.py` | green | `currency_rates` is maintained but not consumed for translation | BE |
| finance | Service order profitability | Done | — | `reports/repository.py::service_order_finance_rows` | `test_workflows.py` | green | Same-currency only | BE |

## 7. Reports

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| reports | Dashboard KPIs and charts | **Partial** | Order KPIs, cash/bank balance and the by-status chart now report real data. **Remaining:** the frontend KPI cards still deep-link with `?workflowStatus=OPEN` etc., which match nothing | `reports/service.py` | `test_reports_dashboard.py`, `test_reporting_values.py` | green for the KPIs | Risk F1 residual (FE only) | BE/FE |
| reports | Receivables / payables with aging | Done | — | `reports/service.py` | `test_finance_automation.py` | green | — | BE |
| reports | Revenue and expense, ledger lines | Done | — | `reports/service.py` | `test_finance_automation.py` | green | — | BE |
| reports | Trial balance | Done | — | `GET /api/v1/reports/trial-balance`, `posted_trial_balance_rows` | `test_reporting_values.py` (reconciles; a reversal returns every account to its prior balance) | green | `balanced` flag proves both sides agree and the ledger nets to zero | BE |
| reports | Profit & loss | Done | — | `GET /api/v1/reports/profit-loss` | `test_reporting_values.py` | green | Signed by normal balance, so credit-normal revenue reads positive | BE |
| reports | Balance sheet | Done | — | `GET /api/v1/reports/balance-sheet` | `test_reporting_values.py` (asserts assets = liabilities + equity + net result) | green | Retained earnings shown explicitly because no year-end closing entry is posted | BE |
| reports | Cash flow | Done | — | `GET /api/v1/reports/cash-flow`, `cash_flow_rows` | `test_reporting_values.py` (asserts agreement with the dashboard cash card) | green | Inflow − outflow = net = closing by construction | BE |
| reports | Container register / status | Done | — | `GET /api/v1/reports/container-register`, `container_register_rows` | `test_reporting_values.py` | green | Status breakdown included | BE |
| reports | Reconciliation assertions in CI | **Missing** | Queries exist in `docs/15` §4 but nothing runs them on every build | `.github/workflows/dev-ci.yml` | manual only | not automated | Risk F6 | OPS |
| reports | SQL views | Done | — | `e6f7a8b9c0d1_reporting_views_and_integrity.py` | `integrity_guards.sql` §G15 | 8 views verified | — | DB |

## 8. Frontend

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| frontend | Pages for all modules (73 routes) | Done | — | `frontend/app/pages/**` | page-access/navigation specs | `lint`, `typecheck`, `test` pass | — | FE |
| frontend | Metadata-driven module, field and table definitions | Done | — | `config/freight-modules.ts`, `lcs-reference-modules.ts` | module specs | green | — | FE |
| frontend | Line-table column sizing (per-column field width, field fills its column) | Done | Admin-supplied widths are honoured only when a column config carries `width`; no screen writes it yet | `utils/table/line-table-columns.ts`, `components/freight/AppLineTable.vue` | `line-table-columns.spec.ts` (7 cases), `line-table-rules.spec.ts` sizing guard | `lint`, `typecheck`, `test`, `i18n:check` pass | — | FE |
| frontend | Note and delete share one icon column on every line table | Done | The container-payment row action (`_invoice`) keeps a column of its own, empty until the row has an invoice | `utils/table/line-table-columns.ts` (`sharedRowControls`), `components/freight/AppLineTable.vue` | `line-table-columns.spec.ts` (4 fold cases), `pricing-and-notes.spec.ts` fold guard over the three job grids | `lint`, `typecheck`, `test` pass | — | FE |
| frontend | Service-order Finance tab shows the finance table and its per-kind totals only (no summary strip) | Done | Job revenue / cost / profit / outstanding are no longer displayed on the order itself — they live in the Finance module's reports; the three now-unused `freight.ui.*` labels are kept in the bundles | `components/freight/JobFinance.vue`; `JobSummaryStrip.vue` deleted, copy in `backups/removed-features-20261015-172748/` | `lint`, `typecheck`, `test`, `i18n:check` pass | — | FE |
| frontend | Financial Documents form: fields and tabs scoped to the document type | Done | A document's type cannot be changed after creation (its number came from that type's sequence) | `config/freight-modules.ts` (`documentTypes`, module fields), `config/freight-options.ts` (`PAYMENT_DOCUMENT_TYPES`, `ALLOCATABLE_DOCUMENT_TYPES`, `ALLOCATION_DOCUMENT_TYPES`, `CREDIT_TERM_DOCUMENT_TYPES`), `utils/freight/document-tabs.ts` (`appliesTo`, `scopedTabs`), `components/freight/DocumentView.vue` | `document-tabs.spec.ts` (3 new cases), `financial-documents.spec.ts` (7 cases), `document-form-validation.spec.ts` | `lint`, `typecheck`, `test`, `i18n:check` pass | The four type sets mirror backend constants and are asserted against the module config, not against the backend | FE |
| frontend | Posting-confirmation card removed from the document view | Done | The card was **browser-only**: it read `accountingPeriods` from the store and hardcoded AR/Revenue, AP/Expense or Cash/AR per document type. There is **no** API behind it, so nothing was removed server-side; the posting-rules endpoints and `PostingRuleResolver.explain()` are the real posting engine and stay | `components/freight/DocumentView.vue`; `lcs.finance.postingConfirmation` + `…Hint` dropped from all three bundles (`lcs.finance.documentTotal` and `freight.fields.debitAccount`/`creditAccount`/`balanceDifference` kept — the `freight.fields.*` ones are dynamic field labels for the posting-rule and journal forms); the card is still recoverable from git HEAD | repo-wide grep for the removed keys; `node -e JSON.parse` on the three bundles. `lint`/`typecheck`/`test` **not run** — the owner asked for no more test runs | — | FE |
| frontend | i18n en/km/zh parity (3023 keys) | Done | — | `i18n/locales/*.json` | `i18n-locales.spec.ts`, `pnpm i18n:check` | green | — | FE |
| frontend | Bilingual print output | Done | — | `composables/print/`, `components/print/` | print specs | green | — | FE |
| frontend | Inline validation stack (`useFormValidation`, `AppFormErrorSummary`, focus + tab reveal, server error mapping) | Done | Computed line-table cells carry the focus target but cannot display a message (they are not editable). `UFormField.error` must receive `undefined` for a clean field — an empty string casts to `true` (Boolean before String) and reds out the control; normalise through `utils/validation/form-field-error.ts` | `utils/validation/**`, `composables/common/useFormValidation.ts` | 11 specs: `validation-error-paths`, `validation-field-rules`, `validation-api-error`, `validation-focus`, `validation-messages`, `form-validation-composable`, `component-attribute-validation`, `document-form-validation`, `save-grid-validation`, `validation-notification-policy`, `form-field-error` | green | — | FE |
| frontend | Success-only toast policy | Done | — | `composables/useApi.ts`, `stores/freight.ts`, `composables/freight/useLcs.ts`, `composables/freight/useFinanceCommands.ts`, `composables/freight/useQuotationCommands.ts` | `validation-notification-policy.spec.ts` scans every toast call | green | `useApi` still toasts transport failures; 400/409/422 are suppressed because the owning form renders them inline | FE |
| frontend | Status changed from the row "..." menu (reusable status manager) | Done | — | `composables/freight/useRecordStatus.ts`, `utils/freight/status-actions.ts`, `utils/freight/status-commands.ts`, `components/common/AppPromptHost.vue`; used by `WorkspaceView.vue`, `DocumentView.vue` and `JobDetail.vue` | `record-status.spec.ts` (7), `financial-documents.spec.ts`, `document-tabs.spec.ts` | `lint`, `typecheck`, `test`, `i18n:check` pass | Only transitions the policy allows *and* the caller may perform are rendered; a refusal goes to the page/form summary, a confirmation toasts; the reversal reason is collected by the app-wide prompt host; the list row shows the in-flight spinner while the request runs | FE |
| frontend | Movements / milestones editor | **Missing** | No UI for the movement and milestone APIs | — | none | not covered | Feature 9 gap | FE |
| frontend | Quotation revision comparison view | **Missing** | API exists, no side-by-side view | — | none | not covered | — | FE |
| frontend | Dead template helpers removed | **Obsolete** | `job-task-fields.ts` + `job-component-line-table.ts` are unreferenced | `utils/freight/` | `job-task-fields.spec.ts` still exercises them | green | Safe to delete in a dedicated cleanup | FE |

## 9. Database

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| DB | 62-table schema via 26 revisions | Done | — | `alembic/versions/` | `test_migration_chain.py` | single head, linear, every revision reversible | — | DB |
| DB | Additive revisions: currencies + FX rates, app_settings, configuration_versions, views + guards | Done | — | `b3c4d5e6f7a8` … `e6f7a8b9c0d1` | `test_migration_chain.py` asserts additive-only | `upgrade` and `downgrade` both verified | — | DB |
| DB | Declarative constraints (partial unique indexes, checks, NUMERIC, tz-aware) | Done | — | models + migrations | `test_schema_integrity.py` | green | — | DB |
| DB | Generated schema documents | Done | — | `docs/06`, `docs/06b` | `test_schema_docs.py` | `--check --strict` green | — | DB |
| DB | Model/migration agreement | Done | — | — | manual DDL-vs-Alembic comparison | 122/122 FKs identical; 2 pre-existing documented column divergences | — | DB |
| DB | Full rollback to base | **Blocked** | Pre-existing defect in legacy revision `6e862ce04e46`; rollback boundary is the previous release head | `alembic/versions/6e862ce04e46_*.py` | documented | `downgrade a2b3c4d5e6f7` verified clean | Not fixable without editing a released revision | DB |

## 10. Deployment

| Module | Feature | Status | Missing work | Location | Test coverage | Validation | Known issues | Owner |
|---|---|---|---|---|---|---|---|---|
| OPS | Docker Compose stack (5 services) | Done | — | `infrastructure/docker-compose.yml` | CI Docker build check | stack healthy locally | — | OPS |
| OPS | CI gates + Docker build on `dev` / PRs to `main` | Done | — | `.github/workflows/dev-ci.yml` | CI | — | Does not run the SQL guard script | OPS |
| OPS | Production workflow: build, push, back up, deploy | Verify | Has not been executed from this environment | `.github/workflows/production.yml` | none | not run | — | OPS |
| OPS | Runtime-only host (repo not cloned) | Done | — | `deploy/compose.yml` transfer | — | — | — | OPS |
| OPS | PostgreSQL backups + restore drill | **Partial** | Google Sheets replication is done and tested; off-host `pg_dump` + WAL archiving is documented, not automated | `docs/15` §5, `docs/12` | `test_backup.py` (Sheets only) | restore procedure verified manually against a dump | The Sheets tables are **not** a database backup | OPS |
| OPS | Monitoring and alerting | **Missing** | No metrics, no alerts, no health dashboard | — | none | not covered | Risk S3 | OPS |
| OPS | Secret hygiene | **Partial** | An RSA private key sits in the working tree at `docs/lcssystem.pem` (untracked, gitignored, read-denied by `opencode.jsonc`) | `docs/lcssystem.pem` | `git check-ignore` | not committed | Risk S1 — needs the owner's decision | OPS |

---

## Current work queue

Ordered, with the reason and the owner. None of these is destructive, so none
requires an approval gate.

| # | Task | Why | Owner | Status |
|---|---|---|---|---|
| 1 | ~~`cashBankBalance` real value~~ | Always-zero KPI card | BE | **Done** (`test_reporting_values.py`) |
| 2 | ~~Service-order invoice lookup~~ | Returned null for a document that exists | BE | **Done** (`test_reporting_values.py`) |
| 3 | ~~Charge tax rate (`taxRate` vs `tax`)~~ | The tax a user typed was silently dropped and the invoice carried none | BE | **Done** (`test_charge_tax_round_trip.py`) |
| 4 | ~~Deletion guards for accounts, financial accounts, posting rules~~ | Referenced rows could be deleted | BE | **Done** (`test_deletion_policy.py`) |
| 5 | ~~Trial balance, P&L, balance sheet, cash flow, container register server-side~~ | The balance control and the statements were computed in the browser | BE | **Done** (`test_reporting_values.py`, 10 cases) |
| 6 | `vw_general_ledger` still not exposed as an endpoint | The view exists but nothing reads it; `ledger-lines` covers the same rows | BE | Queued (low value) |
| 7 | ~~Attachment delete endpoint (S2)~~ | `attachment.delete` existed with no endpoint | BE | **Done** (`test_attachments.py`, 4 cases) |
| 8 | ~~Container register / status report~~ | Required report; absent | BE | **Done** (`test_reporting_values.py`) |
| 9 | ~~Read the DB-stored login lockout and upload allow-list~~ | Configuration was stored and ignored | BE | **Done** (`test_lockout_policy.py`, `test_upload_policy.py`) |
| 10 | Report unrecognised line keys instead of ignoring them (F7) | A payload typo stays silent | BE | Queued |
| 11 | ~~Specs for the frontend validation primitives~~ | The inline-validation contract is unverified | FE | **Done** (9 new specs, 124 assertions) |
| 12 | ~~Suppress the global error toast on form submits~~ | A validation failure is reported twice | FE | **Done** (`useApi.isInlineValidationStatus`) |
| 13 | Fix the dashboard KPI deep-link filter values (F1 residual) | Cards link to filters that match nothing | FE | Blocked |
| 14 | Movements / milestones editor | API complete, unreachable from the UI | FE | Blocked |
| 15 | Run `integrity_guards.sql` + reconciliation in CI (F6) | Guards and totals are only checked by hand. This already cost a real outage: posting failed on PostgreSQL while the SQLite suite stayed green (see `docs/17` §7). Now the highest-value CI addition | OPS | Queued |
| 16 | Monitoring and alerting (S3) | A failed posting or backup produces no signal | OPS | Queued |
| 17 | Move `docs/lcssystem.pem` out of the repository (S1) | Private key inside the working tree | OPS | **Needs the owner's decision** |
| 18 | Refresh `docs/07`–`docs/09`, regenerate the Postman collection, decide `docs/10` | Diagrams and API collection lag the schema | Docs | Queued |
| 19 | ~~Posting rules management (UI, priority, credit notes, reusable resolver and posting service)~~ | Rules were API-only, had no priority, and credit notes had no posting path | BE/FE | **Done** (`test_posting_rules.py` 35 cases, `posting-rules-module.spec.ts` 8) |
| 20 | ~~Posting rule history and usage, plus a list table on the index route~~ | The index route rendered the form instead of a list, and a rule change left no visible trace | BE/FE | **Done** (`test_posting_rules.py` 46 cases, `posting-rules-module.spec.ts` 14) |
| 21 | ~~Administrator password reset, reveal-on-create and forced change~~ | A user who forgot their password and could not receive the reset email had no recovery path; a temporary password could be kept in use indefinitely | BE/FE | **Done** (`test_password_reset.py` 15 cases, `password-policy.spec.ts` 14, live smoke 23/23) |
| 22 | Delete an account that has audit history (S7) | `DELETE /users` fails with a foreign-key error once the account has any `LOGIN` audit event, so stale accounts can only be deactivated | DB | Queued — additive migration setting `audit_events.actor_user_id` to `ON DELETE SET NULL`, then a deletion test with audit rows present |
| 23 | ~~Record statuses through the row "..." menu instead of the create/edit forms~~ | Status was writable through the generic update endpoints with no transition check and no audit row (F8); the period reopen left a stale closure stamp (F9); the quotation reject/cancel handlers wrote a header status the workflow never applied (F10) | BE/FE | **Done** (`test_record_status.py` 18 cases, `record-status.spec.ts` 7) |

`Blocked` rows are blocked solely because another session currently holds the
frontend tree. Re-check the file modification times before starting one.

---

## Verification log

Each entry is a command that was actually run, with its observed result.

| Change | Command | Result |
|---|---|---|
| Dashboard KPIs | `uv run python -m pytest tests/test_reports_dashboard.py -q` | 2 passed |
| Cash balance, invoice lookup, trial balance, P&L, balance sheet, cash flow, container register | `uv run python -m pytest tests/test_reporting_values.py -q` | 10 passed |
| Deletion policy | `uv run python -m pytest tests/test_deletion_policy.py -q` | 8 passed |
| Charge tax round trip | `uv run python -m pytest tests/test_charge_tax_round_trip.py -q` | 6 passed |
| Attachment delete | `uv run python -m pytest tests/test_attachments.py -q` | 4 passed |
| Lockout policy from stored config | `uv run python -m pytest tests/test_lockout_policy.py -q` | 4 passed |
| Upload allow-list from stored config | `uv run python -m pytest tests/test_upload_policy.py -q` | 4 passed |
| API completeness (updated for the two-step delete rule) | `uv run python -m pytest tests/test_api_completeness.py -q` | passed |
| Regressions in touched modules | `uv run python -m pytest tests/test_finance_automation.py tests/test_workflows.py tests/test_archive.py -q` | 25 + 12 passed |
| Lint | `uv run ruff check .` | passed |
| Full backend suite | `uv run python -m pytest -q --no-header` | **307 passed, exit 0** (17m10s) |
| `opencode.jsonc` | node comment-stripping parse | 26 rules (11 deny, 14 ask, 1 allow), 0 malformed; sets no model, provider or MCP |
| Frontend inline validation | `pnpm lint` | passed, 0 errors |
| Frontend inline validation | `pnpm typecheck` | passed, 0 errors |
| Frontend inline validation | `pnpm test` | 59 files, 422 tests passed |
| Frontend inline validation | `pnpm i18n:check` | 2957/2957 keys in `km` and `zh`, passed |
| Frontend inline validation | `pnpm generate` | static SPA built, 55 routes prerendered |
| Frontend, after posting rules | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` / `pnpm generate` | 0 errors; 60 files, 436 tests passed; 2982/2982 keys; 58 routes prerendered |
| Frontend ↔ backend contract | `uv run python -m pytest tests/test_frontend_api_contract.py -q` | 3 passed |
| Backend (unmodified) | `uv run python -m pytest tests/test_api_completeness.py -q` | 6 passed |
| Posting rules | `uv run python -m pytest tests/test_posting_rules.py -q` | 38 passed |
| Posting rules, live stack | 30-check HTTP smoke test against the running PostgreSQL container (CRUD, validation, priority, posting, duplicate posting, reversal, audit, permissions, deletion guard, trial balance) | 30/30 passed |
| Posting rules page, live stack | 8-check test through nginx: the three routes are served and the API answers same-origin, with a non-empty source for every select | 8/8 passed |
| Posting rule history | `uv run python -m pytest tests/test_posting_rules.py -q` | 46 passed |
| Posting rule history, live stack | 26-check HTTP smoke test through nginx: list table, change diff, usage, reversal attribution, delete guard, page routes | 26/26 passed |
| Administrative password reset, live stack | 23-check HTTP smoke test through nginx: reset, session revocation, the forced-change block, refresh as a non-escape, owner change, weak-password refusal, audit, page routes | 23/23 passed |
| Posting rules migration | `alembic upgrade head` / `downgrade e6f7a8b9c0d1` / `upgrade head` on PostgreSQL 16 | applied, reverted (9 columns + PK only), reapplied; head `f8a9b0c1d2e3` |
| Generated schema docs | `uv run python scripts/generate_schema_dump.py` and `generate_schema_docs.py` | 63 tables; `test_schema_docs.py` green |
| Navigation i18n (reported from a Chinese session) | `pnpm vitest run tests/navigation-i18n.spec.ts` | 6 passed |
| Navigation i18n, key audit | every `t('…')` in `useMenu.ts` (8 nav + 28 page keys) resolved in all 3 locales | 0 missing |
| Frontend, after the navigation fix | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 errors; 61 files, 442 tests passed; 2985/2985 keys |
| Currency rates + posting rule history removal still hold | `pnpm vitest run tests/removed-features.spec.ts tests/navigation-i18n.spec.ts` | 2 files, 17 tests passed |
| Cross-stack API contract after the removals | `uv run python -m pytest tests/test_frontend_api_contract.py -q` | 3 passed |
| Generated schema documents after dropping `currency_rates` | `uv run python -m pytest tests/test_schema_docs.py -q` | 7 passed; both `docs/06` and `docs/06b` carry 62 tables and no `currency_rates` |
| Migration chain after dropping `currency_rates` | `uv run python -m pytest tests/test_migration_chain.py -q` | 12 passed |
| Line-table column widths (per-column field width, field fills its column) | `pnpm vitest run tests/line-table-columns.spec.ts tests/line-table-rules.spec.ts tests/document-tabs.spec.ts tests/pricing-and-notes.spec.ts tests/validation-notification-policy.spec.ts` | 5 files, 66 tests passed |
| Line-table column widths | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 errors; 63 files, 480 tests passed; 3023/3023 keys |
| Note and delete folded into one icon column | `pnpm lint` / `pnpm typecheck` / `pnpm test` | 0 errors; 63 files, 485 tests passed |
| Finance tab summary strip removed | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 errors; 63 files, 485 tests passed; 3023/3023 keys |
| Posting-confirmation card removed | repo-wide grep for `postingConfirmation` and `lcs.finance.documentTotal`; `node -e JSON.parse` on `en`/`km`/`zh` bundles | 0 remaining references; all three bundles parse. **No API existed for the card** (finance router has no posting-preview route). Gates deliberately not run — the owner asked to stop running tests |
| Financial documents module: type scoping, save keys, resolved account codes, journal/allocations in the payload | `uv run python -m pytest tests/test_financial_documents_module.py -q` | 20 passed |
| Finance regressions after the payload/save change | `uv run python -m pytest tests/test_posting_rules.py -q` | 42 passed |
| Workflows, finance automation, charge tax after the change | `uv run python -m pytest tests/test_workflows.py tests/test_finance_automation.py tests/test_charge_tax_round_trip.py -q` | 25 passed |
| Backend lint | `uv run ruff check .` | All checks passed |
| Financial documents form (frontend) | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 errors; 66 files, 508 tests passed; 3024/3024 keys |
| Financial documents module, full backend regression | `uv run python -m pytest -q --no-header` | **340 passed**, exit 0 (16m52s) |
| Clean fields no longer render the error ring (`UFormField.error` empty-string cast) | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 errors; 64 files, 490 tests passed; 3023/3023 keys |
| Clean fields …, live stack | headless Chrome (CDP) against `/service-orders/new` after rebuilding the `ff-frontend` image: computed `box-shadow: none`, `aria-invalid="false"` on every Overview control; summary still lists `Company is required.` / `Trade Directions is required.` | fixed |
| Real errors still render (regression guard for the same change) | same browser run on `/service-charges/new` after Submit: Company field keeps the ring, `aria-invalid="true"` and the inline message `Company is required.` | intact |
| User deletion with audit history (S7 finding) | `begin; delete from users where id = …; rollback;` on the live database | `ERROR: violates foreign key constraint "fk_audit_events_actor_user_id_users"` — deletion path is broken for audited accounts (S7) |
| Record status: policy, transitions, audit, permissions, period reopen, command refusal, frontend-runner parity | `uv run python -m pytest tests/test_record_status.py -q` | 18 passed |
| Quotations reject/cancel and revision workflow | `uv run python -m pytest tests/test_record_status.py tests/test_quotations.py tests/test_quotation_versions.py -q` | 31 passed |
| Cross-stack API contract after the two new status routes | `uv run python -m pytest tests/test_frontend_api_contract.py -q` | 3 passed |
| Status frontend specs | `pnpm vitest run tests/record-status.spec.ts tests/document-tabs.spec.ts` | 2 files, 22 tests passed |
| `financial-documents.spec.ts` updated for the new contract (the old case pinned the status field on the form) | `pnpm vitest run tests/financial-documents.spec.ts` | 8 passed — the case now asserts the status is absent from the compiled form and that the record page runs the shared status manager; no assertion was deleted or loosened |
| Status frontend gates | `pnpm lint` / `pnpm typecheck` / `pnpm test` | 0 errors; 66 files, 508 tests passed |
| Status i18n keys (`freight.statusActions.*`, `freight.ui.status*`, `lcs.common.reason`, `freight.ui.requote`) in en/km/zh | `pnpm i18n:check` | 3046/3046 keys in `km` and `zh`, passed |
| Status action icons reach the client bundle (the two new ones are named in `app/config/status-actions.ts`, which the icon scanner globs) | `pnpm generate` | generated `.output/public`; Nuxt Icon client bundle 161 icons (was 159 — exactly `i-lucide-flag` and `i-lucide-lock-open` added); 56 routes prerendered |
| Status backend lint | `uv run ruff check .` | passed |
| Status, full backend suite (final, after every backend edit in this change) | `uv run python -m pytest -q --no-header` | **353 passed, exit 0** (20m20s; the warnings are the pre-existing Starlette `HTTP_422_UNPROCESSABLE_ENTITY` deprecations) |
| Duplication cleanup (dead code + duplicated docs) | backend `uv run ruff check .`; `uv run python -m pytest tests/test_attachments.py tests/test_upload_policy.py tests/test_api_completeness.py tests/test_frontend_api_contract.py tests/test_config_versions.py tests/test_localization_settings.py tests/test_page_api_integration.py tests/test_quotation_versions.py tests/test_role_permissions.py tests/test_security_hardening.py -q`; frontend `pnpm lint` / `pnpm typecheck` / `pnpm test` | ruff passed (one now-unused `json` import removed with the dead function); **72 passed**; frontend 0 lint/type errors, **65 files / 505 tests passed** — the three tests of the deleted dead-code spec went with it, no assertion was weakened. Deleted: the `JobLineTable` pass-through wrapper, `utils/table/row-meta.ts`, `serialization.record/records`, `localization.format_*`, `_resolve_rule`, `snapshot_size`, `config_versions.STATUSES`, the duplicate `POST /attachments` route; docs: cross-document copies in `docs/02`, `docs/05`–`docs/16` replaced by pointers |

| Multi-currency: rate store, resolution, validation, converted amounts, allocation difference | `uv run python -m pytest tests/test_multi_currency.py -q` | **17 passed** |
| Currency master + FX regressions after the removal guard was rewritten | `uv run python -m pytest tests/test_currencies_and_fx.py tests/test_financial_documents_module.py tests/test_finance_automation.py -q` | 27 passed (the guard now asserts the store is routed and consumed instead of asserting its absence — asserted positively in `test_multi_currency.py`) |
| Migration `d2e3f4a5b6c8` against PostgreSQL 16 (disposable database, with a document in place at a non-1 rate) | `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` inside the API container | backfill exact (`105 × 2 = 210.0000`); `CHECK rate > 0` and the distinct-pair constraint both fire; the downgrade removed the table and all five columns; re-upgrade returned to head |
| Generated schema documents after the rate store returned | `uv run python scripts/generate_schema_dump.py`, `generate_schema_docs.py`, `uv run python -m pytest tests/test_schema_docs.py tests/test_schema_integrity.py -q` | 63 tables, all columns documented; 26 passed |
| Frontend: conditional rate field, converted total, direction, rate store page | `pnpm lint` / `pnpm typecheck` / `pnpm test` / `pnpm i18n:check` | 0 lint/type errors; **66 files, 515 tests passed**; 3054/3054 keys in `km` and `zh` |
| Migration applied to the development database (running stack) | `docker exec ff-api alembic upgrade head`; `GET http://localhost:8000/health` from the host | applied `c1d2e3f4a5b7 -> d2e3f4a5b6c8`; 64 tables (= 63 + `alembic_version`), 5 `base_*` columns on `financial_documents`, 13 columns on `currency_rates`; `/health` → 200 `{"status":"ok"}`, so the additive migration leaves the previous build running |
| Full backend suite, first run — started before the unused `created_by_user_id` column was dropped from `currency_rates` and the generated docs regenerated, so it raced those edits | `uv run python -m pytest -q --no-header` | **368 passed, 2 failed**: both failures are `tests/test_schema_docs.py` drift assertions comparing the generator's fresh output against the pre-regeneration files. On the frozen state that file re-runs green (`7 passed`) and both generators report "up to date", so the schema documents match the models |
| Multi-currency, full backend suite on the frozen state (final) | `uv run python -m pytest -q --no-header` | **370 passed, exit 0** (21m48s; the warnings are the pre-existing Starlette `HTTP_422_UNPROCESSABLE_ENTITY` deprecations) |

Shell note: `uv run pytest …` returns exit 1 with no output in this Windows
session; `uv run python -m pytest …` works and is what the rows above used.
