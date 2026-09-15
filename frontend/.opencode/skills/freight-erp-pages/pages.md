# Page catalog

Compare each route to this spec. Update **module schemas**, `WorkspaceView` columns, `JobDetail` tabs, and reports — do not invent a parallel app and do not hardcode the catalog into page Vue files.

Implementation: thin routes + reusable shells. Fields/columns come from `freight-modules.ts` / `lcs-reference-modules.ts`. Tenant look-and-feel comes from System Settings. Job task fields come from component templates. Every form field has ERPNext-style helper text. See [components.md](components.md).

## Dashboard `/`

Only: compact KPI cards and **two charts**. Do not add detailed tables. Do **not** add a dashboard filter bar (no organization, branch, date range, or More Filters). Scope follows the signed-in org/branch.

KPI cards: Open Orders, In Progress, On Hold, Awaiting Closure, Accounts Receivable, Accounts Payable, Cash / Bank, Revenue.

Charts (exactly two), each in `AppChartPanel` (title left; **This Year / Last Year** and **Monthly / Quarterly / Yearly** on the right; `⋯` to download PNG/CSV). Charts stretch to fill remaining dashboard height.

- Line: Revenue vs Expense (posted journals only; period filter changes the axis)
- Bar: Service Orders by Status (year filter; period is chart chrome only)

Aging lives on report pages, not the dashboard.

## Quotations `/quotations`

List columns: Quotation No., Customer, Direction, Branch, Revision, Date, Valid Until, Total, Status, Actions.

Filters: Search, Customer, Branch, Trade Direction, Status, Date Range.

Detail tabs: Overview, Route, Containers, Pricing, Files, Revisions.

Pricing table (compact): Service / Fee, Container, Qty, Unit, Unit Price, Discount, Tax, Total, Actions.

Do not permanently display all calculated subtotal columns.

Rules: DRAFT is editable. SENT is read-only. Changes to sent quotation require new revision. Only ACCEPTED quotation can convert. Conversion must be explicit.

## Service orders `/service-orders`

Treat Service Order as the operational Job Workspace.

List columns: Job No., Customer, Direction, Branch, Containers, Documents, Total Charges, Status, row meta (avatar, relative updated time, comment count) + `⋯` actions.

Filters: Search, Customer, Branch, Direction, Status, Date Range.

Detail tabs: **Overview, Route, Containers** (core), then one tab per active Component Group (`showOnJobWorkspace`), then **Finance, Files**. Comments stay on the Overview meta rail. Service charges live inside Containers.

Core tabs are not configurable and never come from Component Groups. Reserved slugs `overview`, `route`, `containers`, `finance`, and `files` cannot be used as group tabs.

### Overview

Show: Customer, Branch, Trade Direction, Currency, Source Quotation, Status, Created Date, Created By, Description.

Compact summary: Containers, Documents Completed / Total, Total Charges, Invoice Total.

Overview edit: Job Information, Dates, Reference, Remarks only. Invoice / packing list / B/L fields belong on component-group tabs. Route fields belong on the Route tab.

### Route

Compact table: #, Role, Place, Planned / Actual, Notes, Actions.

### Containers

Keep backend separation between Container Requirements and Actual Containers, but show them inside one tab.

Requirements: Container Type, Required, Actual, Remaining, Description.

Actual Containers: Container No., Type, Seal, Status, Net Weight, Gross Weight, Actions.

Preserve: Gross Weight >= Net Weight.

Also allow Service Charges (payments) inside this tab.

### Component-group tabs

Each extra tab is a **dynamic form** from Component Groups + Component Templates + Trade Direction Components. Render attributes with `AppDynamicFieldRenderer` (`dataType` / `inputType`). Do not hard-code Vue forms for Invoice, Packing List, Customs, etc.

Non-repeatable: one form on the tab (create the component instance on first save). Repeatable: compact table + Add, same form in a slideover. Required attributes must be present before completion. Each attribute shows ERPNext-style helper text (`helpText` or i18n). Historical instances keep their captured `templateVersion`.

### Finance

Posted invoices, supplier costs, and receivables for the job.

### Files

Attachments for the service order.

## Service charges `/service-charges`

Operational/commercial records. They do NOT directly affect accounting.

List columns: Charge No., Service Job, Customer, Date, Currency, Total, Status, Invoice, Actions.

Filters: Search, Service Job, Customer, Branch, Status, Date Range.

Header: Charge No., Service Job, Customer, Branch, Document Date, Currency, Status, Remarks.

Detail tabs: General, Fee Lines, Traceability.

Traceability: Finance Invoice, Posted Journal, and the source chain (quotation → service order → finance invoice → posted journal). View opens the linked record.

Pricing lines: Service / Fee, Container, Qty, Unit, Unit Price, Discount, Tax, Total, Actions.

Summary: Subtotal, Discount, Tax, Total.

Actions: Save Draft, Issue, Print / Download, Create Finance Invoice.

Issue Service Charge ≠ Accounting Posting.

Flow: Service Charge → Create Finance Invoice → Draft Financial Document → Post → Journal.

## Financial documents `/finance/documents`

Types: Customer Invoice, Supplier Bill, Customer Receipt, Supplier Payment, Other Income, Other Expense, Transfer, Adjustment.

One shared Financial Document model.

List columns: Document No., Type, Party, Date, Due Date, Service Job, Total, Outstanding, Status, Actions.

Detail tabs: Overview, Lines, Allocation, Journal, Traceability, Files, Activity.

Rules: Draft editable. Posted read-only. Corrections use reversal/adjustment. Posting requires open accounting period. Posting generates balanced journal.

## Chart of accounts `/finance/chart-of-accounts`

Table: Account Code, Account Name, Type, Parent, Normal Balance, Postable, Status, Actions.

Filters: Search, Account Type, Parent, Postable, Status.

Fields: Account Code, Account Name, Account Type, Parent Account, Normal Balance, Postable, Status.

## Financial accounts `/finance/financial-accounts`

Table: Account Name, Ledger Account, Type, Currency, Bank, Account No., Balance, Status, Actions.

Fields: Ledger Account, Account Name, Account Type, Currency, Bank Name, Masked Account Number, Status.

Do not expose sensitive account information unnecessarily.

## Journals `/finance/journals`

List: Entry No., Posting Date, Source, Branch, Description, Debit, Credit, Status, Actions.

Manual lines: Account, Party, Service Job, Description, Debit, Credit, Currency, Actions.

Show: Total Debit, Total Credit, Balance Difference.

Post only when Total Debit = Total Credit. Posted journals are immutable.

## Accounting periods `/finance/accounting-periods`

Table: Period, Start Date, End Date, Status, Posting Count, Closed By, Closed At, Actions.

Actions: View, Close, Reopen. Closed periods must reject posting.

## Operations reports

`/reports/operations/service-orders` — KPIs: Total Orders, Open, In Progress, On Hold, Completed. Table: Job No., Date, Customer, Branch, Direction, Containers, Tasks, Charge Total, Invoice Total, Status.

`/reports/operations/service-order-status` — Summary: DRAFT, OPEN, IN_PROGRESS, ON_HOLD, COMPLETED, CLOSED, CANCELLED. Table: Job No., Customer, Branch, Direction, Created Date, Status, Days Open, Pending Tasks, Last Activity.

`/reports/operations/containers` — Table: Container No., Type, Service Job, Customer, Branch, Seal, Status, Net Weight, Gross Weight, Current Milestone.

`/reports/operations/profitability` — KPIs: Revenue, Cost, Gross Profit, Margin %. Table: Job No., Customer, Branch, Quoted, Service Charges, Posted Revenue, Posted Cost, Gross Profit, Margin %. Gross Profit = Posted Revenue - Posted Cost.

## Financial reports

Posted journals only (except operational reports above).

`/reports/finance/revenue-expense` — KPIs: Revenue, Expense, Net Result. Table: Date, Account, Category, Party, Service Job, Description, Revenue, Expense, Branch.

`/reports/finance/accounts-receivable` — KPIs: Total Receivable, Not Due, 1–30, 31–60, 61–90, 90+. Table: Invoice No., Customer, Service Job, Invoice Date, Due Date, Total, Paid, Outstanding, Aging, Status. Posted customer invoices minus valid receipt allocations.

`/reports/finance/accounts-payable` — Same layout as AR. Table: Bill No., Supplier, Service Job, Bill Date, Due Date, Total, Paid, Outstanding, Aging, Status.

`/reports/finance/general-ledger` — Filters: Branch, Account, Party, Service Job, Period, Date Range. Table: Posting Date, Journal No., Source Document, Account, Description, Debit, Credit, Running Balance, Branch. Summary: Opening Balance, Total Debit, Total Credit, Closing Balance. Only POSTED journal lines.

`/reports/finance/trial-balance` — Table: Account Code, Account Name, Opening Debit, Opening Credit, Period Debit, Period Credit, Closing Debit, Closing Credit. Bottom: Total Debit, Total Credit, Difference (must be zero for balanced posted data).

`/reports/finance/profit-loss` — Financial-statement layout (not a generic wide table). Posted revenue and expense accounts.

`/reports/finance/balance-sheet` — Assets / Liabilities / Equity statement. Show Assets, Liabilities + Equity, Difference (should be zero).

`/reports/finance/cash-flow` — If formal cash-flow classifications are not supported, use a practical Cash & Bank movement report. Do not invent operating/investing/financing classifications. KPIs: Opening Balance, Cash In, Cash Out, Closing Balance. Table: Date, Financial Account, Source, Reference, Party, Description, Cash In, Cash Out, Running Balance. Posted journals affecting cash/bank accounts.

## Master data

`/master-data/business-parties` — Party Code, Name, Roles, VAT/TIN, Contact, Phone, Email, Country, Status, Actions. Roles: CUSTOMER, SUPPLIER, CARRIER, CUSTOMS_BROKER, TRANSPORT_OPERATOR. Do not duplicate a company for different roles.

`/master-data/places` — Code, Name, Category, Parent, Country, Address, Status, Actions.

`/master-data/trade-directions` — Code, Name, Description, Status, Actions.

`/master-data/container-types` — Code, Name, Size, Kind, ISO Code, Max Gross Weight, Status, Actions.

`/master-data/transport-types` — Code, Name, Description, Status, Actions.

`/master-data/transport-assets` — Asset Code, Transport Type, Identity, Identity Type, Owner, Operator, Country, Status, Actions.

`/master-data/fee-types` — Code, Name, Description, Status, Actions.

## Configuration

`/configuration/component-groups` — Code, Name, Description, Display Order, Status, Actions.

`/configuration/component-templates` — List: Code, Name, Version, Description, Attributes, Status, Actions. Attributes: Code, Label, Data Type, Input Type, Required, Repeatable, Reference Type, Display Order, Actions. Preserve template version history.

`/configuration/trade-direction-components` — Trade Direction, Component Group, Template, Required, Repeatable, Display Order, Status, Actions.

`/configuration/posting-rules` — Document Type, Fee Type, Debit Account, Credit Account, Tax Account, Status, Actions.

## Administration

`/administration/organizations` — Organization Code, Legal Name, Display Name, Country, Default Currency, Timezone, Status, Actions.

`/administration/branches` — Branch Code, Branch Name, Organization, Place, Phone, Email, Head Office, Status, Actions.

`/administration/users` — User Code, Username, Display Name, Email, Status, Default Branch, Last Login, Actions. Detail tabs: Profile, Roles, Branches, Sessions, Activity.

`/administration/roles` — Code, Name, Description, System Role, Status, Actions. Group permissions by resource/module.

`/administration/document-sequences` — Document Type, Year, Prefix, Last Value, Padding, Next Number Preview, Status, Actions. Never generate final document numbers in frontend code.

`/administration/system-settings` — Setting Key, Scope, Value, Sensitive, Updated By, Updated At, Actions. Do not expose sensitive values.

`/administration/audit-logs` — Date/Time, User, Event, Action, Entity, Organization, Branch, Result, Actions. Filters: User, Event Type, Entity, Branch, Result, Date Range. Never display passwords, tokens, or secrets.
