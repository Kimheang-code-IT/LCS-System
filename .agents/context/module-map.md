# Module navigation map

Source-inspected 2026-11-04. Read only the selected row and owner; this is not acceptance status.
API entries below are relative to /api/v1; use the router for verbs and nested actions.
Paths/models are verified; linked canonical MOD records own requirements and status.

## Shared owners

Report routes reuse the area/slug page, ReportsView.vue, config/freight-reports.ts and
utils/freight/report-queries.ts. A displayed report need not have its own endpoint.

| Code | Backend owner (router + service + models where present) |
|---|---|
| Q | [backend/app/modules/quotations](../../backend/app/modules/quotations/) |
| O | [backend/app/modules/operations](../../backend/app/modules/operations/) |
| F | [backend/app/modules/finance](../../backend/app/modules/finance/) |
| R | [backend/app/modules/reports](../../backend/app/modules/reports/) |
| M | [backend/app/modules/master_data](../../backend/app/modules/master_data/) |
| A | [backend/app/modules/auth](../../backend/app/modules/auth/) |
| S | [backend/app/modules/settings](../../backend/app/modules/settings/) |
| X | [backend/app/modules/archive](../../backend/app/modules/archive/) |
| U | [backend/app/modules/audit](../../backend/app/modules/audit/) |

R reads O/F/M models; it has no reports/models.py ledger. Configuration lives in M
(component_config.py, config_versions.py). Auth decisions use
[core/authorization](../../backend/app/core/authorization/) even when A exposes the API.

## All 44 approved business pages

| ID / module | Frontend entry | Backend | API entry | Primary DB entities | Related owners | Canonical detail / phase |
|---|---|---|---|---|---|---|
| MOD-001 Dashboard | [index.vue](../../frontend/app/pages/index.vue) | R | `/reports/dashboard` | `journal_entries`, `journal_entry_lines`, `financial_documents`, `financial_document_allocations`, `service_orders` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-001) / P13 / S09–S10 |
| MOD-002 Quotations | [quotations/index.vue](../../frontend/app/pages/quotations/index.vue) | Q | `/quotations` | `quotations`, `quotation_revisions`, `quotation_revision_places`, `quotation_revision_containers`, `quotation_revision_lines`, `quotation_conversions` | M,O | [requirements](../../docs/00-project/feature-inventory.md#mod-002) / P05 / S02 |
| MOD-003 Service Orders | [service-orders/index.vue](../../frontend/app/pages/service-orders/index.vue) | O | `/service-orders` | `service_orders`, `service_order_places`, `service_order_pricing`, `service_order_pricing_lines`, `service_order_containers`, `service_order_component_rows` | Q,M,F | [requirements](../../docs/00-project/feature-inventory.md#mod-003) / P06 / S02–S03 |
| MOD-004 Service Charges | [service-charges/index.vue](../../frontend/app/pages/service-charges/index.vue) | O | `/service-charges` | `service_order_charges`, `service_order_charge_lines`, `financial_document_sources` | Q,M,F | [requirements](../../docs/00-project/feature-inventory.md#mod-004) / P07 / S04 |
| MOD-005 Service Order Register | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | O,F,R | `/service-orders` + `/service-charges` + `/financial-documents` (shared store) | `service_orders`, `service_order_containers`, `service_order_charges` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-005) / P12 / S09 |
| MOD-006 Service Order Status | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | O,F,R | `/service-orders` + `/service-charges` + `/financial-documents` (shared store) | `service_orders`, `service_order_component_rows`, `service_order_milestones` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-006) / P12 / S09 |
| MOD-007 Containers | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | O,R | `/service-orders` (embedded containers; report projection also exists) | `service_order_containers`, `service_orders`, `container_types` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-007) / P12 / S09 |
| MOD-008 Profitability | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/profitability` (current store projection); `/reports/service-order-profitability` also exists | `service_orders`, `quotation_revisions`, `service_order_charges`, `financial_documents`, `journal_entry_lines` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-008) / P12 / S09 |
| MOD-009 Financial Documents | [finance/documents/index.vue](../../frontend/app/pages/finance/documents/index.vue) | F | `/financial-documents` | `financial_documents`, `financial_document_lines`, `financial_document_sources`, `financial_document_postings`, `financial_document_allocations` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-009) / P08 / S05–S07 |
| MOD-010 Chart of Accounts | [finance/chart-of-accounts/index.vue](../../frontend/app/pages/finance/chart-of-accounts/index.vue) | F | `/chart-of-accounts` | `chart_of_accounts`, `journal_entry_lines` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-010) / P09 / S05,S08 |
| MOD-011 Financial Accounts | [finance/financial-accounts/index.vue](../../frontend/app/pages/finance/financial-accounts/index.vue) | F | `/financial-accounts` | `financial_accounts`, `chart_of_accounts` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-011) / P09 / S05–S08 |
| MOD-012 Journal Entries | [finance/journals/index.vue](../../frontend/app/pages/finance/journals/index.vue) | F | `/journal-entries` | `journal_entries`, `journal_entry_lines` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-012) / P09 / S08 |
| MOD-013 Accounting Periods | [finance/accounting-periods/index.vue](../../frontend/app/pages/finance/accounting-periods/index.vue) | F | `/accounting-periods` | `accounting_periods`, `journal_entries`, `audit_events` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-013) / P09–P10 / S08 |
| MOD-014 Posting Rules | [finance/posting-rules/index.vue](../../frontend/app/pages/finance/posting-rules/index.vue) | F | `/posting-rules` | `posting_rules`, `chart_of_accounts`, `fee_types` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-014) / P09 / S05,S08 |
| MOD-015 Revenue & Expense | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/income + /reports/expenses` | `journal_entries`, `journal_entry_lines`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-015) / P11 / S10 |
| MOD-016 Accounts Receivable | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/receivables` | `financial_documents`, `financial_document_allocations`, `journal_entry_lines` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-016) / P11 / S10 |
| MOD-017 Accounts Payable | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/payables` | `financial_documents`, `financial_document_allocations`, `journal_entry_lines` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-017) / P11 / S10 |
| MOD-018 General Ledger | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/general-ledger/generate` | `journal_entries`, `journal_entry_lines`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-018) / P11 / S10 |
| MOD-019 Trial Balance | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/trial-balance/generate` | `journal_entries`, `journal_entry_lines`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-019) / P11 / S10 |
| MOD-020 Profit & Loss | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/profit-loss` | `journal_entries`, `journal_entry_lines`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-020) / P11 / S10 |
| MOD-021 Balance Sheet | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/balance-sheet` | `journal_entries`, `journal_entry_lines`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-021) / P11 / S10 |
| MOD-022 Cash Flow | [reports/[area]/[slug].vue](../../frontend/app/pages/reports/[area]/[slug].vue) | R | `/reports/cash-flow` | `journal_entries`, `journal_entry_lines`, `financial_accounts`, `chart_of_accounts` | O,F,M | [requirements](../../docs/00-project/feature-inventory.md#mod-022) / P11 / S10 |
| MOD-023 Business Parties | [master-data/business-parties/index.vue](../../frontend/app/pages/master-data/business-parties/index.vue) | M | `/businessParties` | `business_parties`, `business_party_roles` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-023) / P03 / prerequisite slices,S11 |
| MOD-024 Party Roles | [master-data/party-roles/index.vue](../../frontend/app/pages/master-data/party-roles/index.vue) | M | `/partyRoles` | `party_roles` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-024) / P03 / prerequisite slices,S11 |
| MOD-025 Place Roles | [master-data/place-roles/index.vue](../../frontend/app/pages/master-data/place-roles/index.vue) | M | `/placeRoles` | `place_roles` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-025) / P03 / prerequisite slices,S11 |
| MOD-026 Trade Directions | [master-data/trade-directions/index.vue](../../frontend/app/pages/master-data/trade-directions/index.vue) | M | `/tradeDirections` | `trade_directions` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-026) / P03 / prerequisite slices,S11 |
| MOD-027 Container Types | [master-data/container-types/index.vue](../../frontend/app/pages/master-data/container-types/index.vue) | M | `/containerTypes` | `container_types` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-027) / P03 / prerequisite slices,S11 |
| MOD-028 Transport Types | [master-data/transport-types/index.vue](../../frontend/app/pages/master-data/transport-types/index.vue) | M | `/transportTypes` | `transport_types` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-028) / P03 / prerequisite slices,S11 |
| MOD-029 Transport Assets | [master-data/transport-assets/index.vue](../../frontend/app/pages/master-data/transport-assets/index.vue) | M | `/transportAssets` | `transport_assets` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-029) / P03 / prerequisite slices,S11 |
| MOD-030 Asset Identity Types | [master-data/asset-identity-types/index.vue](../../frontend/app/pages/master-data/asset-identity-types/index.vue) | M | `/transportAssetIdentityTypes` | `transport_asset_identity_types` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-030) / P03 / prerequisite slices,S11 |
| MOD-031 Capacity Units | [master-data/capacity-units/index.vue](../../frontend/app/pages/master-data/capacity-units/index.vue) | M | `/capacityUnits` | `capacity_units` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-031) / P03 / prerequisite slices,S11 |
| MOD-032 Fee Types | [master-data/fee-types/index.vue](../../frontend/app/pages/master-data/fee-types/index.vue) | M | `/feeTypes` | `fee_types` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-032) / P03 / prerequisite slices,S11 |
| MOD-033 Currencies | [master-data/currencies/index.vue](../../frontend/app/pages/master-data/currencies/index.vue) | M | `/currencies` | `currencies`, `currency_rates` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-033) / P03 / prerequisite slices,S11 |
| MOD-034 Document Types | [master-data/document-types/index.vue](../../frontend/app/pages/master-data/document-types/index.vue) | M | `/documentTypes` | `document_types` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-034) / P03 / prerequisite slices,S11 |
| MOD-035 Component Attributes | [configuration/component-attributes/index.vue](../../frontend/app/pages/configuration/component-attributes/index.vue) | M | `/component-attributes` | `component_attributes`, `component_group_attributes` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-035) / P04 / S03,S11 |
| MOD-036 Component Groups | [configuration/component-groups/index.vue](../../frontend/app/pages/configuration/component-groups/index.vue) | M | `/component-groups` | `component_groups`, `component_group_attributes` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-036) / P04 / S03,S11 |
| MOD-037 Component Tabs | [configuration/component-tabs/index.vue](../../frontend/app/pages/configuration/component-tabs/index.vue) | M | `/component-tabs` | `component_tabs`, `component_tab_groups` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-037) / P04 / S03,S11 |
| MOD-038 Configuration Versions | [configuration/versions/index.vue](../../frontend/app/pages/configuration/versions/index.vue) | M | `/configuration-versions` | `configuration_versions` | Q,O,F,A | [requirements](../../docs/00-project/feature-inventory.md#mod-038) / P04 / S03,S11 |
| MOD-039 User Management | [administration/users/index.vue](../../frontend/app/pages/administration/users/index.vue) | A | `/users` | `users`, `user_credentials`, `user_sessions`, `casbin_rule` | all (Casbin) | [requirements](../../docs/00-project/feature-inventory.md#mod-039) / P14 / S01,S11 |
| MOD-040 Roles & Permissions | [administration/roles/index.vue](../../frontend/app/pages/administration/roles/index.vue) | A | `/roles` | `casbin_rule` | all (Casbin) | [requirements](../../docs/00-project/feature-inventory.md#mod-040) / P14 / S01,S11 |
| MOD-041 Document Sequences | [administration/document-sequences/index.vue](../../frontend/app/pages/administration/document-sequences/index.vue) | F | `/document-sequences` | `document_sequences` | O,M,R,A | [requirements](../../docs/00-project/feature-inventory.md#mod-041) / P14 / S02–S08,S11 |
| MOD-042 Settings | [administration/system-settings/index.vue](../../frontend/app/pages/administration/system-settings/index.vue) | S | `/settings/app-config` | `app_settings` | A, integrations | [requirements](../../docs/00-project/feature-inventory.md#mod-042) / P14 / S11 |
| MOD-043 Archive | [administration/archive/index.vue](../../frontend/app/pages/administration/archive/index.vue) | X | `/archive` | `archive_records` | M,A,U | [requirements](../../docs/00-project/feature-inventory.md#mod-043) / P14 / S11 |
| MOD-044 Audit Logs | [administration/audit-logs/index.vue](../../frontend/app/pages/administration/audit-logs/index.vue) | U | `/audit-events` | `audit_events` | all | [requirements](../../docs/00-project/feature-inventory.md#mod-044) / P14 / S01,S08,S11 |

## Supporting paths and planned controls

- Printing: [components/print](../../frontend/app/components/print/) and
  [finance/printing.py](../../backend/app/modules/finance/printing.py); PLAN-0004 owns evidence.
- Shared APIs: [repositories](../../frontend/app/repositories/) and
  [endpoint constants](../../frontend/app/utils/constants/api-v1-endpoints.ts).
- Import/export, backup and Telegram: backend/app/modules/excel_io/, backup/, telegram/.
  These support existing pages; do not add business navigation.
- Smart Period Closing extends MOD-013. Basic periods/close/reopen exist;
  [P10](../../docs/04-implementation/phases/P10-period-closing.md) owns unfinished review,
  stale-review, warning and preserved-report requirements.
- Source/API registries and models win over a stale path here; verify moves and update only
  affected rows. Do not reread the full inventory for a small change.
