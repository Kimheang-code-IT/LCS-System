# Deployment Runbook

## 1. Purpose

This runbook defines the repeatable procedure for deploying, verifying, monitoring, backing up, restoring, and rolling back the platform.

## 2. Deployment Components

- SvelteKit web application.
- FastAPI API.
- Background worker.
- PostgreSQL database.
- Redis.
- Object storage.
- Reverse proxy/TLS termination.
- Monitoring and log aggregation.

## 3. Environments

```text
local → development → staging → production
```

Each environment must have separate:

- database;
- object-storage bucket;
- Redis instance;
- secrets;
- external integration credentials;
- monitoring namespace.

Never use production secrets in lower environments. Production data must not be copied to lower environments without approved anonymization.

## 4. Prerequisites

- Versioned application image.
- Reviewed database migration.
- Verified backup.
- Required secrets available.
- TLS certificate and DNS.
- Database connectivity.
- Object-storage bucket.
- Rollback version identified.
- Maintenance window approved where required.

## 5. Required Secrets

- `DATABASE_URL`.
- Application session/JWT secret.
- Object-storage credentials.
- Customs-credential encryption key or secret-manager credentials.
- Email credentials if enabled.
- External integration credentials.

Secrets must not be committed to Git, included in Docker images, stored in seed files, or written to logs.

## 6. Pre-Deployment Checklist

- [ ] Change request approved.
- [ ] Release version tagged.
- [ ] CI build passed.
- [ ] Dependency and image scans passed.
- [ ] Unit tests passed.
- [ ] Integration tests passed.
- [ ] Authorization and cross-branch tests passed.
- [ ] Financial posting tests passed.
- [ ] Migration reviewed.
- [ ] Database backup completed and verified.
- [ ] Rollback image available.
- [ ] Stakeholders notified.

## 7. Standard Deployment

1. Announce deployment start.
2. Verify service and database health.
3. Pause scheduled jobs that may conflict with migration.
4. Take a fresh database backup.
5. Deploy the API image in a rolling or controlled update.
6. Run database migrations once through a migration job.
7. Verify migration completion.
8. Deploy web image.
9. Deploy worker image.
10. Resume scheduled jobs.
11. Run smoke tests.
12. Monitor errors and latency.
13. Announce deployment completion.

## 8. Migration Safety

Before applying a migration:

- test it against a production-size copy;
- inspect locks and expected duration;
- verify all new foreign keys;
- verify indexes;
- verify organization and branch consistency;
- verify journal constraints;
- prepare rollback or forward-fix plan.

Never run destructive migration operations without an approved backup and migration plan.

## 9. Smoke Tests

- `GET /health/live` returns success.
- `GET /health/ready` confirms dependencies.
- User can log in.
- User sees only assigned organization and branches.
- A quotation draft can be created.
- An accepted test quotation can convert once.
- A service charge can issue without creating a journal.
- A financial draft can be created.
- A balanced test document can post.
- An unbalanced journal is rejected.
- A closed period rejects posting.
- Attachment upload and download work for an authorized user.
- Cross-branch access is denied.

## 10. Finance Safety Verification

After deployment, verify:

- chart-of-accounts mappings;
- posting rules;
- base currency;
- accounting periods;
- document sequences;
- journal balance enforcement;
- receipt/payment allocation limits;
- reversal behavior;
- branch dimensions;
- ledger report reconciliation.

Do not post real financial documents as a smoke test unless the business approves a controlled test period.

## 11. Backup

### Database

- Schedule daily full backups.
- Enable point-in-time recovery where supported.
- Encrypt backups.
- Store backups separately from the primary database.
- Retain backups according to policy.

### Object storage

- Enable versioning where supported.
- Configure retention and deletion policy.
- Back up metadata and storage-key mappings.
- Test file restoration.

## 12. Restore Drill

1. Provision an isolated recovery environment.
2. Restore the latest database backup.
3. Restore object-storage data or versioned objects.
4. Deploy the matching application version.
5. Run integrity checks.
6. Verify organization/branch isolation.
7. Verify financial totals and journal balance.
8. Verify representative attachments.
9. Record recovery time and issues.

## 13. Rollback

Use rollback when the release causes critical errors and a forward fix is not safer.

1. Stop or limit new writes if required.
2. Preserve logs and request IDs.
3. Keep the database available for investigation unless corruption is suspected.
4. Roll back web, API, and worker images to the previous version.
5. Do not automatically roll back database migrations.
6. Apply a tested down migration only when safe.
7. Prefer a forward migration for data-preserving corrections.
8. Reconcile documents and journals created during the incident.
9. Verify health and smoke tests.
10. Record the incident and corrective actions.

## 14. Monitoring and Alerts

Alert on:

- API 5xx rate;
- authentication failure spikes;
- authorization denial spikes;
- database connection exhaustion;
- migration failure;
- worker queue age;
- repeated job retries;
- object-storage failures;
- backup failures;
- journal-posting failures;
- unbalanced-journal attempts;
- unusual customs-password retrieval.

## 15. Operational Commands

Use the project's approved scripts rather than ad hoc production commands:

```text
make build
make test
make migrate
make migrate-status
make seed-dev
make healthcheck
make backup
make restore-test
```

The exact commands should be implemented in the repository and documented with environment-specific safeguards.

## 16. Incident Evidence

Preserve:

- deployment version;
- migration version;
- application logs;
- audit events;
- database metrics;
- request and correlation IDs;
- affected organization and branch;
- financial document and journal IDs.
