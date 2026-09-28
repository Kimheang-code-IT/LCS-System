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
- [ ] Authorization and permission tests passed.
- [ ] Financial posting tests passed.
- [ ] Migration reviewed.
- [ ] Database backup completed and verified.
- [ ] Rollback image available.
- [ ] Stakeholders notified.

## 7. Standard Deployment

Production deployment is automated by `.github/workflows/production.yml` on
every push to `main` (`dev` is validated by Dev CI, then a pull request into
`main` is reviewed and merged manually). The manual steps below describe the
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
- verify journal constraints;
- prepare rollback or forward-fix plan.

Never run destructive migration operations without an approved backup and migration plan.

## 9. Smoke Tests

- `GET /health` returns success.
- `GET /health/ready` confirms dependencies (reachable through nginx at `/health`).
- An empty database shows the first-run `/setup` page; after setup a user can log in.
- A user only sees pages and actions their roles permit.
- A quotation draft can be created.
- An accepted test quotation can convert once.
- A service charge can issue without creating a journal.
- A financial draft can be created.
- A balanced test document can post.
- An unbalanced journal is rejected.
- A closed period rejects posting.
- Attachment upload and download work for an authorized user.
- A user without the required permission is denied.

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
6. Verify role/permission isolation.
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
gh workflow run "Production" --ref main -f image_tag=sha-<short-commit>
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
gh workflow run "Production" --ref main

# roll back to a previous immutable image without rebuilding
gh workflow run "Production" --ref main -f image_tag=sha-<short-commit>

# restore a pre-deployment backup (run on the EC2 host)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists \
  < "$HOME/lcs-backups/freight-<timestamp>.dump"
```

Do not seed data manually: migrations leave the database empty and the first-run
`/setup` page (or `create_admin`) provisions the initial records — the
administrator, the built-in Platform Administrator role, default document
sequences for the current year, and the default app info/config. No finance or
business data is seeded, and every other role is entered manually from
Roles & Permissions.

## 16. Incident Evidence

Preserve:

- deployment version;
- migration version;
- application logs;
- audit events;
- database metrics;
- request and correlation IDs;
- affected user and role;
- financial document and journal IDs.

## 17. CI/CD Pipeline and Branch Protection

### Flow

push to `dev` → Dev CI → pull request `dev` → `main` → required `Dev CI` passes
→ manual review + manual merge → `production.yml` on `main` → production tests
→ build immutable `sha-<short>` images → GHCR → database backup → transfer
runtime files to `/opt/lcs` → Docker Compose recreate → Alembic migration/startup
→ HTTPS readiness check.

Production never deploys from `dev`; the merge to `main` is manual.

### Workflows

- `dev-ci.yml` (`Dev CI`) — runs on pushes to `dev` and on pull requests
  targeting `main`. Branch-aware concurrency
  (`github.head_ref || github.ref_name`, `cancel-in-progress: true`) cancels
  outdated runs. Runs backend ruff + pytest, frontend lint + typecheck + test,
  and Docker build validation for both images. It never deploys, never SSHes to
  EC2 and never pushes images to GHCR.
- `production.yml` (`Production`) — runs only on pushes to `main` or manual
  dispatch. Validates, builds `sha-<short>` images, pushes to GHCR, transfers the
  runtime files to `/opt/lcs`, backs up PostgreSQL, deploys the exact tag,
  recreates the stack (Alembic runs on backend start) and verifies HTTPS
  readiness.

### EC2 runtime-only architecture

EC2 is a Docker runtime host only. It does **not** hold the application Git
repository and never runs `git clone/pull/fetch/reset`. The `production.yml`
deploy job transfers only this runtime bundle to `/opt/lcs`:

```text
/opt/lcs/
  compose.yml              # from deploy/compose.yml
  nginx/production.conf    # from infrastructure/nginx/production.conf
  .env                     # generated by the workflow, chmod 600, never committed
```

`compose.yml` builds nothing; it pulls the prebuilt, **public** GHCR
`sha-<short>` images (no GHCR login on the host). Only the frontend (nginx)
publishes host ports (80/443); postgres, redis, minio and backend are reachable
only on the internal Docker network via their service names. The workflow never
runs `docker compose down -v`.

Persistent state lives in Docker named volumes and the deploy user's home:

- `freight_forwarding_freight_postgres_data` — PostgreSQL data
- `freight_forwarding_freight_redis_data` — Redis data
- `freight_forwarding_freight_minio_data` — MinIO objects
- `freight_forwarding_freight_uploads` — backend `/app/storage`
- `freight_forwarding_certbot_etc` / `_certbot_www` — TLS certificates + ACME webroot
- `$HOME/lcs-backups` — pre-deployment PostgreSQL dumps (outside the repo)

`docker compose up -d` recreates containers but never removes volumes.

### Fresh EC2 bootstrap (clean host)

On a clean host the certificate volume is empty and `production.conf` references
a certificate that does not exist yet — nginx will not start. Prepare the host
**before** the first workflow deploy:

```bash
# 0. /opt/lcs must exist and be writable by the deploy user.
sudo mkdir -p /opt/lcs/nginx && sudo chown -R "$USER":"$USER" /opt/lcs

# 1. DNS must already resolve. Issue the cert into the exact named volume the
#    stack uses; port 80 must be free.
sudo docker run --rm -p 80:80 \
  -v freight_forwarding_certbot_etc:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  -d lcslog.minidev.in \
  --email you@example.com --agree-tos --no-eff-email
```

Then run the Production workflow; it transfers `compose.yml` +
`nginx/production.conf`, writes `.env`, and brings the stack up.

### Browser-facing MinIO (presigned S3 URLs)

MinIO is internal to the Docker network and has **no** host port or public
subdomain. The main nginx server (`infrastructure/nginx/production.conf`)
proxies the bucket path `/freight-attachments/` to `minio:9000`, preserving the
`Host` and `Authorization` headers so the SigV4 signature validates. The backend
signs browser upload/download URLs with `S3_PUBLIC_ENDPOINT_URL`, which must be
the main origin:

- `S3_PUBLIC_ENDPOINT_URL=https://lcslog.minidev.in` (the default).
- The certificate only needs `lcslog.minidev.in` — no storage DNS/cert.
- Keep the nginx `/freight-attachments/` path in sync with `S3_BUCKET`.
- Presigned URLs are same-origin, so no cross-origin (CORS) rules are needed.

### Required branch-protection check

Protect `main` with a ruleset requiring:

- a pull request before merge;
- the **`Dev CI`** status check;
- successful checks before merge;
- blocked force pushes and blocked branch deletion.

The merge is manual; nothing auto-merges `dev` into `main`.

### Image tags

- `sha-<short-commit>` — immutable, used by production. The build and the deploy
  use the same value, computed in the `resolve` job.
- `latest` — convenience only; production must not depend on it.

### Secrets and variables (production environment)

Secrets: `AWS_SSH_KEY`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`,
`MINIO_ROOT_PASSWORD`. `GHCR_TOKEN` is **not needed** — the GHCR images are
public and EC2 does no registry login.

Variables: `AWS_HOST`, `AWS_USER`, optional `AWS_PORT`; `MINIO_ROOT_USER`, and
optional `S3_PUBLIC_ENDPOINT_URL` (defaults to `https://lcslog.minidev.in`),
`POSTGRES_DB`, `POSTGRES_USER`, `S3_BUCKET`, `S3_REGION`, `CORS_ORIGINS`.
`NUXT_PUBLIC_SITE_URL` stays a **repository-level** build variable (the build
job does not use the environment).

Secrets are forwarded through the SSH action's `envs` mechanism and written to
`/opt/lcs/.env` atomically (0600); they are never printed and never committed.
