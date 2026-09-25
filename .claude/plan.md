# LCS-System Full Backend-to-Frontend Integration Plan

## Executive Summary

The LCS-System Freight Forwarding application is a comprehensive system with a FastAPI backend and Nuxt 3 frontend. After auditing the entire codebase, the core CRUD APIs and frontend pages are largely connected. However, there are **significant disconnects** in reports, dashboard, and some finance module mappings that need to be resolved.

## Architecture Overview

- **Backend**: FastAPI with SQLAlchemy async, modular structure (`app/modules/`)
- **Frontend**: Nuxt 3 with Pinia store, metadata-driven module system
- **Data Flow**: Frontend uses a centralized `useFreightStore` that caches remote data. Most list/detail pages fetch via generic `ModuleRepository` or specialized LCS repositories.

## Modules Audited

### Backend Modules (8 total)
1. **auth** — login, logout, refresh, me, forgot/reset password, organizations, branches, users, roles, permissions, avatar
2. **master_data** — CRUD for reference tables (businessParties, places, tradeDirections, containerTypes, transportTypes, transportAssets, feeTypes, componentGroups, componentTemplates, tradeDirectionComponents) plus generic record store (companies, shipments, customs, documents, deliveries, customerPayments, supplierCosts, supplierPayments) and service-order-tabs configuration
3. **finance** — chart-of-accounts, financial-accounts, accounting-periods, journals, financial-documents, posting-rules, document-sequences
4. **operations** — service-orders, service-charges, attachments, dynamic tabs, components, containers
5. **quotations** — quotations, revisions, send, accept, convert, submit
6. **reports** — dashboard, service-orders, quotation-performance, receivables, payables, income, expenses, profitability, financial-summary
7. **settings** — app-info (branding), app-config (localization/email/telegram), global search
8. **audit** — audit-events

### Frontend Pages (all audited)
- auth, quotations, service-orders, service-charges, finance/*, administration/*, configuration/*, master-data/*, reports/*, print/*, dashboard

## Critical Gaps Found

### 1. Reports & Dashboard Backend API Disconnect (HIGH PRIORITY)
**Problem**: Backend exposes dedicated `/reports/*` endpoints (`/reports/dashboard`, `/reports/service-orders`, `/reports/receivables`, `/reports/payables`, `/reports/profitability`, `/reports/financial-summary`, etc.). The frontend **never calls these endpoints**. Instead, `ReportsView.vue` and `DashboardView.vue` build report data client-side from the local store cache.

**Impact**:
- Backend report APIs are completely unused (dead code)
- Report accuracy depends on whether the user has previously loaded all dependent collections into the store
- Dashboard and reports may show stale or incomplete data
- Complex aggregations (aging, profitability) run in the browser instead of the database

**Fix**: Wire `DashboardView.vue` to call `/reports/dashboard`. Wire `ReportsView.vue` to call the corresponding `/reports/{slug}` backend endpoint when available, falling back to client-side computation only for reports without a backend counterpart.

### 2. Finance Collection Endpoint Mapping Issue (MEDIUM PRIORITY)
**Problem**: In `frontend/app/utils/api/freight-remote.ts`, `debitNotes` maps to `financial('CUSTOMER_INVOICE')`. The `/finance/documents` page uses collection `debitNotes`. The generic module repository sends data to `/api/v1/financial-documents?document_type=CUSTOMER_INVOICE`, but the page label and module config describe it as "Financial Documents" supporting multiple document types. The filter and create flows may not correctly pass `documentType` through the generic repository.

**Impact**: Users may create financial documents with the wrong type, or filters may not apply correctly.

**Fix**: Ensure `documentType` is correctly passed in query params for list and in payload for create/update through the generic module repository.

### 3. Legacy Module Definitions Without Pages (LOW PRIORITY)
**Problem**: `frontend/app/config/freight-modules.ts` defines modules at paths like `/sales/companies`, `/operations/jobs`, `/operations/shipments`, `/finance/debit-notes`, `/finance/customer-payments`, etc. No corresponding Vue page files exist for these paths. The canonical routes (`/quotations`, `/service-orders`, `/finance/documents`) exist instead.

**Impact**: Dead config bloat. Users cannot navigate to these paths.

**Fix**: Remove legacy module definitions that have no page files, or create stub pages that redirect to canonical routes.

### 4. Missing UI Schema Integration Verification (LOW PRIORITY)
**Problem**: Backend has `/api/v1/ui-schemas/{page}` in `master_data/router.py`. Frontend has `UiSchemaRepository`. It is unclear whether any page actually calls this endpoint to dynamically configure forms.

**Fix**: Verify if any component uses `uiSchema.getPageSchema()`. If none, document as unused.

### 5. Print Preview Data Source (MEDIUM PRIORITY)
**Problem**: Print page (`/print/[collection]/[id]`) loads `PrintDocumentPreview`. Need to verify whether it fetches fresh data from the API for print or relies on store cache.

**Fix**: Inspect print components and ensure they call the correct GET endpoint for the collection/id being printed.

## Implementation Plan

### Phase 1: Reports & Dashboard Integration (Highest Impact)
1. **Backend verification**: Confirm `/reports/dashboard` and each `/reports/{slug}` endpoint returns the expected shape.
2. **Frontend Dashboard**:
   - Modify `DashboardView.vue` to call `api.get('/api/v1/reports/dashboard')` on load.
   - Merge backend response with existing client-side chart computation if needed.
3. **Frontend Reports**:
   - Modify `ReportsView.vue`: for each report slug, check if a backend endpoint exists. If yes, fetch from backend; if no, keep client-side computation.
   - Add report-specific API calls to `useLcsRepositories` or `useFreightStore`.
4. **Update `freight-remote.ts`**: Add report endpoint mappings if needed.

### Phase 2: Finance Document Type Mapping Fix
1. Verify `financial('CUSTOMER_INVOICE')` mapping for `debitNotes` is intentional.
2. Update generic module repository (`module.ts`) to include `document_type` in query for list operations where applicable.
3. Test create/update of financial documents to ensure `documentType` field is preserved.

### Phase 3: Cleanup & Verification
1. Remove or redirect legacy module definitions in `freight-modules.ts` that have no page files.
2. Verify print preview calls the correct API endpoint.
3. Verify UI schema endpoint usage.
4. Run end-to-end smoke tests for each module.

### Phase 4: End-to-End Testing
1. Test each frontend page → API → backend → database flow.
2. Verify CRUD for: quotations, service-orders, service-charges, financial-documents, journals, all master-data, all configuration, all administration.
3. Verify reports and dashboard show correct data.
4. Verify auth flows (login, logout, refresh, password reset).

## Testing Strategy

- **API Testing**: Use `curl` or HTTP client to call each backend endpoint independently.
- **Frontend Testing**: Verify network tab calls in browser for each page operation.
- **Integration Testing**: Walk through complete user flows (create quotation → convert to job → add charges → create invoice → post).

## Files Likely to Change

- `frontend/app/components/freight/DashboardView.vue`
- `frontend/app/components/freight/ReportsView.vue`
- `frontend/app/stores/freight.ts`
- `frontend/app/utils/api/freight-remote.ts`
- `frontend/app/repositories/http/lcs.ts`
- `frontend/app/repositories/http/module.ts`
- `frontend/app/config/freight-modules.ts`
- `frontend/app/components/print/DocumentPreview.vue` (if print needs fixes)

## Overall Integration Status Before Fixes

| Area | Status |
|------|--------|
| Auth | ✅ Connected |
| Master Data CRUD | ✅ Connected |
| Configuration CRUD | ✅ Connected |
| Administration CRUD | ✅ Connected |
| Quotations → Service Orders | ✅ Connected |
| Service Charges → Finance | ✅ Connected |
| Finance Documents / Journals | ✅ Connected (with minor type mapping issue) |
| Attachments | ✅ Connected |
| Dynamic Tabs | ✅ Connected |
| Audit Logs | ✅ Connected |
| Settings | ✅ Connected |
| Reports | ❌ Disconnected from backend report APIs |
| Dashboard | ❌ Disconnected from backend dashboard API |
| Print | ⚠️ Needs verification |

## Approval Requested

Please review the plan above. If approved, I will proceed with **Phase 1** first (Reports & Dashboard integration), then continue through the remaining phases. I can also provide a more granular breakdown of any specific phase if needed.
