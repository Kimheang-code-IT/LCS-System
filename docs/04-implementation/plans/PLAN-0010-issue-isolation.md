# PLAN-0010 — S04 issue isolation (P07 task 07.2)

## Metadata

Slice: S04 — Service Charge to Financial Draft (P07 task 07.2)
Status: Completed
Last updated: 2026-11-05
Task level: STANDARD (one-line backend isolation fix + test-shape updates; permission-gate alignment)

## Objective and requirement IDs

Close the demonstrated 07.1 mismatch: issuing a Service Charge must not create a Finance
Document or Journal Entry; conversion stays the explicit, separately authorized command.
Approved behavior: [workflows.md](../../02-business/workflows.md) §9 steps 9–10;
requirements LCS-004, LCS-005; [P07](../phases/P07-service-charges.md).

## Previous behavior (verified in the working tree before editing)

`issue_charge` (operations/service.py) called
`finance_service.create_invoice_from_charge(..., commit=False)` after setting ISSUED, so
every issue silently produced a `CUSTOMER_INVOICE` DRAFT (`uq_fin_doc_sources` source row
`SERVICE_ORDER_CHARGE`), even though the same conversion already exists as
`POST /service-charges/{id}/create-finance-invoice` under
`service_charge.convert_to_invoice`. The browser UI (DocumentView/WorkspaceView)
already modeled the *approved* workflow — for an ISSUED charge without a linked document
it shows "Create Finance Invoice" only with the convert permission — so that branch was
dead while the backend bypassed it. Zero code path wrote journals at issue.

## Corrected behavior

- **Issue** (`POST /service-charges/{id}/issue`, `service_charge.submit`): unchanged
  validations (existence, DRAFT/ISSUED state, ≥1 positive line, positive total), same
  `SELECT … FOR UPDATE` row lock; sets ISSUED; commits the operational change; `record_
  charge_status_change` writes the `SERVICE_CHARGE_ISSUED` audit event with both statuses.
  The response carries **no** `financialDocumentId`/`invoiceNo` when nothing is converted.
- **Convert** (`POST /service-charges/{id}/create-finance-invoice`,
  `service_charge.convert_to_invoice`): unchanged; creates one DRAFT draft (or returns the
  existing linked document) with Decimal amounts copied from the charge and the invoice's
  own approved rate for its currency; no journal.
- **Post** (`POST /financial-documents/{id}/post`): unchanged — remains the only
  journal-producing step (balanced/atomic; period and rule checks untouched).
- **UI gate alignment** (DocumentView): the Issue button now checks
  `service_charge.submit` — the code the route actually enforces (it previously checked
  `service_charge.issue`, so a custom issue-only account saw a button that answered 403).
  Standard role templates are unaffected (the `finance.service_charges.submit` aggregate
  grants both codes). No weakening: an account that would be refused silently now simply
  does not see the action.

## Files changed

- `backend/app/modules/operations/service.py` — issue_charge no longer calls
  `create_invoice_from_charge` (the auto-prepare call removed; comment updated to §9).
- `frontend/app/components/freight/DocumentView.vue` — Issue action gate →
  `service_charge.submit`; unrelated pre-existing duplicate import of
  `~/utils/freight/document-tabs` merged (eslint import/no-duplicates).
- Tests updated to the approved workflow (**no assertion weakened**; each removed
  assumption is replaced by its now-correct expectation):
  - `tests/test_finance_automation.py`: `test_issued_charge_automatically_creates_one_
    draft_invoice_and_report` → `test_issuing_is_isolated_and_conversion_creates_one_draft`
    (issue creates no document/journal, audit event asserted, explicit convert creates the
    single draft, replay + re-issue idempotent, reports flow unchanged); new
    `test_issue_permission_cannot_convert_and_post_permission_is_separate`; the
    fee-specific posting-rule test now converts explicitly (name updated); the
    draft-conversion 409 + issuance-immutability test unchanged and still passing.
  - `tests/test_charge_tax_round_trip.py`, `tests/test_multi_currency.py`,
    `tests/test_reporting_values.py`: insert the explicit convert command between issue
    and the invoice assertions (tax/currency/order-invoice expectations unchanged).

## Existing data compatibility

Historical drafts created by the old auto-issue behavior stay untouched: soft links
(`financial_document_sources`) unchanged, statuses/balances never rewritten. A charge
already linked to a document shows View (not Create) — `serviceChargeInvoiceAction`
returns 'view' whenever `financialDocumentId` is set, regardless of how the draft was
created. An ISSUED charge without a draft (possible only from data predating the
auto-creation or from manual correction) shows Convert for authorized users. No data
migration.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Issue isolation + explicit conversion + posting + permission isolation + reports/ledger + audit event | `uv run --no-sync pytest -q tests/test_finance_automation.py tests/test_charge_tax_round_trip.py tests/test_multi_currency.py tests/test_reporting_values.py tests/test_created_by.py tests/test_job_finance_entries.py tests/test_workflows.py tests/test_financial_documents_module.py` | 82 passed / 0 failed, 2026-11-05 (incl. the two rewritten/new tests) |
| Frontend gates | `pnpm exec eslint app/components/freight/DocumentView.vue`; `pnpm typecheck`; `pnpm exec vitest run` | eslint 0; typecheck 0; 825 passed (99 files), 2026-11-05 |
| Dev compose (both images rebuilt, healthy; no DB migration needed) | `docker compose -f infrastructure/docker-compose.yml up -d --build backend frontend` | healthy, 2026-11-05 |

Assertions proven per §10 checklist: (1) DRAFT→ISSUED + audit event (`SERVICE_CHARGE_ISSUED`
on entity `service_charge`); (2) zero Finance Documents and zero JournalEntryLines after
issue (DB-queried); (3) issue-only holder can issue but convert → 403; (4) explicit
conversion creates one DRAFT; conversion creates zero journals; (5) authorized posting
creates the balanced journal (debit=credit=110 asserted) — the only journal step;
(6) replay returns the same document; (7) historical linked documents remain accessible.

## Acceptance criteria (07.2)

All §13 points met; issue writes no finance state; conversion requires separate Casbin
authorization; posting separate; focused suites pass; docs updated.

## Handoff

- Task 07.2 closed 2026-11-05. S04 remains IN PROGRESS. Next: **07.3 bill-once race** —
  **executed 2026-11-05** — [PLAN-0011](PLAN-0011-bill-once-conversion-idempotency.md)/E30:
  `FOR UPDATE` conversion + partial unique source index + idempotency keys; PG race 4 passed.
- Limits: browser journey for issue/convert not run (API-level evidence; the UI was
  verified read-only — no layout changed). `Idempotency-Key` remains accepted-but-ignored
  on issue/convert (07.3). No commit authorized yet.
