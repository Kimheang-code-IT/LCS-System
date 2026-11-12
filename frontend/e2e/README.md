# Browser acceptance tests

Reusable Playwright Test specs for the critical LCS workflows. They drive the
running SPA (real backend, real database), so every run creates records whose
text is prefixed `E2E`.

## Run

```powershell
cd frontend
$env:E2E_USER='<user>'
$env:E2E_PASSWORD='<password>'
pnpm exec playwright test            # or: pnpm e2e
```

`E2E_BASE_URL` defaults to `http://localhost`. Never point it at production:
the specs write quotations, service orders and financial documents.

Sign-in is repeated per test on purpose — refresh tokens are single-use, so a
shared `storageState` breaks after the first test rotates it.

## Coverage

| Spec | Workflow |
| --- | --- |
| `quotations.spec.ts` | required-field validation, create, route stop, pricing line + total, empty-line refusal, convert to Service Order, draft lifecycle |
| `service-orders.spec.ts` | header number on in-app navigation, add container, add service charge, finance summary |
| `finance.spec.ts` | draft debit note, post (balanced journal), reverse with reason |
| `finance-edge.spec.ts` | multi-line invoice totals, idempotent re-post, supplier bill → AP, partial receipt |
| `master-data.spec.ts` | customer + supplier party creation, required-field validation |
| `access-control.spec.ts` | viewer account: no create control, create-form deep link and admin pages redirected |
| `print-reports.spec.ts` | quotation print/PDF view, trial balance debit = credit |
| `reports.spec.ts` | every finance/operations report renders with no server error |

## Artifacts

`test-results/` (traces and failure screenshots) and `e2e/.report/` (HTML
report) are git-ignored.
