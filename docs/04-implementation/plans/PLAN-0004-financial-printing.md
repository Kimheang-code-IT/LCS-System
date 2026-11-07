# PLAN-0004 — Stored invoice and actual-container printing

Status: Completed for the current explicit printing request only.
Last updated: 2026-11-04. Task level: DEEP (read-only financial contract).
S01's existing unfinished acceptance and roadmap sequence are preserved.

## Scope and acceptance

Extend existing Financial Documents, print layouts and repositories. Consolidated output uses
all stored invoice lines once; printing cannot select a financially different partial tax
invoice. A selected actual-container Debit Note is a clearly labeled breakdown of its source
invoice, not a newly issued or numbered financial document. Shared/unassigned lines appear
only on the consolidated source. No schema, historical-record, posting or sequence changes.

Use configured company/party/branding information and the supplied logo as a fallback asset.
Never infer customer/container ownership from display names or container types. No automatic
10% VAT, current-rate repricing, or conversion of another document type to a Tax Invoice.
Draft output stays watermarked; missing/ambiguous associations and totals mismatches block.

## Controlled tasks

1. Inspect stored lines/container links, print/view-model/repository/branding paths and tests.
2. Add one protected GET print-data contract with Decimal reconciliation, exact source scope,
   actual-container choices and allowlisted public display fields. No writes/commits.
3. Reuse the template picker, preview, header/footer/table/bank/signature components; add
   searchable actual-container selection, persistent errors and direct-route protection.
4. Update A4 templates, stored-currency formatting and optional-data layout; preserve legacy
   quotation/SO/charge printing and do not call unbilled statements official tax invoices.
5. Test scope/denial/mismatch/read-only regressions, frontend calculations/mapping, UI/PDF
   layout and Khmer/font/logo readiness; run affected lint/typechecks/contracts and reviewer.

## Verification plan

Backend synthetic fixtures: two same-type physical containers (150+20 vs 180+25), shared fee,
VAT/discount/zero/non-USD cases, missing/stale/foreign container/source/party, missing document,
denied caller and repeated reads with unchanged business/journal/sequence balances.
Frontend: source-only mapping, selection and query tampering, stable numbers, no 10% fallback,
draft/ineligible tax titles, empty contacts/dates, asset failures, long/multipage descriptions.
Render real Vue layouts with synthetic data to A4 PDF and inspect pages/fonts/tables/totals.
Use no production data or notifications. PostgreSQL locking is not changed by read-only work.

## Executed verification (2026-11-04)

| Command / check | Observed result |
|---|---|
| backend: uv run --no-sync pytest -q tests/test_financial_printing.py | 11 passed, 9 warnings in 26.67s; source scope, two same-type containers, shared fee, tax classification, reconciliation, ownership, draft/discount/JPY-to-USD precision, status and 401/403/404 |
| backend: uv run --no-sync pytest -q tests/test_financial_printing.py -k single_container | Additional case: 1 passed, 11 deselected in 3.26s; one-container auto-selection, zero lines, no-container refusal; 12 focused cases now verified across these runs |
| backend: uv run --no-sync pytest -q tests/test_financial_documents_module.py tests/test_multi_currency.py | 37 passed, 12 warnings in 94.33s |
| backend: uv run --no-sync ruff check app/modules/finance/printing.py app/modules/finance/router.py tests/test_financial_printing.py | All checks passed; repeated test-file Ruff after final added case also passed |
| backend: test_frontend_api_contract.py + test_route_authorization.py | Passed in initial combined run; printing fixture failures in that run were corrected and focused cases rerun above |
| frontend: pnpm test | 816 passed in 97 files before two later query/base-precision regressions were added; these two passed in focused rerun |
| frontend: pnpm exec vitest run tests/financial-print.spec.ts tests/print-navigation.spec.ts tests/i18n-locales.spec.ts | 23 passed in 3 files; earlier complete print compatibility set: 43 passed in 6 files |
| frontend: pnpm lint; pnpm i18n:check | Passed; km/zh each 3341/3341 keys; 49 existing identical translations reported |
| frontend: pnpm typecheck | Passed after final layout/number formatting changes; final touched DebitNoteLayout/print layout ESLint passed |
| node scripts/feature-status.mjs | FIN and shared printing scope reviewed; existing unrelated dirty-tree groups preserved |
| Read-only reviewer | Both P2 findings fixed and rechecked; no remaining blockers in scoped changes |

Existing warnings: SQLite metadata FK ordering cycle and deprecated Starlette 422 constant.
No PostgreSQL mutation/concurrency behavior changed or claimed verified by these SQLite tests.
Initial fixture/setup, import formatting and query typing failures were fixed before the passing
runs. No authorization or accounting assertion was weakened.

## UI and PDF evidence

Synthetic APIs only; no real login, business data mutation or financial posting. Real Nuxt/Vue
components were exercised through Chromium and the existing preview. Same-type actual box
MSCU7654321 selects stored 180+25=205; consolidated output returns 385 including the shared 10.
The searchable selector is by physical number. No selection disables Print. Switching templates
through the UI removes containerId and restores all five lines. Broken logo blocks window.print;
a 422 reconciliation failure displays the server's message and disables Print.

Artifacts in output/browser/: consolidated-invoice.pdf (1 A4 page), container-debit-note.pdf
(1 A4 page), long-invoice.pdf (4 A4 pages, 60 rows). All continuation headers and final Item 60
were verified with PDF extraction, and raster pages inspected for Khmer, logo, wrapping, totals,
signatures and footer. All page dimensions are approximately 595 x 842 points; no blank trailing
page remains. Named-page CSS previously produced a footer-only page; a common A4 page rule in
the existing print layout fixes it. Final clean-server render reported no application errors;
intentional failure checks naturally log the refused image/422 requests. Locale-loading fallback
warnings occur before the print-ready locale load. Physical printers, Edge/Firefox/Safari and
extreme rows taller than a page remain unverified.

## Changed files and reuse

Paths below are repository-relative and list only this task's changes; preexisting dirty edits
in shared files were preserved.

- Backend: app/modules/finance/printing.py (new read-only projection), finance/router.py
  (protected GET), tests/test_financial_printing.py (new).
- Frontend print: components/print/DocumentPreview.vue, TemplateModal.vue, TaxInvoiceLayout.vue,
  DebitNoteLayout.vue, IssuerHeader.vue, LinesTable.vue; layouts/print.vue;
  composables/print/usePrintBilingual.ts.
- Frontend integration: components/freight/DocumentView.vue;
  composables/freight/useDocumentActions.ts; repositories/contracts/lcs.ts,
  repositories/http/lcs.ts; utils/constants/api-v1-endpoints.ts;
  utils/freight/print-model.ts, print-navigation.ts, financial-print.ts (new adapter).
- Assets/locales/tests: public/lcs-invoice-logo.jpg (supplied unchanged), i18n/locales/en.json,
  km.json, zh.json; tests/financial-print.spec.ts (new), print-navigation.spec.ts.
- Documentation: this plan, master-plan.md, phase-tracker.md, project-status-checklist.md,
  00-project/feature-status.md, 01-architecture/api-design.md,
  02-business/accounting-and-posting.md and ui-ux-standards.md.

Reused components: existing template modal, preview, tax/debit layouts, issuer header, lines
UTable, metadata, totals, bank, signature and footer blocks; existing finance repository,
localization, Casbin guard and shared API error normalizer. No new UI component or dependency.
The new backend projection and frontend adapter fill the missing stored-source contract.
No database schema/migration, record rewrite, posting/numbering/settlement logic change.

## Limits and manual checklist

Issuer/customer display details still use current linked master data because this schema has
no immutable print identity snapshot. Exactly one active Company is required. Bank numbers are
stored masked; ambiguous bank configuration is omitted. Tax title needs saved TAX_INVOICE
classification. Shared fees remain consolidated only. Batch export is not added. Browser PDF
output uses the existing print dialog; cancelling or a browser/OS PDF-save failure changes no
business data. Unsupported precision amount words are omitted rather than invented.

1. Open a saved customer invoice in Financial Documents and choose Print; check its original
   number, company, customer, totals, discount/tax and currency against the source.
2. Select Debit Note, search each actual container number (including two of the same type),
   and verify only its billed lines; compare consolidated shared charges once.
3. Return to Invoice/Tax Invoice and verify the container filter clears; draft stays watermarked.
4. Preview empty contacts/dates, long Khmer/English descriptions and multiple pages; save A4 PDF.
5. Try an unauthorized caller, mismatched source totals or broken logo; verify clear refusal.
   Print repeatedly and confirm document balances, status, sequences and journal counts stay unchanged.

## Handoff

- Completed: implementation, scoped automated checks, reviewer fixes/recheck, synthetic browser
  assertions, PDF raster verification and directly affected documentation.
- Remaining within this request: none. Cross-browser/physical-printer acceptance and historical
  print-identity snapshots are explicit limits above, not claims of release readiness.
- Resume: follow S01/PLAN-0002's existing Handoff only when the user requests continuation;
  do not automatically start unrelated phases. Full P08 and S01 remain unfinished.
- Commit status: uncommitted; no commit authorized. No deployment or production-data use.
