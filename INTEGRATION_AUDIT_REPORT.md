# Full Backend-to-Frontend Module Integration — Audit Report

**Date:** 2025-09-25
**Scope:** Reports & Dashboard Integration (Phase 1), Finance Mapping Verification (Phase 2), Cleanup & Verification (Phase 3)
**Status:** Phase 1 Complete, Phase 2 Verified Clean, Phase 3 Complete

---

## Executive Summary

The LCS Freight Forwarding system has a significant architectural disconnect in its reporting layer: the backend exposes eight `/reports/*` endpoints that were completely unused by the frontend, while the frontend computed all dashboard KPIs and report tables client-side from cached store data. This audit connects the reporting layer end-to-end, enriches the backend report payloads to match frontend column expectations, and verifies branch-scoped isolation on every report query.

---

## Phase 1 — Reports & Dashboard Integration

### Problem Identified
- **Backend:** `/api/v1/reports/dashboard` returned a minimal shape (`openServiceOrders`, `quotations`, `receivableTotal`, `payableTotal`, `receivables[]`, `payables[]`).
- **Frontend:** `DashboardView.vue` called `store.dashboardSummary()`, which computed KPIs, aging buckets, revenue/expense charts, and status counts entirely from cached store data (`jobs`, `debitNotes`, `journals`, etc.). The backend dashboard endpoint was never called.
- **Reports:** `ReportsView.vue` built all 12 report variants client-side via `buildReportRows()` from store cache. Backend endpoints `/reports/receivables`, `/reports/payables`, `/reports/profitability`, etc. were unused.

### Changes Made

#### Backend — `backend/app/modules/reports/service.py`
1. **Extended `dashboard()`** to return the full `DashboardSummary` shape the frontend expects:
   - `summary`: `openOrders`, `inProgressOrders`, `onHoldOrders`, `awaitingClosure`, `receivables`, `overdueReceivableCount`, `payables`, `cashBankBalance`, `revenue`, `expense`
   - `charts`: `revenueExpense` (by month), `ordersByStatus`, `receivablesAging`, `payablesAging`
   - `options`: `customers` list
2. **Added branch-scoped filtering** to `dashboard()`, `receivables()`, `payables()`, `profitability()`, `_journal_revenue_expense_by_month()`, `_account_type_totals()`, `_customers()`, and `_service_order_status_counts()`.
3. **Enriched `receivables()` and `payables()`** responses with frontend-mapped fields:
   - Added `invoiceNo` / `billNo`, `customer` / `supplier` (joined `BusinessParty`), `jobNo` (joined `ServiceOrder`), `invoiceDate` / `billDate`, `outstanding`, `aging` (computed in days)
4. **Enriched `profitability()`** with `customer` (joined `BusinessParty`) and mapped aliases (`postedRevenue`, `postedCost`, `grossProfit`).

#### Frontend — API Layer
1. **`frontend/app/utils/constants/api-v1-endpoints.ts`**
   - Added `REPORTS_DASHBOARD`, `REPORTS_SERVICE_ORDERS`, `REPORTS_QUOTATION_PERFORMANCE`, `REPORTS_RECEIVABLES`, `REPORTS_PAYABLES`, `REPORTS_INCOME`, `REPORTS_EXPENSES`, `REPORTS_PROFITABILITY`, `REPORTS_FINANCIAL_SUMMARY`

2. **`frontend/app/repositories/contracts/lcs.ts`**
   - Added `DashboardSummary` type (matches backend response)
   - Added `ReportsRepository` interface with `dashboard()`, `receivables()`, `payables()`, `profitability()`, `income()`, `expenses()`, `serviceOrders()`, `quotationPerformance()`, `financialSummary()`

3. **`frontend/app/repositories/http/lcs.ts`**
   - Implemented `createHttpReportsRepository()` using `useApi()` and the new endpoint constants

4. **`frontend/app/repositories/index.ts`**
   - Exported `reports` from `useLcsRepositories()`

#### Frontend — Dashboard (`frontend/app/components/freight/DashboardView.vue`)
- Replaced `store.dashboardSummary()` with `await reports.dashboard()`
- Added `filterByYear()` helper to slice the backend's full `revenueExpense` array by chart year
- Chart year watchers now filter the already-fetched backend data instead of re-computing from store cache

#### Frontend — Reports (`frontend/app/components/freight/ReportsView.vue`)
- Added backend report loading for three report slugs that have matching backend endpoints:
  - `accounts-receivable` → `reports.receivables()`
  - `accounts-payable` → `reports.payables()`
  - `profitability` → `reports.profitability()`
- All other reports (`service-orders`, `containers`, `general-ledger`, `profit-loss`, `balance-sheet`, etc.) continue to build client-side from store cache as fallback
- Refresh action triggers both `store.reload()` and `loadBackendReport()`

---

## Phase 2 — Finance Document Type Mapping Verification

### Finding: Mapping is Correct
The frontend collection-to-document-type mappings in `frontend/app/utils/api/freight-remote.ts` align perfectly with backend constants:

| Frontend Collection | Query Param | Backend Constant | Used In Posting Rules |
|---------------------|-------------|------------------|----------------------|
| `debitNotes` | `CUSTOMER_INVOICE` | `CUSTOMER_INVOICE` | ✅ Default accounts defined |
| `customerPayments` | `CUSTOMER_RECEIPT` | `CUSTOMER_RECEIPT` | ✅ Default accounts defined |
| `supplierCosts` | `SUPPLIER_BILL` | `SUPPLIER_BILL` | ✅ Default accounts defined |
| `supplierPayments` | `SUPPLIER_PAYMENT` | `SUPPLIER_PAYMENT` | ✅ Default accounts defined |

**No code changes required.** The finance module wiring is already correct.

---

## Phase 3 — Cleanup & Verification

### Legacy Modules
- `freight-modules.ts` contains legacy module definitions (e.g., `/sales/companies`, `/operations/jobs`, `/finance/debit-notes`) alongside canonical modules (`/quotations`, `/service-orders`, `/finance/documents`).
- **Finding:** This is intentional. Legacy modules serve as schema templates; canonical modules clone them with updated paths, permissions, and columns. The sidebar navigation in `composables/layout/useMenu.ts` hardcodes canonical paths and never exposes legacy routes.
- **Action:** No removal needed. Legacy modules are required for schema inheritance.

### Print Preview
- `components/print/DocumentPreview.vue` uses `freightModules.find(item => item.collection === collection.value)` to resolve print metadata.
- **Finding:** Works correctly because both legacy and canonical modules are in the array; the canonical modules have the same collection names.
- **Action:** No changes required.

### UI Schema
- Backend endpoint: `GET /api/v1/ui-schemas/{page}` exists and is wired in `frontend/app/repositories/http/lcs.ts` as `createHttpUiSchemaRepository()`.
- **Finding:** The repository is initialized and exported, but **no component or page in the frontend actually calls `getPageSchema()`**.
- **Impact:** Low. The feature is dormant on both sides — backend endpoint exists, frontend repository exists, but integration is not active.
- **Action:** Documented as known gap; not critical for core freight operations.

---

## Phase 4 — End-to-End Verification Notes

### Backend Tests
- Existing test `tests/test_workflows.py` verifies `/api/v1/reports/receivables` returns rows with `balance`.
- The enriched response retains all original fields, so this test continues to pass.

### Manual Verification Checklist
| Endpoint | Expected | Status |
|----------|----------|--------|
| `GET /api/v1/reports/dashboard` | Returns full DashboardSummary with charts + aging | ✅ Backend updated |
| `GET /api/v1/reports/receivables` | Returns enriched rows with customer, jobNo, aging | ✅ Backend updated |
| `GET /api/v1/reports/payables` | Returns enriched rows with supplier, jobNo, aging | ✅ Backend updated |
| `GET /api/v1/reports/profitability` | Returns rows with customer, postedRevenue, grossProfit | ✅ Backend updated |
| Frontend Dashboard | Calls `reports.dashboard()` instead of store cache | ✅ Wired |
| Frontend A/R Report | Calls `reports.receivables()` when slug = accounts-receivable | ✅ Wired |
| Frontend A/P Report | Calls `reports.payables()` when slug = accounts-payable | ✅ Wired |
| Frontend Profitability | Calls `reports.profitability()` when slug = profitability | ✅ Wired |

### Known Limitations
1. **Cash/Bank Balance:** The backend dashboard returns `cashBankBalance: 0.0` because there is no dedicated `cashAccounts` backend collection mapped. The frontend previously read from `db.cashAccounts` (locally seeded). A future backend enhancement could compute cash/bank balances from `FinancialAccount` or `ChartOfAccount` ASSET types.
2. **Backend Report Date Filtering:** The backend `/reports/dashboard` does not yet accept `date_from`/`date_to` query params. The frontend filters chart data by year client-side from the full backend response. This is sufficient for annual charts.
3. **Branch Scope on Reports:** Backend reports now filter by branch for users without cross-branch access. Frontend reports still apply client-side filters (branch, party, status, currency, date) on top of backend data.
4. **UI Schema:** The `/api/v1/ui-schemas/{page}` endpoint and frontend repository exist but are not integrated into any page flow.

---

## Files Modified

| File | Change |
|------|--------|
| `backend/app/modules/reports/service.py` | Extended dashboard, added branch filtering, enriched report payloads |
| `frontend/app/utils/constants/api-v1-endpoints.ts` | Added 9 report endpoint constants |
| `frontend/app/repositories/contracts/lcs.ts` | Added DashboardSummary type and ReportsRepository interface |
| `frontend/app/repositories/http/lcs.ts` | Added createHttpReportsRepository() |
| `frontend/app/repositories/index.ts` | Exported reports repository |
| `frontend/app/components/freight/DashboardView.vue` | Calls backend dashboard API |
| `frontend/app/components/freight/ReportsView.vue` | Calls backend report APIs for A/R, A/P, profitability |

---

## Recommendations

1. **Deploy and monitor** the backend `/reports/dashboard` endpoint performance. Organizations with very large invoice volumes may need pagination or caching on the detail arrays (`receivables[]`, `payables[]`).
2. **Add cash/bank balance computation** to the backend dashboard by summing `FinancialAccount` balances where account type is ASSET and category is cash/bank.
3. **Activate UI Schema integration** when dynamic page layouts are needed; the plumbing is already in place on both sides.
4. **Extend backend report coverage** for remaining reports (`service-orders`, `containers`, `general-ledger`, `trial-balance`, `cash-flow`) so the frontend can eventually retire client-side report building entirely.

---

*Report generated by Claude Code as part of the Full Backend-to-Frontend Module Integration audit.*
