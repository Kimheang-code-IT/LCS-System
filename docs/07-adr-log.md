# Architecture Decision Log

## ADR index

The following decisions were approved during foundation discovery; they are planning
decisions, not claims of runtime verification. No speculative ADR files are created.

| ID | Decision | Status / rationale |
|---|---|---|
| ADR-001 | Preserve FastAPI modular monolith and Nuxt 4 SPA | Accepted; existing application, minimal migration and operational complexity |
| ADR-002 | PostgreSQL with existing Decimal double-entry engine | Accepted; preserve atomic financial history and safeguards |
| ADR-003 | Existing session authentication and Casbin RBAC | Accepted; one authorization authority, backend enforcement |
| ADR-004 | Versioned REST and existing envelopes | Accepted; preserve shared client contracts; no GraphQL requirement |
| ADR-005 | Hostinger VPS / Compose / nginx / existing CI/CD | Accepted intended baseline; live deployment and capacity unverified |
| ADR-006 | Scheduled encrypted off-host backups and coordinated file recovery | Accepted requirement; implementation/restore evidence outstanding; PITR conditional |
| ADR-007 | Preserve background services; no required external runtime AI | Accepted; queues require demonstrated reliability need and approval |
| ADR-008 | Exact foundation paths with linked legacy references | Accepted; preserve existing material without competing authorities |

## Decision records

[Decision directory](decisions/README.md) holds future detailed records when a real decision
needs them. Record context, options, cost/complexity/scaling trade-offs, decision, status,
consequences, approval and validation limits. Link each from this index and the affected topic.
Do not silently replace an accepted architecture choice; supersede it explicitly with approval.
