# Deployment and Security

## 1. Purpose

This document is the operational reference for deploying, verifying, monitoring,
backing up, restoring, and rolling back the platform, and for the production
security controls around it. API contracts are in `docs/07_api_documentation.md`,
RBAC in `docs/09_roles_and_permissions.md`, and the schema in
`docs/06_database_design.sql`.

## 2. Deployment Components

- Nuxt 4 static SPA (`nuxt generate`), served by nginx.
- FastAPI API (Uvicorn).
- PostgreSQL database.
- Redis (optional; disables gracefully when unavailable).
- Object storage (MinIO / S3-compatible).
- nginx reverse proxy (serves the SPA and proxies `/api/`).
- Monitoring and log aggregation (required; not currently deployed).

Default host ports: frontend `80`, backend `8000`, PostgreSQL `5432`,
Redis `6379`, MinIO `9000` / console `9001` (all env-driven in
`infrastructure/.env`).

## 3. Environments

The repository defines a local Docker Compose stack and the production AWS
deployment. A staging environment is optional and is not provisioned here. Each
environment must have separate:

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
5. Deploy the API image in a rolling or controlled update. Its entrypoint runs
   `alembic upgrade head` before serving; if a separate migration job is used,
   run it once and do not let the entrypoint migrate concurrently.
6. Verify migration completion.
7. Deploy the frontend (nginx) image.
8. Resume normal traffic.
9. Run smoke tests.
10. Monitor errors and latency.
11. Announce deployment completion.

## 8. Migration Safety

Before applying a migration:

- test it against a production-size copy;
- inspect locks and expected duration;
- verify all new foreign keys;
- verify indexes;
- verify journal constraints;
- prepare rollback or forward-fix plan.

Never run destructive migration operations without an approved backup and migration plan.

### Current chain and rollback boundary

- Current Alembic head: `c3d4e5f6a7b8` (Places removal). The schema has 65
  tables.
- The backend container runs `alembic upgrade head` on start. In a controlled
  deployment, run it as a separate migration step before switching traffic.
- Every new revision must be additive and must have a working `downgrade()`.
  The migration is reviewed against a production-size copy; locks, duration,
  foreign keys, indexes, and journal constraints are checked before apply.
- Do not roll back schema and application independently. A code rollback keeps
  the database at its current revision unless a tested down migration is part of
  the release plan.
- A full `alembic downgrade base` is **not** supported: the legacy revision
  `6e862ce04e46` fails while dropping an index that an earlier revision already
  removed. The supported automated rollback boundary is the previous release
  revision. Deeper recovery uses the pre-deployment dump (section 11) or a forward fix.
- RBAC migration `a2b3c4d5e6f7` is data-preserving: it expires duplicate legacy
  assignments, normalizes the retained current assignment, and maps active users
  without a role to `MIGRATED_NO_ACCESS` (zero permissions). After deployment,
  review that role's assigned-user list in Administration -> Roles & Permissions
  and explicitly reassign each account. Do not grant permissions to the migration
  role as a shortcut.
- The generated SQL reference is documentation only. Regenerate it with
  `uv run python scripts/generate_schema_docs.py` and verify it with
  `--check --strict`; never apply it with `psql` as a migration.

## 9. Smoke Tests

- `GET /health` returns success.
- `GET /health/ready` confirms dependencies; both are reachable through nginx.
- An empty database shows the first-run `/auth/setup` page; after setup a user can log in.
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

The application also has a Google Sheets backup scheduler; it mirrors supported
tables for reporting and is **not** a PostgreSQL backup. Do not use it for
disaster recovery.

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

No monitoring or alerting stack is deployed yet. The list below is the required
configuration; until it exists, a failed posting, lockout, or backup has no
external signal. This is an open production risk.

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

## 15. CI/CD Pipeline and Branch Protection

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
  outdated runs. Runs backend ruff + pytest, dependency and static security
  scans, frontend lint + typecheck + test, secret scanning, and Docker build
  validation for both images. It never deploys, never SSHes to EC2 and never
  pushes images to GHCR.
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
`CSRF_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `MINIO_ROOT_PASSWORD`,
`S3_SECRET_KEY`. `GHCR_TOKEN` is **not needed** — the GHCR images are public and
EC2 does no registry login. This list is the single source; the security section
(§16) points here instead of repeating it.

Variables: `AWS_HOST`, `AWS_USER`, optional `AWS_PORT`; `MINIO_ROOT_USER`, and
optional `S3_PUBLIC_ENDPOINT_URL` (defaults to `https://lcslog.minidev.in`),
`POSTGRES_DB`, `POSTGRES_USER`, `S3_BUCKET`, `S3_REGION`, `CORS_ORIGINS`.
`NUXT_PUBLIC_SITE_URL` stays a **repository-level** build variable (the build
job does not use the environment).

Secrets are forwarded through the SSH action's `envs` mechanism and written to
`/opt/lcs/.env` atomically (0600); they are never printed and never committed.

## 16. Security Hardening

This application is hardened in code, but production security also depends on
the GitHub environment, AWS host, DNS, TLS, and backup configuration. Complete
this checklist before deploying the hardened release.

### 16.1 Configure production secrets

Create independent, randomly generated values (at least 32 characters) for every
secret the deployment reads; the list lives with the deployment itself, in
section 15 of this document ("Secrets and variables").
Never reuse one
value for multiple settings. Keep `S3_ACCESS_KEY` as a non-root application
identity (the deployment defaults it to `lcs-app`).

If the current database already contains encrypted customs-account passwords,
first deploy with `FIELD_ENCRYPTION_KEY` set to the **current** JWT signing
secret. Re-encrypt those records with a newly generated field-encryption key in
a planned migration before rotating the JWT key. Losing the field-encryption
key makes those values unrecoverable.

The first-run setup page (`/auth/setup`) is accepted only while no user exists
and closes as soon as the first administrator is created. On a fresh deployment,
complete setup immediately — until then, whoever reaches the site first could
claim the administrator account.

### 16.2 Protect delivery and the host

- Protect `main`: require a pull request, approval, and the `Dev CI` check. The
  aggregate check fails closed unless tests, lint, type checks, dependency
  audits, secret scanning, static analysis, and Docker builds all pass.
- Add required reviewers to the GitHub `production` environment.
- Permit public inbound traffic only on TCP 80/443. Restrict SSH to a trusted
  administrative IP or replace it with AWS Systems Manager Session Manager.
- Enable EC2 and EBS encryption, automatic OS security updates, CloudTrail, and
  GuardDuty. Alert on unusual authentication and network activity.
- Keep Docker data services private. Only nginx publishes host ports in the
  production compose file.

### 16.3 Deploy and verify

The production workflow backs up the database, deploys immutable image tags,
checks readiness, and restores the previous images if readiness fails. After a
deployment, verify:

```bash
curl -fsS https://lcslog.minidev.in/health
curl -fsSI https://lcslog.minidev.in/
```

Confirm HSTS, CSP, `X-Content-Type-Options`, and frame restrictions in the
response. Test login, refresh, logout, password reset, a protected write, file
upload/download, and a role with restricted permissions. Confirm that access
and refresh tokens are HttpOnly cookies and do not appear in local storage.

### 16.4 Backups and recovery

The deployment creates a checksummed database dump before release, but a dump
stored only on the EC2 host is not a disaster-recovery backup. Send encrypted
database backups to a separate AWS account or protected S3 bucket with
versioning, retention, and object lock. For stronger recovery objectives, use
RDS automated backups and point-in-time recovery.

Run a documented restore drill at least quarterly. A backup is not considered
verified until it has been restored and the application health and core
financial totals have been checked.

### 16.5 Remaining defence-in-depth work

The frontend audit has two narrowly scoped temporary exceptions:
`CVE-2026-85393` (`node-forge` through Nitro's development listener) and
`CVE-2026-93687` (`braces` through build-time file globbing). Neither package is
copied into the production nginx image, which contains only generated static
files. The audit still blocks every other high or critical advisory. Remove
each exception as soon as its upstream dependency publishes a fixed release.

- Put CloudFront and AWS WAF in front of nginx if the service is internet-facing.
- Add MFA for privileged users; the current application does not implement MFA.
- Add malware scanning/quarantine (for example ClamAV or a managed scanner) if
  customers upload files from untrusted sources. Current controls enforce file
  size, extension, content signature, safe disposition, and short-lived links,
  but they are not antivirus scanning.
- Resolve high/critical package audit findings as updated packages become
  available and keep Dependabot and the scheduled security workflow enabled.
- Review authentication, authorization, audit logs, backup restores, and access
  keys at least quarterly. Rotate secrets immediately after suspected exposure.

## 17. Security Architecture

- TLS terminates at nginx for all external traffic; HTTP redirects to HTTPS.
- Passwords are Argon2id hashes and are never readable through any API.
- Access tokens are short-lived JWTs (default 24 hours); refresh tokens rotate and
  the previous token is revoked. The browser receives HttpOnly cookies and a
  signed double-submit CSRF token.
- Permission checks are enforced by `require_permission(...)` on the API; the UI
  only hides what the API would already refuse.
- Retrievable integration secrets, such as customs-account passwords, use Fernet
  encryption with `FIELD_ENCRYPTION_KEY`. Losing that key makes the values
  unrecoverable.
- Sensitive columns are excluded from the Google Sheets backup mirror.
- Secrets never appear in logs, responses, seed data, audit payloads, or the
  repository. Production `.env` files are written atomically with mode 0600.
- First-run setup is accepted only while no user exists. Complete it immediately
  or provision the administrator headlessly.

## 18. Known Risks and Limitations

| Risk | Impact | Status |
|---|---|---|
| A private key sits in `docs/lcssystem.pem` | It is untracked and gitignored, but inside the working tree and readable by any process with filesystem access; a lost ignore rule could expose it | **Open (S1)** - owner decision required; recommend moving it outside the repository and rotating it if exposure is suspected |
| No monitoring or alerting | Failed postings, lockouts, backup failures, and 5xx spikes produce no signal | Open |
| PostgreSQL guard triggers are not run in CI | A trigger regression can pass the SQLite suite | Open; run `tests/sql/integrity_guards.sql` before release |
| Full `alembic downgrade base` fails at `6e862ce04e46` | Recovery below the previous release needs a restore, not downgrade | Known limitation; supported boundary is the previous release |
| A database owner can disable guards with `SET LOCAL lcs.allow_financial_purge` | The guards defend against mistakes, not a hostile DBA | Accepted; least-privilege DB roles are required |
| Cross-currency allocation is not implemented | Payment and invoice must share a currency | Accepted; a reviewed FX design is required |
| No MFA for privileged users | A stolen password is sufficient for login | Open |
| No malware scanning on uploads | File type/size/signature are checked, but content is not scanned | Open; add a scanner if untrusted uploads are accepted |
| Off-host PostgreSQL backups are not automated | A host-level dump is not disaster recovery | Partial; send encrypted dumps to a separate account/bucket |
| No browser E2E | Focus, tab reveal, and responsive layout are checked manually | Open; see `docs/10_testing_and_quality.md` |

## 19. Operational Commands

From the repository root:

```bash
# build and start the local stack
docker compose -f infrastructure/docker-compose.yml up -d --build

# status and logs
docker compose -f infrastructure/docker-compose.yml ps
docker compose -f infrastructure/docker-compose.yml logs -f backend

# migrations inside the backend container
docker compose -f infrastructure/docker-compose.yml exec backend alembic upgrade head

# health through nginx (frontend port 80)
curl http://localhost/health/ready

# quality gates
cd backend && uv run pytest -q && uv run ruff check .
cd ../frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm generate
```

Production deploy, rollback, and restore commands are in section 15 and section 13.
The production workflow is manual-dispatch for rollback and automatic on `main` for
deployment.

## 20. Incident Evidence

Preserve:

- deployment version and image tag;
- migration revision;
- application logs and request IDs;
- audit events;
- database metrics;
- affected user and role;
- financial document and journal IDs.
