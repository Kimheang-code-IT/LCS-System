x# Business Requirements Document

## 1. Purpose

The Freight Forwarding and Administrative Platform manages quotations, service orders, operational components, documents, service charges, payments, expenses, and double-entry financial records.

## 2. Business Goals

- Standardize freight-forwarding operations.
- Support Import, Export, Transit, and related trade directions.
- Track dynamic operational components without creating a physical table for every component.
- Link services, containers, transport movements, documents, and milestones.
- Generate customer-facing service charges and invoices.
- Maintain reusable financial documents and balanced double-entry accounting entries.
- Preserve audit history and document traceability.

## 3. Scope

### In scope

- Master data management.
- Business parties and roles.
- Places, zones, checkpoints, ports, warehouses, and destinations.
- Container and transport master data.
- Dynamic component templates and trade-direction configuration.
- Quotation revisions and conversion to service orders.
- Service-order execution and document attachments.
- Service-order charges and container-linked fee lines.
- Financial documents for invoices, receipts, payments, income, expenses, transfers, and adjustments.
- Chart of accounts and double-entry journals.
- Payment allocation.
- Audit, authorization, and reporting foundations.

### Out of scope for the first release

- Full tax-regulatory integration.
- Automated customs-system submission.
- Payroll accounting.
- Inventory accounting.
- Multi-company consolidation.
- Automated supplier-rate procurement.

## 4. Actors

- System administrator.
- Operations officer.
- Sales or quotation officer.
- Finance officer.
- Finance manager.
- Operations manager.
- Auditor or read-only reviewer.

## 5. Core Requirements

### BR-001 Master data

The system shall manage trade directions, places, container types, transport types, transport assets, fee types, financial accounts, chart-of-accounts records, and business parties.

### BR-002 Shared business parties

One business party shall be able to have multiple roles, including customer, supplier, carrier, customs broker, or transport operator.

### BR-003 Dynamic operations

The system shall support configurable service components grouped by business category and configured per trade direction.

### BR-004 Quotations

Users shall create quotations containing multiple revisions, places, transport options, container requirements, and pricing lines.

### BR-005 Explicit conversion

Only an authorized user action shall convert an accepted quotation revision into a service order.

### BR-006 Service orders

The system shall track service-order status, requirements, actual containers, operational components, documents, and milestones.

### BR-007 Service charges

A service order shall support informational customer charges consisting of fee lines, optionally linked to actual containers. A service charge shall not itself be an accounting journal entry.

### BR-008 Financial documents

The finance module shall use one reusable financial-document model for invoices, supplier bills, receipts, payments, income, expenses, transfers, and adjustments.

### BR-009 Double-entry accounting

Every posted journal entry shall contain balanced debit and credit lines.

### BR-010 Payment allocation

Payments shall be allocatable to one or more invoices or bills, with support for partial settlement.

### BR-011 Traceability

Financial documents generated from service-order charges shall retain their source relationship.

### BR-012 Auditability

Posted financial records and completed operational records shall not be destructively edited. Corrections shall use reversal or adjustment mechanisms.

## 6. Business Rules

- Quotation revisions become immutable after sending.
- Only an accepted quotation revision may be converted.
- A service-order charge may exist without a financial document.
- A financial invoice may be created manually or from a service-order charge.
- Posting a financial document creates or links a journal entry.
- A posted journal must balance.
- Payment allocation cannot exceed the available payment amount or target balance.
- Credentials must be encrypted or stored using a secret reference; passwords must not be hashed when users need to retrieve them.
- Actual containers are distinct from container requirements.
- A service-order component uses the template version captured when it was created.

## 7. Success Criteria

- Operations can process a service order without custom tables for every service component.
- Finance can record both service-order-related and standalone transactions.
- Management can determine customer receivables, supplier payables, income, expenses, and service-order profitability.
- Every posted accounting entry is balanced and traceable to its source.
