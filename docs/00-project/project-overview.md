# Project overview

LCS Freight Forwarding Management System is an existing single-tenant modular monolith for
freight sales, operational execution, customer/supplier documents and double-entry finance.
The Smart ERP direction prioritizes deterministic automation, fewer repeated inputs and
auditable financial correctness while preserving the existing application.

## Existing technology and ownership

| Area | Existing implementation |
|---|---|
| Frontend | Nuxt 4 static SPA, TypeScript, Nuxt UI/Tailwind, Pinia and shared HTTP repositories |
| Backend | FastAPI, async SQLAlchemy, Pydantic and additive Alembic migrations |
| Data and authorization | PostgreSQL, existing Decimal accounting engine and Casbin |
| Existing services | nginx/Compose, Redis and S3-compatible attachment storage; current integrations retained |

Exact inspected manifest ranges and evidence limits are in
[system architecture](../01-architecture/system-architecture.md). Live deployment/capacity is
not certified by the documentation.

Sales owns commercial offers; operations owns SO snapshots, physical containers, configured
work and informational charges; finance owns posting, allocations and corrections.
Reports consume operational or posted sources according to their declared purpose.
Master data/configuration/administration provide existing shared prerequisites.

## Boundaries and terminology

[Requirements](requirements.md) owns the approved 44 business pages. Supporting create/detail/
auth/print routes do not increase the count. A standalone Period Closing navigation page
remains proposed; the specified workspace belongs to Accounting Periods.

Quotation revision = versioned commercial offer; SO = Service Order; charge = operational
billing information; posting = immutable journal creation; allocation = settlement linkage;
period lock = prohibition on new postings in a closed date range. Business Party Roles
classify parties; authorization roles grant Casbin capabilities.

Use the [master plan](../04-implementation/master-plan.md) for sequence and
[feature inventory](feature-inventory.md) for page contracts. This overview supplies navigation
and vocabulary; it does not duplicate acceptance rules or implementation status.
