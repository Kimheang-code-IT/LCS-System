# ERP acceptance and traceability

[Design brief](../00-project/requirements.md) owns stable scope IDs; [target requirements](../02-business/accounting-and-posting.md)
adds detailed IDs. This matrix assigns implementation/evidence responsibility without copying
a second specification. [Inventory](../00-project/feature-inventory.md) supplies all 44 page criteria.

| Requirement | Owning document / pages | Package / slice | Verified source discovery | Required acceptance evidence |
|---|---|---|---|---|
| LCS-001,014 | Inventory MOD-001–044; design brief | P01–P14 / S01–S11 | frontend/app/pages; config/freight-modules.ts, lcs-reference-modules.ts, freight-reports.ts | Every applicable page action/API/filter/form accounted for; explicit N/A and limits |
| LCS-002,009,013 | Security; MOD-039,040,043,044 and every protected action | P14,P15 / S01 + each slice | core/permissions.py, core/authorization, auth + status routers | Allowed/denied direct API/browser; session/logout/replay; protected administrator; no side effects on denial |
| LCS-003; LCS-QUO-001 | Lifecycle; MOD-002 | P05 / S02 | quotations/service.py convert_revision, create_revision; test_quotation_reuse.py | Two intentional SOs allowed; same-key concurrent replay creates one; source/payload mismatch refused |
| LCS-004; LCS-SO-001 | Lifecycle; MOD-003 | P04,P06 / S02–S03 | operations/service.py save_service_order, finish_service_order, component_tabs.py | Copied/overridden prices stable; actual boxes manual; valid Finish locks operations without ledger effect |
| LCS-004,005; LCS-CHG-001 | Lifecycle; MOD-004,009 | P07,P08 / S04–S05 | operations/service.py issue_charge/charge_to_invoice; finance/service.py invoice conversion | No journal at issue/conversion; one source-linked draft under repeated/racing billing paths |
| LCS-005,006 | Data invariants; MOD-009–014 | P08,P09 / S05,S07,S08 | finance/posting.py, posting_rules.py, service.py; PostgreSQL guards | Balanced atomic unique journals; rollback; immutable original/rate history; safe linked reversal |
| LCS-007 | Data model; MOD-009,016,017 | P08 / S06–S07 | finance/service.py allocate_payment, models.py allocations | Partial/full and multi-target payments; over-allocation/type/party/currency/race refusal; AR/AP reconciliation |
| LCS-PER-001; LCS-006 | Lifecycle/target; MOD-013 | P09 / S08 | finance/service.py create_period/resolve_period/update_period; AccountingPeriod | No user Year; valid custom dates; no overlap; approved missing-period policy; no generic state/closed-post bypass |
| LCS-CLS-001–003 | Smart closing specification; MOD-013 | P10 / S08,S10 evidence | finance close/reopen/status paths; report baseline; existing audit/storage | Check severities/drill-down; stale review; close-vs-post serialization; rollback; authorized reasoned reopen and preserved reports/history |
| LCS-008; LCS-RPT-001 | Report contract; MOD-005–008,015–022 | P11,P12 / S09–S10 | reports/service.py, ledger_reports.py, engine.py; freight-reports.ts | Declared dates/currency, posted reversal cutoff, full export/page totals, controls/BS/cash reconciliation, empty and denied states |
| LCS-AUTO-001 | Smart automation; MOD-041 and document producers | P14.1 + P05–P09 / S02–S08 | core/sequences.py; document_sequences and keyed command paths | Concurrent unique numbers; preview not allocation; retry returns original operation |
| LCS-AUTO-002,003 | Precision/population contract; MOD-002–004,009 | P05–P09 / S02–S08 | core/fx.py, quotation _money, finance amounts and source copy | No saved override overwritten; defined rounding/precision and positive rate; browser preview equals persisted source |
| LCS-AUTO-004 | Report/dashboard contract; MOD-001,008,016,017 | P08,P11–P13 / S06–S10 | reports dashboard/receivables/payables/profitability | Derived settlement/overdue and separated profit layers reconcile at cutoff; per-metric access enforced |
| LCS-CFG-001 | Architecture/target; MOD-035–038 | P04 / S03,S11 | master_data config_snapshot/config_versions/component_config; operations/component_tabs | Publish/rollback concurrency; old SO keeps version, required types/values and refs |
| LCS-UI-001; LCS-010,011,016 | Coding/UI standards; every relevant page | P02 + owners / producing slices,S13 | shared forms/tables/reference selectors; print/locales | Persistent field/refusal errors, loading/empty/focus/draft preservation, en/km/zh and applicable bilingual print |
| LCS-012 | Operations runbook | P16 / S12–S13 | infrastructure restore workflow and coordinated DB/file/config sets | Authorized isolated restore; source/file/ledger integrity and measured recoverable point/time |
| LCS-015,016,019 | Design brief | P16 / S13 | e2e config and accessibility/browser workflows | Chrome/Edge/Firefox/Safari + keyboard/labels/focus/contrast; approved mobile/target limits; evidence, not assumptions |

Source paths in the discovery column are relative to backend/app unless frontend/test/infra
is stated. They identify where to inspect, not a test run or exact line-number promise.

## Evidence and acceptance boundaries

Current task: documentation checks only. All runtime rows remain unverified on this snapshot;
historical evidence is in the existing plan/checklist. No whole page or implementation package
is marked complete here. Current requirements supersede obsolete one-order/Send/Accept-only
examples, while legacy data remains readable. Findings DOC-01–DOC-11 in the audit remain
test/decision inputs, not completed defects or permission to implement.

A row passes only with the owning slice's scoped criteria plus handbook DoD. Exact environment/
revision/command/result/skips and reviewer are required where applicable. A financial journal
test on SQLite alone never proves PostgreSQL deferred constraints, locking or concurrent close.
No legal/statutory compliance or production readiness is inferred from report formulas.

