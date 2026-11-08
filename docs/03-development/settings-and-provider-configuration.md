# Settings, Providers, Email Recovery and Security

Status: implementation-ready target contracts, 2026-11-04. Existing behavior is separately
classified in the [source inventory](../01-architecture/integration-architecture.md#current-implementation-inventory).
No provider is configured, account created, message sent or security setting changed by this task.
[Plan A–G](../04-implementation/plans/PLAN-0005-settings-integrations.md) controls future slices.

## SET-001 — Preserve the Settings experience

Keep Localization, Email, Telegram, Security and Backup tabs, existing page title/Refresh/More
Actions/Save Changes header and Nuxt UI/shared document components. General/Notifications
schema entries exist but are filtered from systemSettingsTabs; do not expose new sidebar pages.
Use current two-column/responsive forms, shared secret renderer, UFormField, field keys,
useFormValidation, apiErrorMessage, confirmation dialogs, repositories and localization.
Backend field errors persist under their fields; fieldless refusals persist at page level;
confirmed success can use the existing success notification. Preserve input after failures.

Load: show skeleton/error/retry; Save: validate dirty active group → patch with group revision
→ apply canonical response → update baseline for that group only. Refresh with dirty fields
prompts before discarding. Navigation/tab switch/back/unload has consistent unsaved protection;
secret drafts never enter local/session storage, URLs, telemetry or console. Background status
polling must not overwrite editing fields. Disable duplicate Save/test/run while in flight;
changing tabs preserves independent drafts. Tests must not implicitly save unrelated settings.

Server allowlist and ALL-group permission validation precede writes. Omitted/blank secrets
preserve; separate explicit Remove action revokes/removes after confirmation. Only a replacement
is sent from the browser; saved secrets return configured/masked state. Different group updates
must not overwrite one another; stale same-group revision gives 409 with refresh/diff guidance.
Recheck authorization if privileges change while a form is open. No app-config response should
return unneeded integration metadata to a localization-only consumer.

Important current risks: update_app_config loops merged groups; UI Save submits whole model.
SMTP/backup values go into AppSetting JSON without the Telegram prepare_patch encryption path.
API redaction is not encryption at rest. Implement group revisions, write-only encryption and
safe legacy-copy migration before declaring provider-secret protection complete. Current SMTP
connection/send-test endpoints are placeholders (not_verified), not working transport probes.

## SET-002 — Email provider fields and behavior

Preserve SMTP and add provider choice Resend/SMTP behind one small transactional send boundary.
Do not delete working credentials or force migration merely because Resend is recommended.
No email-provider code was found in the scoped current build; implement only demonstrated gaps.

| Field | Contract |
|---|---|
| Enable Email | Enables transactional delivery; independent of Telegram/group settings |
| Email Provider | RESEND or SMTP; selects relevant fields, not another Settings tab |
| Sender Name / Sender Email | Valid configured sender identity; Resend domain must be verified |
| Reply-To Email | Optional valid address, no header injection |
| API Key / SMTP Credentials | Write-only, encrypted; configured state and explicit removal; no ciphertext round-trip |
| SMTP Host / Port / Security / Username / Password | Preserve existing smtpHost/smtpPort/encryption/username/password fields; verified TLS/STARTTLS per approved deployment, not insecure production downgrade |
| Test Recipient Email | Explicit approved test destination, never arbitrary bulk relay |
| Test Connection / Send Test | Distinct outcomes: authentication/connectivity versus accepted email; no delivery claim without provider evidence |
| Status / error / last test | Server-owned, sanitized, tied to credential/config revision; accepted != inbox delivered |

Use installed httpx for Resend HTTPS API and available SMTP facilities with bounded timeouts;
choose sync-to-thread/async use deliberately, never block the event loop. Define send(template,
recipient, safe parameters, idempotency key) → accepted provider ID or typed failure. Render a
small allowlisted template set and escape header/text/HTML input. Require recipient eligibility;
no user-chosen sender/provider endpoint or unrestricted message proxy. Disable click/open
tracking for recovery content. API keys must be send-only/least privilege where supported.

401/403 or unverified sender: permanent configuration failure; 429/quota: respect retry headers,
alert admin and delay only while delivery TTL permits; transient 5xx/network: bounded backoff.
SMTP connection/auth failure must not leak server credential text. Unknown send outcome remains
explicit. Provider acceptance does not prove delivered/inbox placement; signed webhooks can
update delivery state later after replay/signature verification if a real requirement needs it.

Reuse the durable notification outbox by adding channel/eligible-email destination constraints,
not a second queue. Current recovery_sensitive_payload constraints allow only Telegram PRIVATE;
an additive migration must explicitly permit owner-bound EMAIL recovery without permitting
recovery in either group. Raw reset token exists only transiently and in short-lived encrypted
outbox ciphertext needed for delivery; auth token table stores only its hash. Purge ciphertext
on expiry/terminal state; metadata/audit never contains tokens or rendered reset URLs.

## MAIL-001 — Resend costs and setup snapshot

Verified 2026-11-04 from the official pages below; USD list prices, not a purchase or account
quota guarantee. Recheck before activation; prices/limits never become business-logic constants.

| Transactional plan | Monthly list price / volume | Daily limit |
|---|---|---|
| Free | $0 / 3,000 emails | 100/day |
| Pro | $20 / 50,000 emails; extra $0.90/1,000 | No plan daily quota |
| Scale | $90 / 100,000 emails; extra $0.90/1,000 | No plan daily quota |

Source: [Resend pricing](https://resend.com/pricing). No paid plan/add-on/pay-as-you-go is
authorized. Free currently includes three verified domains. Free daily quota resets at UTC
midnight; multiple recipients count separately and sent/received transactional email shares
the allowance. Default API throughput is 10 requests/second per team, shared across keys;
obey returned headers rather than assuming paid plans remove throughput limits.
Source: [account quotas/limits](https://resend.com/docs/knowledge-base/account-quotas-and-limits).

Before enabling, verify a domain owned by the organization and the required SPF/DKIM DNS
records; set an authorized From address, review DMARC and sender/domain mismatch failures.
Do not use the testing sender identity for arbitrary production recipients. See
[verified-domain requirements](https://resend.com/docs/dashboard/domains/introduction).
Resend supports idempotency keys for email requests with a 24-hour window; reuse the stable
outbox message key/body and retain local outcome longer. Recovery TTL must be shorter than
that window. Source: [idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys).
SMTP has no equivalent exactly-once guarantee; accepted-send/crash ambiguity is documented.

## REC-001 — Secure email Forgot Password / Reset Password

Current recovery is already secure-token based through verified PRIVATE Telegram and depends
on that bot/link at reset time. Preserve it during migration; email must be independent of bot,
adminGroupId and Operations/Developer destinations. Explicit channel/purpose eligibility and
credential version prevent an email token being invalidated merely by a Telegram group change.
Preserve existing auth endpoints/opaque code compatibility; never add a second password engine.

1. Login → Forgot Password → enter account email. Apply server IP/account throttles and bounded
   issuance cooldown. Return the same neutral response/body/status for known, unknown, disabled,
   ineligible account or unavailable provider, with comparable processing paths: If an account
   exists for this email address, a password reset link will be sent. Do not return raw tokens.
2. Eligible active account uses its recorded trusted recovery address, never a submitted alternate
   recipient. Email trust/verification policy must be settled before release; address syntax or
   administrator entry alone is not proof of mailbox ownership. Preserve approved existing
   employees through an explicit verified/admin-confirmed address policy, not guessed flags.
3. Lock the account/issuance state, enforce cooldown, invalidate older same-purpose resets, create
   at least 256 bits cryptographically random token and store only hash + user/purpose/channel,
   creation/expiry/used time and credential version. Proposed default expiry 15 minutes (reuse
   current), configurable within a reviewed bounded range. Enqueue email atomically then commit.
4. Worker rechecks account/address/version/policy/token expiry, decrypts only for send and respects
   the expiry budget. Repeated worker processing reuses provider idempotency; repeated browser
   requests within cooldown do not create duplicate logical emails. Do not log the token/link.
5. Build HTTPS URL from a deployment-controlled trusted origin/allowlisted reset route. Never
   trust Host/X-Forwarded-Host or arbitrary returnTo. Reuse fragment token pattern for SPA and
   remove it from the address bar immediately after capture; no third-party analytics/assets
   on recovery screens, no-referrer policy, no token in query/access logs, storage or telemetry.
6. GET/open/verify is read-only; email link scanners must not consume tokens. Optional preverify
   is never authorization to reset later. User enters and confirms new password; server applies
   the existing shared password validator, CSRF/Origin rules appropriate to the credential flow
   and endpoint throttles. Never email a password or automatically log the account in.
7. In one transaction, lock account, recheck active/address/version/purpose/expiry and atomically
   consume unused token; Argon2-hash new password, clear failed counters/forced-change marker
   appropriately, invalidate other outstanding reset tokens, revoke ALL sessions/refresh chains
   and increment token version. Any failure rolls back consumption/password together.
8. Audit completion without secrets and enqueue confirmation to the trusted address. Confirmation
   email failure is a delivery failure, not a rollback of the completed password change. Show
   success → normal Login. Old tokens, old sessions, replay and racing resets must fail.

Use [OWASP recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
for uniform responses, safe URLs, single use, expiry and session handling. Provider metadata
must not expose whether an account exists through public polling. Error logs use correlation
IDs/safe codes only. Credential rotation/new password/address change cancels obsolete queued
recovery work. Do not silently change current Telegram-only users' recovery policy.

## SEC-001 — Preserve and enforce security fields

| UI / stored key | Current behavior / target effect |
|---|---|
| Idle Timeout / sessionTimeoutMinutes | Server compares actual activity with current idle policy; range 1–1440 min. Frontend warning is UX, not a second authority |
| Access Token Lifetime / accessTokenMinutes | Current policy used when issuing/renewing JWT; range 1–30 min. Changing it affects new tokens; existing JWT expiry stays unless explicit revocation; session/idle checks still apply |
| Absolute Session Lifetime / sessionAbsoluteMinutes | range 15–10080 min; server deadline is min(stored expires_at, created_at + current policy). Shortening can expire existing sessions; increasing does not extend their stored deadline |
| Maximum Login Attempts / maxLoginAttempts | Server lockout policy reads current settings; range 1–100. Verify atomic concurrent counter handling; no client-only enforcement |
| Account Lock Duration / accountLockMinutes | range 1–1440 min; applied at future threshold lock. Existing locked_until remains unless explicit authorized change; no silent unlock |
| Password Expiry / passwordExpiryDays | range 0–3650 days; zero disables periodic expiry. Enable only under explicit policy, never add automatic frequent rotation |
| Require Password Change / requirePasswordChange | Current server marker requirePasswordChangeSince records enable time; protected flow gates normal actions until change. Toggle is audited; preserve existing admin-set must-change semantics |

Existing get_access_policy caches for up to 5 seconds locally, settings writes invalidate local
policy and bump auth cache. Verify cross-process convergence within the documented bound; do
not promise instantaneous revocation through a cache. Explicit logout/revoke/deactivation and
password changes must still fail closed through persisted session/token version validation.
Renewal rotates refresh tokens, rejects replay and expired/revoked sessions; absolute/idle
lifetime is not reset by silent polling. Review current activity header handling in core/deps.py
and browser auth store; avoid multiple conflicting timeout timers. Set/clear cookies with the
existing Secure/HttpOnly/SameSite/CSRF policy. Logout must invalidate the server session.

Current locked/inactive login errors differ from invalid credentials: NEEDS_REVIEW for public
enumeration. Target a uniform public credential refusal with dummy-hash/comparable work and
private audited reason. Do not expose existence/lock status or blanket-disable useful admin
Audit Logs. Rate limits must cover IP and opaque account/token keys and be reliable across
replicas using existing infrastructure; no new Redis deployment is requested.

Shared password policy is core/security.py validate_password_strength with configured min/max,
common-password rejection and uppercase/lowercase/number/symbol checks; Argon2 handles hashing.
Use the same validator for setup/user creation/admin reset/self-change/recovery. Do not silently
replace this policy, alter legacy login validation or force periodic expiry without approval.
Prefer long passphrases and approved risk-based controls; any policy modernization is a separate
reviewed change. Security settings update requires granular capability, recent reauthentication,
consequence summary/confirmation and secret-free audit; protect the last Super Administrator.

## Provider setup, cost and operational gates

R2: private bucket, direct S3 endpoint, least-privilege credentials; no MinIO required for target.
Official [R2 pricing](https://developers.cloudflare.com/r2/pricing/) snapshot: Standard $0.015/
GB-month, Class A $4.50/million, Class B $0.36/million; monthly free Standard allowance 10 GB-month,
1 million A/10 million B, direct egress free. Infrequent Access has distinct retrieval/minimum
storage charges; do not select it just from a lower storage headline. Estimate encrypted
recovery-set size × retained copies plus readback/drills/request rounding; no price hardcoding.
[S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/) determines checksum,
multipart and encryption support; do not assume AWS KMS behavior on R2.

Drive: OAuth authorization/refresh/revoke, private folder and encrypted archives; least scope
per [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).
Account storage/subscription and API quotas vary. New/legacy project limits changed in 2026;
check [current limits](https://developers.google.com/workspace/drive/api/guides/limits), billing
and [service-account/shared-drive restrictions](https://developers.google.com/workspace/drive/api/guides/about-shareddrives)
before enabling. No assumption of unlimited/free storage or unchanged old request quotas.
Provider setup never asks for a Google password or stores refresh tokens in frontend config.

## Acceptance and manual checks

Extend existing settings-validation/localization, password-reset/policy, auth-sessions and
Telegram recovery suites only for changed behavior; real token/session races use disposable
PostgreSQL, plus denial/API-contract regression and read-only DEEP review. Mock external sends.
Manual: edit one tab, keep another dirty, Save/Refresh conflict and reload; verify configured-only
secrets; compare view-only/manage/test/restore grants; run recovery with known/unknown/disabled
accounts, expired/replayed link and quota outage; verify neutral public responses and all old
sessions revoked. Tests/provider sends are candidate future checks, not executed here.

Unresolved before release: trusted recovery-email proof, approved sender/domain/OAuth account,
secret key owner/rotation/escrow, new capability grant migration and security confirmation policy.
Provider pricing is dated reference only; account charges or real mail/Telegram tests need
explicit authorization. Maintain S01's remaining session/action acceptance rather than marking
it complete from this specification.
