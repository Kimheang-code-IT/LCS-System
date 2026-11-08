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
restricted. Inspect names/presence only. See [retained detailed runbook](../archive/deployment-security-history.md).

## Deployment and rollback

Preserve existing CI/CD. Dev CI does not deploy; production workflow builds/selects immutable
images, verifies a pre-migration dump, runs Alembic explicitly, starts the release, and checks
health. Prior images are preserved for rollback. Application image rollback does not undo
database changes; do not automatically restore over live data or run downgrade.
Production images start Uvicorn, not automatic migrations.
Coordinate maintenance announcements/status, protect in-flight financial transactions,
verify backups before risky operations, and obtain release authorization.
Use existing workflow rollback inputs and runbook; exact live recovery remains unverified.

## Maintenance deployment and emergency recovery

Use **System Settings → Maintenance** or the shared controls in **Backup**: toggle, Reason,
and the document-header Save. The compact UI intentionally omits advanced configuration/history
and deployment forms; scheduling/destination configuration and recovery verification remain
available through the existing authorized maintenance APIs. This feature gates application admission; it does
not run a deployment, create a full PostgreSQL backup, automatically drain requests, or
prove a restore. The deployment verification API records accountable operator attestations, not
automated probes. No deployment/provider configuration was changed by this implementation.

1. For advanced operation, use `PUT /api/v1/settings/maintenance` to configure a public
   message, support contact, estimated downtime and timezone-aware start/end.
   Leave start blank for immediate activation. Optional negative Telegram group IDs are separate
   operations/developer destinations using the existing enabled bot. Use a verified destination
   controlled by the intended recipients; do not enter credentials in messages/reasons/references.
   Saving a schedule queues the advance announcement; active clients poll a warning every 30 seconds.
2. Enable the toggle, enter Reason and confirm the header Save; the client supplies the
   API's `MAINTENANCE` confirmation. API admission immediately evaluates shared persisted state;
   no process-local maintenance cache exists. Already-admitted requests and already-started backup
   tasks may finish normally. Wait for every replica's active requests, database write transactions,
   scheduled/external tasks and integrations to drain. Inspect operational metrics and
   `pg_stat_activity` through approved operator access; activation alone does not prove quiescence.
3. Scheduled backup starts are paused. Telegram delivery, monitoring and housekeeping remain active
   as control-plane work. External workers are outside this process and must be paused by their
   operator. Keep deployment blocked until the drain check actually passes.
4. Create and verify the approved pre-migration PostgreSQL dump, checksums/archive listing and
   coordinated file/configuration recovery set. Existing redacted JSON/R2/Sheets snapshots are
   insufficient as the database backup for this gate. Confirm backup completion before deployment;
   on failure record `backup_failed` through `POST /api/v1/settings/maintenance/deployment`,
   stop, and keep maintenance enabled.
5. Deploy only through the separately authorized release workflow. Validate migrations, database
   and backend health, authentication, important business workflows, and background jobs/integrations.
   Record any deployment/health failure immediately; never reopen automatically or on an end-time timer.
6. Once every check actually passes, record successful verification and a non-secret backup reference
   through the deployment verification API. Disable the toggle and confirm the header Save;
   the client supplies `REOPEN`. The server rejects stale revisions and reopening without successful
   verification. Lifecycle messages use the committed outbox: starts/ends to operations and developer
   groups; deployment results to developer. Existing system-health alerts use the developer group
   when configured and still respect system notification rules. Accepted-send/ack failures retain
   the existing possibility of duplicate Telegram delivery. Scheduled-start announcements are
   evaluated by the existing workers; disabled workers cannot deliver notifications.

**Database unavailable / emergency lockdown:** an authorized host operator can provision
`LCS_FORCE_MAINTENANCE=true` through the existing protected server environment and restart **all**
API replicas using the approved service procedure. No database lookup or recovery API credential
is needed for the public maintenance status in this mode. This is a DB-independent lockdown,
not a login/authorization bypass or a database repair tool. Do not open a public emergency-secret
endpoint. Host access/secret-manager credentials remain the existing recovery trust boundary.
If the API process or reverse proxy is unavailable, use the hosting incident procedure to keep
traffic closed; a SPA cannot replace a failed host.

Repair connectivity or restore the approved recovery set through the authorized operator process;
never delete business/session rows to regain access. Keep the force flag on while checking recovery.
Then use the authenticated maintenance controls to verify/reopen the persisted window, remove the
force flag on every replica, restart consistently and recheck public status plus denied/allowed
requests. Leaving even one replica on an old build/config is unsafe. Code rollback does not undo
database migrations; do not run automatic downgrade or overwrite production data.

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

## Planned cloud backup and integration operations

[Backup/recovery](../02-business/backup-and-recovery.md) specifies coordinated encrypted
PostgreSQL/files/config recovery; [provider setup](settings-and-provider-configuration.md)
owns dated limits/pricing and key/account requirements. Current R2 redacted snapshots and
Sheets restore remain preserved, accurately labeled and not declared full DR.

Target R2/Drive connections do not require/add local MinIO. Existing MinIO ports/upload storage
above describe current Compose, not a new dependency recommendation. Do not remove containers,
volumes or credentials during documentation. Migration needs authorized object/reference parity
and rollback. Daily policy, retention/key escrow, resource limits, outage observer and recovery
targets need named owners. Restore is staged/isolated by default, outside a web request and
maintenance-controlled; production cutover is separately authorized.
