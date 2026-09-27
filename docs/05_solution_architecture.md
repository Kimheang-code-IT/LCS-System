# Solution Architecture

## 1. Architecture Decision

Implement the first release as a **modular monolith** with clear bounded modules and interfaces. The current version runs the API, a static SPA served by nginx, and the datastores; there is no separate background worker yet. Extract services later only when scaling, team ownership, or deployment independence justifies it.

```text
Nuxt 4 Static SPA (nuxt generate) ── served by nginx
          │  /api/ reverse proxy
          ▼
FastAPI Application
 ├── Identity and Authorization
 ├── Organization and Branch
 ├── Master Data
 ├── Configuration
 ├── Quotation
 ├── Service Order
 ├── Service Charge
 ├── Finance and Accounting
 ├── Document Management
 ├── First-run Setup
 └── Reporting API
          │
          ├── PostgreSQL
          ├── Redis
          └── Object Storage (MinIO / S3)
```

## 2. Bounded Contexts

### Identity and authorization

Owns users, credentials, sessions, roles, permissions, assignments, and authorization policy evaluation.

### Organization

Owns organizations, branches, settings, accounting periods, and document sequences.

### Master data

Owns parties, places, directions, container types, transport types, transport assets, and fee types.

### Configuration

Owns component groups, versioned templates, attributes, and direction-specific assignments.

### Operations

Owns quotations, revisions, service orders, containers, dynamic components, and milestones.

### Commercial

Owns informational service-order charges and charge-to-financial-document conversion requests.

### Finance

Owns reusable financial documents, allocation, chart of accounts, posting rules, journal entries, and reversals.

### Document management

Owns attachment metadata, object-storage operations, secure access, and rendering.

### Reporting

Consumes read-only data or projections and never modifies transactional records.

## 3. Dependency Rules

Allowed dependency direction:

```text
API layer
   ↓
Application services
   ↓
Domain policies
   ↓
Repositories / transaction manager
   ↓
PostgreSQL
```

Rules:

- Domain modules must not query another module's tables directly.
- Cross-module operations use application services or explicit interfaces.
- Finance may consume a service-charge source snapshot through a conversion service.
- Reporting reads projections or read-only repositories.
- Authorization is called before repository access.
- No UI rule is treated as a security rule.

## 4. Suggested Repository Structure

```text
backend/
  app/
    api/            versioned routers (/api/v1)
    core/           config, auth, permissions, storage, bootstrap
    modules/        auth, master_data, quotations, operations,
                    finance, reports, settings, setup, audit
  alembic/          versioned migrations (source of truth for schema)
  tests/
frontend/
  app/
    components/     Vue components (Nuxt UI)
    composables/
    config/         module + settings schemas
    pages/
    repositories/   http + contracts
    stores/         Pinia
    utils/
  i18n/locales/     en.json, km.json
infrastructure/
  docker-compose.yml
  nginx/            default.conf (serves SPA, proxies /api)
```

Each backend module should contain:

```text
router.py
schemas.py
service.py
policies.py
repository.py
models.py
exceptions.py
```

## 5. Request Flow

```text
HTTP request
  → authentication middleware
  → organization/branch context
  → permission policy
  → request validation
  → application service
  → repository transaction
  → audit event
  → response
```

## 6. Transaction Boundaries

Use one database transaction for:

- quotation conversion;
- revision creation where children are copied;
- service-charge-to-invoice conversion;
- financial-document posting;
- manual journal posting;
- payment allocation;
- reversal;
- period closure;
- document-number allocation.

## 7. Finance Posting Architecture

```text
Financial document
        │
        ▼
Posting service
        ├── validate document state
        ├── resolve period
        ├── resolve account rules
        ├── build journal lines
        ├── validate balance
        └── persist document + journal atomically
```

The journal is the source of truth for posted accounting balances. Financial documents are source/business records.

## 8. Events and Background Jobs

The current version is synchronous: there is no outbox table or background
worker. Notifications, document rendering, report refresh and external
integrations run inline or are not yet implemented.

A future release may add an outbox table and workers for:

- document rendering;
- email or Telegram notifications;
- OCR;
- external customs integration;
- report refresh;
- checksum or antivirus processing.

Asynchronous jobs must not be used for operations that require immediate
transactional consistency, such as journal posting or payment allocation.

## 9. Storage Architecture

PostgreSQL stores metadata and business references. Object storage stores file contents.

Upload flow:

1. Authorize attachment creation.
2. Create pending metadata record.
3. Return a pre-signed upload URL.
4. Client uploads the file.
5. API verifies completion, size, MIME type, and checksum.
6. Mark attachment available.
7. Audit upload.

## 10. Security Architecture

- TLS for all external traffic.
- Argon2id or equivalent password hashing for application credentials.
- Encryption or secret-manager references for retrievable customs passwords.
- Scoped RBAC enforced at API and repository boundaries.
- No secrets in logs, responses, seed data, or audit payloads.
- Rate limits for authentication and sensitive endpoints.
- Audit events for high-risk actions.

## 11. Database and Consistency

- PostgreSQL is the transactional source of truth.
- Migrations are versioned and reviewed.
- Organization and branch ownership are explicit columns.
- Composite foreign keys protect organization/branch consistency where possible.
- Application services enforce business invariants not expressible as row constraints.
- Journal balance must be checked before posting.

## 12. Reporting

Start with indexed read-only queries and views. Add materialized projections when dashboard volume increases.

Accounting reports must read posted journal lines only. Operational reports may include draft records but must label their status clearly.

## 13. Deployment Environments

```text
local → development → staging → production
```

Each environment has separate:

- database;
- object-storage bucket;
- secrets;
- external integration credentials;
- monitoring namespace.

Production data must never be copied to lower environments without approved anonymization.

## 14. Observability

Log:

- request ID;
- correlation ID;
- user ID where safe;
- organization and branch;
- module and operation;
- duration;
- result/error code.

Measure:

- API latency and error rates;
- authorization denials;
- posting failures;
- database connections;
- storage failures;
- backup success.

## 15. Future Extraction Criteria

Extract a module into a service only when at least one is true:

- independent scaling is required;
- separate team ownership is established;
- external integration isolation is necessary;
- deployment cadence creates operational risk;
- data ownership can be made explicit;
- distributed transaction complexity is acceptable.
