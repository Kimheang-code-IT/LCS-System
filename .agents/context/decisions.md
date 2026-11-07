# LCS decision lookup

Verified means source/config inspection on the date shown, not executed business acceptance.
These pointers do not replace canonical requirements. Update only affected facts; mark stale
or conflicting memory explicitly. Sources below are repository-relative.

| ID | Decision / rationale | Source | Status | Verified |
|---|---|---|---|---|
| CTX-01 | Preserve single-tenant monolith and 44 pages; reuse existing boundaries | docs/00-project/requirements.md; backend/app/api/v1/router.py; frontend/nuxt.config.ts | Approved; source-inspected | 2026-11-04 |
| CTX-02 | Casbin alone decides access; protected admin and current multi-role composition remain | docs/01-architecture/security-and-permissions.md; backend/app/core/authorization/ | Approved; source-inspected; remaining action acceptance is S01 | 2026-11-04 |
| CTX-03 | One quotation may source multiple intentional SOs; a retried keyed command must not duplicate an order | docs/02-business/accounting-and-posting.md; backend/app/modules/operations/service.py (save_service_order) | Approved; keyed replay code exists; full S02 source/payload/concurrency acceptance open | 2026-11-04 |
| CTX-04 | SO pricing is an independent captured/overridden snapshot; actual containers are individually entered physical records | docs/02-business/business-rules.md; backend/app/modules/operations/models.py; PLAN-0002 Handoff | Approved; source-inspected | 2026-11-04 |
| CTX-05 | SO Save/Finish is operational; Finish does not post or require settlement | docs/02-business/accounting-and-posting.md; backend/app/modules/operations/service.py | Approved; implementation exists; full S03 acceptance open | 2026-11-04 |
| CTX-06 | Charge issue/draft conversion do not recognize revenue; posting rules control balanced financial events | docs/02-business/accounting-and-posting.md; backend/app/modules/finance/posting_rules.py; backend/app/modules/finance/service.py | Approved; preserve atomicity, Decimal, idempotency, history | 2026-11-04 |
| CTX-07 | Custom period start/end dates; derived year/month; basic close/reopen exists | backend/app/modules/finance/service.py (create_period, close_period, reopen_period); docs/04-implementation/phases/P10-period-closing.md | Source-inspected; rich closing review/report evidence NOT completed | 2026-11-04 |
| CTX-08 | Invoice consolidates stored billed lines once; container Debit Note is a breakdown by actual ID, excludes shared fees and keeps original number | backend/app/modules/finance/printing.py; docs/04-implementation/plans/PLAN-0004-financial-printing.md | Implemented with scoped test/PDF evidence; no new receivable | 2026-11-04 |
| CTX-09 | Tax title needs saved TAX_INVOICE classification; no invented VAT/current-rate repricing; printing read-only | docs/02-business/accounting-and-posting.md#stored-invoice-and-container-printing; backend/app/modules/finance/printing.py | Implemented; not a regulatory compliance certificate | 2026-11-04 |
| CTX-10 | Git-backed context is default memory; graph facts cannot override newer approved docs or store customer finance/secrets | docs/03-development/agent-tooling.md; current agent-setup request | Approved workflow; optional MCPs not activated | 2026-11-04 |

Conflict queue: older inventory/legacy descriptions may still claim conversion is ungated,
one SO per quotation, mandatory Send/Accept or no Finish. Current lifecycle and PLAN-0002's
Handoff supersede those examples; recheck current callers/tests during implementation.
P10 targets exceed basic close/reopen. Do not claim those gaps resolved or rewrite historical
records during setup. Detailed decisions belong in docs/01-architecture/architecture-decisions.md.
