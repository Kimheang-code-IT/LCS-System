---
name: lcs-finance
description: Change or review LCS posting, settlements, journals, periods, numbering, currency or financial-report logic with focused integrity verification.
---

# lcs-finance

Purpose/modules: finance, accounting controls, AR/AP, financial reports and operational source
links. Read affected [map rows](../../context/module-map.md),
[financial invariants](../../../docs/01-architecture/database-design.md#financial-data-integrity--canonical-invariants),
[accounting rules](../../../docs/02-business/accounting-and-posting.md) and the current task/Handoff.

Workflow: trace source → document → journal → allocation/report; inspect the existing Decimal
calculation and transaction owner. Preserve debit=credit, atomicity, idempotency, account/type
validation, rate snapshots, allocation bounds, closed-period denial and immutable posted
history. Use reversal instead of editing posted facts. Casbin remains the sole access engine.
Custom dates/basic close exist; rich P10 closing review is not proven complete.

Validation is DEEP: meaningful success/refusal/boundary, rollback, duplicate/retry and regression
cases; permission denial and affected API contracts; real disposable-PostgreSQL tests for
locking/triggers. Use read-only reviewer; if unavailable report the missing independent gate.
No full suite without shared-impact/release justification. Never weaken financial checks.

Complete only the authorized slice; reconcile affected totals/reports, record exact commands,
limits and Handoff. Schema work also uses the existing database-migration skill. No production
writes, numbering/posting during print, deployment or commits without explicit authorization.
