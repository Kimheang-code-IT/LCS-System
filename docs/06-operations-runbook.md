# Operations Runbook

## Environments and hosting

Hostinger VPS is the approved intended production baseline. Actual resources, host identity,
connectivity, service health and recurring costs require live verification. Historical EC2
references are not evidence of the current provider. Production is a runtime host; use the
existing release bundle/image workflow, not ad hoc source edits on the host.
Keep development, isolated test/restore, and production data separate.

## Local setup and configuration

Use `.env.example` templates; supply secrets locally without displaying them.
From the repository root:

```bash
docker compose -f infrastructure/docker-compose.yml up -d --build
docker compose -f infrastructure/docker-compose.yml ps
```

These are operational instructions, not commands executed by foundation creation.
Local default ports: frontend 80, backend 8000, PostgreSQL 5432, Redis 6379,
MinIO 9000/9001; env-driven bindings apply. The local backend runs Alembic on startup.
An empty database uses `/auth/setup`; baseline provisioning is described in security.
Settings controls application/security/localization configuration; deployment secrets remain
restricted. Inspect names/presence only. See [retained detailed runbook](11_deployment_and_security.md).

## Deployment and rollback

Preserve existing CI/CD. Dev CI does not deploy; production workflow builds/selects immutable
images, verifies a pre-migration dump, runs Alembic explicitly, starts the release, and checks
health. Prior images are preserved for rollback. Application image rollback does not undo
database changes; do not automatically restore over live data or run downgrade.
Production images start Uvicorn, not automatic migrations.
Coordinate maintenance announcements/status, protect in-flight financial transactions,
verify backups before risky operations, and obtain release authorization.
Use existing workflow rollback inputs and runbook; exact live recovery remains unverified.

## Backup and recovery requirements

Daily automated PostgreSQL backup is mandatory, with encrypted off-host storage, integrity
checks, failure alerts, a defined schedule/retention policy and isolated restore tests.
Protect files, metadata/references, required configuration and securely recoverable secrets.
Coordinate database and attachment recovery points; record cutoff times and verify referenced
files exist after restore. Same-host volumes and Google Sheets mirrors are not disaster recovery.

Current repository evidence: production workflow uses `pg_dump -Fc`, nonempty/archive-list
checks and SHA-256; optional S3 copies request KMS encryption. It is deployment-triggered,
not proof of daily scheduling. Local dumps older than 30 days are currently removed by that
workflow; this existing behavior is not an approved retention policy. Changes require later
approval. Attachment backup completeness, external scheduling, alerts and actual restoration
are unverified. WAL/PITR is conditional on accepted recovery needs, not automatically required.

## Isolated recovery procedure and acceptance

1. Obtain authorization, recovery owners, safe isolated target and approved secret access.
2. Select a verified database dump and compatible file/configuration recovery set.
3. Verify integrity; use `infrastructure/restore-db.sh` only after reviewing its isolated-target
   safeguards. Never point a drill at the production database.
4. Restore files/configuration through the approved provider mechanism; block external side
   effects such as notification delivery from the test environment.
5. Verify login, references, document counts, attachments, source links, ledger balance and
   report reconciliation; record actual recovery point and elapsed time.
6. Record failures, cleanup plan and acceptance evidence in S12 before declaring recoverability.

RPO 24 hours and RTO 4 hours are proposals. Daily intervals plus transfer lag may exceed a
24-hour loss window; measure actual recoverable points. Availability percentage, retention,
restore frequency and secure-secret recovery ownership remain TBD.

## Monitoring and incidents

Check `/health` and `/health/ready`, release health checks, request-correlated errors,
disk/storage capacity, backup age/failure, certificate expiry, authorization failures and
posting failures. Thresholds, monitoring stack, alert routes and named responders are TBD.
On an incident, preserve evidence and records; assess containment/rollback with authorized
owners, communicate status, and validate recovery. Never silently discard failed transactions.
No live production checks or restore drill were performed for this foundation.
