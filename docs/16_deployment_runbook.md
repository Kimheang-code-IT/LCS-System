# Deployment Runbook

## 1. Purpose

This runbook defines the repeatable procedure for deploying, verifying, monitoring, backing up, restoring, and rolling back the platform.

## 2. Deployment Components

- Nuxt 4 static SPA (`nuxt generate`), served by nginx.
- FastAPI API (Uvicorn).
- PostgreSQL database.
- Redis (optional; disables gracefully when unavailable).
- Object storage (MinIO / S3-compatible).
- nginx reverse proxy (serves the SPA and proxies `/api/`).
- Monitoring and log aggregation.

Default host ports: frontend `80`, backend `8000`, PostgreSQL `5432`,
Redis `6379`, MinIO `9000` / console `9001` (all env-driven in
`infrastructure/.env`).

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

Production deployment is automated by `.github/workflows/publish.yml` on every
push to `main` (feature branches are validated by CI, auto-merged into `main`,
then the deploy workflow is dispatched). The manual steps below describe the
equivalent procedure and are used for exceptional/controlled deployments.

1. Announce deployment start.
2. Verify service and database health.
3. Drain or limit write traffic that may conflict with the migration.
4. Take a fresh database backup.
5. Deploy the API image in a rolling or controlled update.
6. Run database migrations once through a migration job.
7. Verify migration completion.
8. Deploy the frontend (nginx) image.
9. Resume normal traffic.
10. Run smoke tests.
11. Monitor errors and latency.
12. Announce deployment completion.

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

- `GET /health` returns success.
- `GET /health/ready` confirms dependencies (reachable through nginx at `/health`).
- An empty database shows the first-run `/setup` page; after setup a user can log in.
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

The deploy workflow takes a pre-deployment `pg_dump` (custom format) on the EC2
host before the stack is recreated. Backups are written outside the repository
and outside container filesystems, to `$HOME/lcs-backups/freight-<timestamp>.dump`
on the deploy user's home directory. The deployment aborts if the dump command
fails or produces an empty file. Nothing prints database credentials; the dump
reads `POSTGRES_USER`/`POSTGRES_DB` from the database container's own
environment.

- Schedule daily full backups.
- Enable point-in-time recovery where supported.
- Encrypt backups.
- Store backups separately from the primary database (copy off-host).
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
4. Roll back the frontend and backend images to the previous version.
5. Do not automatically roll back database migrations.
6. Apply a tested down migration only when safe.
7. Prefer a forward migration for data-preserving corrections.
8. Reconcile documents and journals created during the incident.
9. Verify health and smoke tests.
10. Record the incident and corrective actions.

### Rolling back the application (automated)

Images are immutable and tagged `sha-<short-commit>`. To redeploy an earlier
known-good image without rebuilding it, dispatch the deploy workflow with the
target tag:

```bash
gh workflow run "Build & Deploy" --ref main -f image_tag=sha-<short-commit>
```

The deploy job resolves that tag, backs up the database, pulls the exact image,
recreates the stack, and runs the HTTPS readiness check. It does not rebuild
images and does not roll back database migrations. `latest` is a convenience tag
only and must never be used for production rollback.

## 14. Monitoring and Alerts

Alert on:

- API 5xx rate;
- authentication failure spikes;
- authorization denial spikes;
- database connection exhaustion;
- migration failure;
- object-storage failures;
- backup failures;
- journal-posting failures;
- unbalanced-journal attempts;
- unusual customs-password retrieval.

## 15. Operational Commands

From the repository root:

```bash
# build and start the stack
docker compose -f infrastructure/docker-compose.yml up -d --build

# status / logs
docker compose -f infrastructure/docker-compose.yml ps
docker compose -f infrastructure/docker-compose.yml logs -f backend

# migrations and admin provisioning run inside the backend container
docker compose -f infrastructure/docker-compose.yml exec backend alembic upgrade head
docker compose -f infrastructure/docker-compose.yml exec backend \
  python -m app.create_admin --email admin@example.com --password 'Passw0rd!'

# health through nginx (frontend port 80)
curl http://localhost/health/ready

# local quality gates
cd backend && uv run pytest -q && uv run ruff check .
cd ../frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm generate
```

### Automated deploy / rollback / restore

```bash
# deploy current main (builds immutable sha-<short> images, backs up, deploys)
gh workflow run "Build & Deploy" --ref main

# roll back to a previous immutable image without rebuilding
gh workflow run "Build & Deploy" --ref main -f image_tag=sha-<short-commit>

# restore a pre-deployment backup (run on the EC2 host)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  < "$HOME/lcs-backups/freight-<timestamp>.dump"
```

Do not seed data manually: migrations leave the database empty and the first-run
`/setup` page (or `create_admin`) provisions the initial records — the
administrator, default document sequences for the current year, and the default
app info/config. No finance or business data is seeded.

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

## 17. CI/CD Pipeline and Branch Protection

### Flow

feature branch → CI → pull request → required CI passes → merge to `main`
→ `publish.yml` builds immutable images → GHCR → EC2 deploy → database backup
→ Docker Compose recreate → Alembic migration/startup → HTTPS readiness check.

### Workflows

- `ci.yml` — runs on every branch push and pull request. Branch-aware
  concurrency (`github.head_ref || github.ref_name`) cancels outdated runs. Path
  filtering skips the unaffected side for backend-only/frontend-only changes;
  workflow, infrastructure and lockfile changes run both.
- `auto-merge.yml` — triggered by `workflow_run` after CI succeeds. If the
  source branch has an open, same-repository pull request, it is squash-merged
  (respecting branch protection) and `publish.yml` is dispatched.
- `publish.yml` — builds `sha-<short-commit>` images for backend and frontend,
  publishes to GHCR, and deploys the exact tag to EC2. It does not re-run the CI
  suite; the required CI check on the pull request is the production gate.

### Required branch-protection check

Protect `main` and require the single aggregate check named **`CI`** (the
`ci-ok` job). The automated flow merges through the pull-request API, so it does
not bypass protection. Do not require mandatory reviews unless you are willing
to approve every deployment manually.

### Image tags

- `sha-<short-commit>` — immutable, used by production. The build and the deploy
  use the same value, computed in the `resolve` job.
- `main`, `v*` — informational tags.
- `latest` — convenience only; production must not depend on it.

### Secrets

`AWS_HOST`, `AWS_USER`, `AWS_SSH_KEY`, optional `AWS_PORT`; optional
`GHCR_TOKEN` (read:packages) falling back to `GITHUB_TOKEN`. Secrets are never
interpolated into the remote deploy script; they are forwarded through the SSH
action's `envs` mechanism.
