---
name: deployment-devops
description: Use when working on LCS Docker Compose, environment configuration, CI/CD workflows, image builds, PostgreSQL backup and restore, monitoring, release verification, or production rollback procedures.
---

# Deployment and DevOps

Ship the LCS platform safely. The EC2 host is **runtime-only** — the Git repository
is not cloned there — so every deployment artifact must be self-contained.

## When to use

- Changing `infrastructure/docker-compose.yml`, any Dockerfile, or nginx config.
- Changing a GitHub Actions workflow or the deploy transfer set.
- Adding or changing an environment variable.
- Taking a backup, rehearsing a restore, or preparing a release.
- Planning a rollback.

## Required inputs

1. What is changing: compose, image, proxy, workflow, or environment.
2. Whether it affects the database schema (then also load `database-migration`).
3. Whether the change is reversible on the host without a redeploy.

## Project references

| Document | Use it for |
|---|---|
| `docs/11_deployment_and_security.md` | The authoritative deploy, backup, restore, rollback, and hardening procedure |
| `docs/11_deployment_and_security.md` §8 | Schema apply/verify/rollback and the migration boundary |
| `AGENTS.md` §Commands, §Run stack | Ports, env files, branch and CI model |
| `infrastructure/`, `deploy/`, `.github/workflows/` | The artifacts themselves |

## Topology

| Service | Host port | Notes |
|---|---|---|
| frontend (nginx) | 80 | Serves the static SPA and reverse-proxies `/api/` |
| backend (FastAPI) | 8000 | Runs `alembic upgrade head` on start |
| PostgreSQL | 5432 | Authoritative store |
| Redis | 6379 | Cache; never authoritative |
| MinIO | 9000 / 9001 | S3-compatible attachment storage |

Ports are env-driven in `infrastructure/.env`. Two long-lived branches: `dev`
(integration) and `main` (protected). `dev-ci.yml` runs the gates plus a Docker
build check on pushes to `dev` and PRs into `main`; `production.yml` runs on `main`
or manual dispatch and builds immutable `sha-<short>` images, pushes to GHCR, backs
up the database, and deploys. Protect `main` with a ruleset requiring a pull request
and the **`Dev CI`** status check.

## Workflow

1. **Validate locally first.**

   ```bash
   docker compose -f infrastructure/docker-compose.yml up -d --build
   docker compose -f infrastructure/docker-compose.yml ps
   docker exec ff-api curl -fsS http://localhost:8000/health
   curl -fsS http://localhost:8000/health/ready     # database + redis
   ```

2. **Never put a secret in a tracked file.** `.env` files are gitignored; only
   `.env.example` is committed and it must contain placeholders, never real values.
   Production secrets come from GitHub environment secrets/vars, which generate
   `/opt/lcs/.env` on the host.
3. **Back up before any schema change.** `pg_dump -Fc` plus WAL archiving for
   point-in-time recovery, then **restore the dump into a scratch database and
   confirm the revision and row counts**. An unverified backup is not a backup.
   `docs/11_deployment_and_security.md` §11-§12 has the exact commands.
4. **Deploy in the order `docs/11_deployment_and_security.md` §7 states:** back up →
   deploy the backend (its entrypoint migrates before serving) → run the post-deploy
   verification → deploy the frontend → keep the previous image tagged for rollback.
5. **Verify after deploying** (`docs/11_deployment_and_security.md` §9):
   - `SELECT version_num FROM alembic_version;` matches the release head;
   - table and view counts match the expected shape;
   - `pre_migration_counts.sql` diffed against the pre-deploy output;
   - the ledger still nets to zero and there are no unvalidated foreign keys;
   - `/health` and `/health/ready` respond.
6. **Roll back by the documented boundary.** `alembic downgrade <previous-release-head>`
   plus redeploying the previous image is the supported path. Do not attempt
   `alembic downgrade base` — a pre-existing defect in legacy revision
   `6e862ce04e46` makes it impossible; use the restore procedure instead.

## Security requirements

- TLS terminates at the proxy; the backend is not exposed directly in production.
- Database, Redis, and MinIO are not published to the public internet.
- `.env` files are `chmod 600`, owned by the deploy user, and never copied into an
  image layer or a build log.
- A private key inside the working tree (`docs/lcssystem.pem`) is a finding: report
  it and recommend moving it outside the repository. Do not delete it unasked.
- The backend health endpoints are unauthenticated by design; keep them free of
  version, path, or configuration detail.
- CI must run on the protected branch and require the status check; never add
  `continue-on-error` to a gate step to unblock a release.

## Backup and recovery

- `backup_runs` / `backup_states` / `backup_records` are Google-Sheets replication
  telemetry. They are **not** a PostgreSQL backup and must never be described as one.
- Required: encrypted off-host base backups plus WAL archiving, with a periodic
  restore drill.
- The recovery path is: stop the app, restore into a new database, verify, then
  rename the damaged database aside (keep it for forensics) and the restore into
  place. Never restore over the live database.

## Testing

| Check | Command |
|---|---|
| Compose config is valid | `docker compose -f infrastructure/docker-compose.yml config` |
| Stack healthy | `docker compose ... ps` and both `/health` endpoints |
| Gates | backend `pytest` + `ruff`; frontend `lint` + `typecheck` + `test` |
| Migration apply/rollback | `docs/11_deployment_and_security.md` §8 |
| Restore drill | `docs/11_deployment_and_security.md` §12 |

Run the restore drill at least once per release train, not just once per
environment.

## Acceptance criteria

- Compose config parses and the stack becomes healthy from a clean checkout.
- No secret is added to a tracked file or an image layer.
- A backup was taken **and restored** before any schema change, and the drill result
  is recorded.
- The post-deploy verification in `docs/11_deployment_and_security.md` §9 has been
  executed with its output captured.
- The rollback path is stated, uses the supported revision boundary, and the
  previous image is still available.
- Any verification that was not run is named as unverified in the report.

## Expected outputs

- Changed compose / Dockerfile / nginx / workflow / `.env.example`.
- An updated procedure in `docs/11_deployment_and_security.md` when the steps changed.
- A recorded verification result (commands and observations).
- Outstanding operational risks appended to `docs/11_deployment_and_security.md` §18.
