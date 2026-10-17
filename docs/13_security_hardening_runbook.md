# Security hardening and production rollout

This application is hardened in code, but production security also depends on
the GitHub environment, AWS host, DNS, TLS, and backup configuration. Complete
this checklist before deploying the hardened release.

## 1. Configure production secrets

Create independent, randomly generated values (at least 32 characters) for every
secret the deployment reads; the list lives with the deployment itself, in
`docs/12_deployment_runbook.md` §17 ("Secrets and variables"). Never reuse one
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
claim the administrator account. When the host must not be exposed before
provisioning, create the administrator headlessly with
`python -m app.create_admin` (see the deployment runbook).

## 2. Protect delivery and the host

- Protect `main`: require a pull request, approval, and the `Dev CI` check. The
  aggregate check fails closed unless tests, lint, type checks, dependency
  audits, secret-history scanning, static analysis, and Docker builds all pass.
- Add required reviewers to the GitHub `production` environment.
- Permit public inbound traffic only on TCP 80/443. Restrict SSH to a trusted
  administrative IP or replace it with AWS Systems Manager Session Manager.
- Enable EC2 and EBS encryption, automatic OS security updates, CloudTrail, and
  GuardDuty. Alert on unusual authentication and network activity.
- Keep Docker data services private. Only nginx publishes host ports in the
  production compose file.

## 3. Deploy and verify

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

## 4. Backups and recovery

The deployment creates a checksummed database dump before release, but a dump
stored only on the EC2 host is not a disaster-recovery backup. Send encrypted
database backups to a separate AWS account or protected S3 bucket with
versioning, retention, and object lock. For stronger recovery objectives, use
RDS automated backups and point-in-time recovery.

Run a documented restore drill at least quarterly. A backup is not considered
verified until it has been restored and the application health and core
financial totals have been checked.

## 5. Remaining defence-in-depth work

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

