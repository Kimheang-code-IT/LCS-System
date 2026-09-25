# What Was Done — Backend-to-Frontend Integration Sprint

This document is a plain-English summary of the changes made to connect the LCS Freight Forwarding backend APIs to the frontend UI.

---

## The Big Picture

The frontend was computing **all dashboard KPIs and financial reports entirely in the browser** from locally cached store data. Meanwhile, the backend already had a full `/reports/*` API suite sitting unused. We wired those backend endpoints into the frontend, enriched the backend responses so the frontend could render them without changing its component logic, and verified branch-level security filtering everywhere.

---

## Backend Changes

### `backend/app/modules/reports/service.py`

This is the only backend file we changed. Here's what happened inside it:

#### 1. Dashboard endpoint now returns everything the frontend needs

Before, `GET /api/v1/reports/dashboard` returned a tiny JSON blob:
```json
{
  "openServiceOrders": 5,
  "quotations": 12,
  "receivableTotal": 3400.00,
  "payableTotal": 1200.00
}
```

Now it returns the full `DashboardSummary` shape the frontend expects — KPI cards, monthly revenue/expense chart points, receivables/payables aging buckets, and a customer list:
```json
{
  "generatedAt": "2025-09-25",
  "summary": {
    "openOrders": 5,
    "inProgressOrders": 3,
    "onHoldOrders": 1,
    "awaitingClosure": 2,
    "receivables": 3400.00,
    "overdueReceivableCount": 1,
    "payables": 1200.00,
    "cashBankBalance": 0.0,
    "revenue": 15000.00,
    "expense": 8200.00
  },
  "charts": {
    "revenueExpense": [
      { "month": "2025-01", "revenue": 2000, "expense": 1500 }
    ],
    "ordersByStatus": [
      { "status": "OPEN", "count": 5 }
    ],
    "receivablesAging": [
      { "key": "not_due", "amount": 1000 },
      { "key": "d1_30", "amount": 500 }
    ],
    "payablesAging": [ ... ]
  },
  "options": {
    "customers": ["Acme Corp", "Global Freight Ltd"]
  }
}
```

#### 2. Branch scoping on every report query

All report functions now respect the user's branch permissions. If a user is scoped to a single branch and not an organization-wide role, the backend automatically adds `branch_id == context.branch_id` to every SQL query.

This was added to:
- `dashboard()`
- `receivables()`
- `payables()`
- `profitability()`
- `_journal_revenue_expense_by_month()`
- `_account_type_totals()` (used by income/expense/financial-summary)
- `_customers()`
- `_service_order_status_counts()`

#### 3. Receivables & Payables now include names and job numbers

The backend used to return bare IDs like `partyId`. The frontend table expects readable names. We added SQL joins:
- `BusinessParty.display_name` → `customer` / `supplier`
- `ServiceOrder.service_order_no` → `jobNo`

We also added computed `aging` strings (e.g. `"15d"`) and `outstanding` aliases so the report columns map 1:1 with the frontend's expected keys.

#### 4. Profitability report now includes customer names

Same story — joined `BusinessParty` to get the customer display name, and added frontend-friendly field aliases (`postedRevenue`, `postedCost`, `grossProfit`).

---

## Frontend Changes

### New API endpoint constants

**File:** `frontend/app/utils/constants/api-v1-endpoints.ts`

Added 9 new endpoint paths:
- `/api/v1/reports/dashboard`
- `/api/v1/reports/service-orders`
- `/api/v1/reports/quotation-performance`
- `/api/v1/reports/receivables`
- `/api/v1/reports/payables`
- `/api/v1/reports/income`
- `/api/v1/reports/expenses`
- `/api/v1/reports/profitability`
- `/api/v1/reports/financial-summary`

### New Reports repository

**Files:**
- `frontend/app/repositories/contracts/lcs.ts` — the TypeScript contract
- `frontend/app/repositories/http/lcs.ts` — the HTTP implementation
- `frontend/app/repositories/index.ts` — exported for use in components

The frontend now has a first-class `reports` repository that wraps all report endpoints with proper typing:
```ts
const { reports } = useLcsRepositories()
const data = await reports.dashboard()
const rows = await reports.receivables()
```

### Dashboard now calls the backend

**File:** `frontend/app/components/freight/DashboardView.vue`

- **Before:** Called `store.dashboardSummary()`, which computed everything from cached `jobs`, `debitNotes`, `journals`, etc.
- **After:** Calls `await reports.dashboard()` on load, then slices the returned monthly data by selected chart year.

The chart year toggles still work instantly — they just filter the already-fetched backend data instead of triggering a full re-computation from store cache.

### Three reports now call backend APIs

**File:** `frontend/app/components/freight/ReportsView.vue`

The reports page now loads backend data when the active report slug matches one of the supported endpoints:

| Report Slug | Backend Endpoint Called |
|-------------|------------------------|
| `accounts-receivable` | `reports.receivables()` |
| `accounts-payable` | `reports.payables()` |
| `profitability` | `reports.profitability()` |

All other reports (`service-orders`, `containers`, `general-ledger`, `profit-loss`, `balance-sheet`, `cash-flow`, etc.) still fall back to the existing client-side `buildReportRows()` logic.

---

## What We Verified (Without Changing Code)

### Finance document type mapping
The frontend maps collections to backend document types like this:
- `debitNotes` → `CUSTOMER_INVOICE`
- `customerPayments` → `CUSTOMER_RECEIPT`
- `supplierCosts` → `SUPPLIER_BILL`
- `supplierPayments` → `SUPPLIER_PAYMENT`

These match exactly with the backend's `DEFAULT_ACCOUNTS` and `PostingRule` definitions. **No changes needed.**

### Legacy modules are intentional
`freight-modules.ts` contains both old paths (`/sales/companies`, `/operations/jobs`) and new paths (`/quotations`, `/service-orders`). The canonical modules clone the legacy ones as schema templates. The sidebar hardcodes the canonical routes, so legacy routes are never exposed to users. **We left them in place.**

### UI Schema is dormant
The backend has `GET /api/v1/ui-schemas/{page}` and the frontend has a repository for it, but no page actually calls it. **We documented this as a known gap**, not a bug.

---

## Known Limitations

1. **Cash/Bank balance is hardcoded to 0.0** in the backend dashboard because there is no cash-account balance aggregation query yet. The frontend previously read from seeded local data.
2. **Dashboard date filtering** is client-side only. The backend returns all-time data; the frontend slices by year.
3. **9 of 12 reports** still build client-side. Only `accounts-receivable`, `accounts-payable`, and `profitability` are backend-driven.

---

## Files Changed (7 files)

| # | File | What changed |
|---|------|-------------|
| 1 | `backend/app/modules/reports/service.py` | Full rewrite of dashboard; branch scoping; joins for names/job numbers |
| 2 | `frontend/app/utils/constants/api-v1-endpoints.ts` | Added 9 report endpoint constants |
| 3 | `frontend/app/repositories/contracts/lcs.ts` | Added `DashboardSummary` type + `ReportsRepository` interface |
| 4 | `frontend/app/repositories/http/lcs.ts` | Added `createHttpReportsRepository()` |
| 5 | `frontend/app/repositories/index.ts` | Exported `reports` from `useLcsRepositories()` |
| 6 | `frontend/app/components/freight/DashboardView.vue` | Now fetches from backend API |
| 7 | `frontend/app/components/freight/ReportsView.vue` | Fetches backend data for 3 report types |

---

*Written 2025-09-25. Commit: `ee43ac0`.*
