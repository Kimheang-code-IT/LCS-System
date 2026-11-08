# Notifications: Operations and Developer destinations

Status: approved requested target, NOT IMPLEMENTED in full; 2026-11-04.
[Current inventory and architecture](../01-architecture/integration-architecture.md) distinguishes
existing private/admin Telegram code from new routing. [Plan B](../04-implementation/plans/PLAN-0005-settings-integrations.md#phase-b--telegram)
owns implementation. Preserve private Telegram recovery; it is not a third business group.

## NOT-001 — Settings and verified destinations

Reuse Settings > Telegram, one bot, two independently configured private groups:
OPERATIONS and DEVELOPER. Both are disabled until configured, verified and explicitly enabled.
Never copy adminGroupId into both. Migration treats a verified legacy admin group as the
Developer candidate only; revalidate bot/group ownership and leave Operations disabled.

| Section | Fields / behavior |
|---|---|
| General | Enable Telegram; write-only Bot Token (configured state/explicit remove); read-only Bot Display Name and Bot Username from getMe; Message Language; Include Organization; Test Bot Connection |
| Operations | Enable Operations Notifications; Operations Group Chat ID; verification state/name; Created, Updated-important-only, Finished, Important Status Changes, Operational Exceptions preferences; Test Operations Group |
| Developer | Enable System Alerts; Developer Group Chat ID; Backup Success/Failure/Verification/Overdue, System Errors, Unavailable/Recovered, Database Failure/Recovery, Object Storage Failure, Restore Failure and scheduler preferences; Test Developer Group |

Use existing pairing/getChat confirmation to prove a private group, bot membership and valid
negative/supergroup ID; do not infer from name or allow a public group. Server-owned verified
fields are never writable by the browser. Reject using the same chat for both destinations to
preserve isolation. Support bot migration/group upgrade by explicit revalidation, not silent
ID replacement. Token/group changes invalidate relevant verification and stale pending work;
a bot change preserves no false verified state. No raw tokens/ciphertext returned to UI.

Bot connection test calls getMe and updates only the tested revision. Group Test sends a
clearly labeled synthetic test to exactly the selected verified destination, only after an
explicit privileged action. It does not save unrelated form drafts or send a business event.
A bot test alone does not prove group delivery. This documentation task sends nothing.

## NOT-002 — Operations events

| Event | Trigger / dedup identity | Allowed message |
|---|---|---|
| SO_CREATED | Successful first creation; SO ID + creation event ID | SO number, authorized display customer, direction, actual container count, saved status, creator display name, timestamp and authorized detail URL |
| SO_UPDATED_IMPORTANT | Explicit configured material transition/version, not every Save/autosave | Changed event type and minimal reference; no before/after row dump |
| SO_FINISHED | Actual unfinished→finished transition | Source number and final operational status, actor/time |
| SO_STATUS_CHANGED | Allowlisted business transition/version | Source number, old/new non-sensitive status, actor/time |
| SO_REOPENED | Only if existing authorized lifecycle supports reopen | No invented endpoint/status; explicit actor/reason summary policy |
| OPERATIONAL_EXCEPTION | Defined actionable validation/operational incident, not every bad input | Sanitized reason category and record reference |

Creation versus keyed replay yields one event; an idempotent Finish/repeated Save yields no
extra alert. Count actual physical container records, never quoted type requirements. Use
stored source/actor fields at commit; do not send example data as seeds. Sensitive customer
financial amounts, charges, documents or personal contacts are excluded unless a separately
approved payload policy explicitly allows them. Operations recipients must be approved for
that operational information; a link still requires normal login/Casbin access.

Example TEMPLATE ONLY (no seed/send):
SERVICE ORDER CREATED; SO No: {source_number}; Customer: {approved_display_name}; Direction:
{direction}; Actual Containers: {count}; Status: {status}; By: {actor}; Time: {localized_time};
View: {trusted_application_origin}/service-orders/{id}.
Trusted HTTPS origin is deployment configuration, never Host header or unvalidated user URL.
Escape text/formatting; prefer bounded plain text and safe templates, not arbitrary HTML.

## NOT-003 — Technical alert policy

Developer only: backup success/failure/integrity failure/storage unavailable/overdue; restore
started/completed/failed; sustained API/dependency unavailable and recovered; repeated critical
server failures; DB loss/recovery; object-storage failures; scheduler/worker failures; measured
disk/capacity warnings. Reuse current monitor and health checks. Do not notify on ordinary
400/404/422 requests or every isolated 500. Failed authorization/login events use thresholds
and authorized Audit Logs, not account/credential disclosure in the group.

Severity: INFO, WARNING, CRITICAL. RECOVERED is an explicit transition rendered as RECOVERED,
not a severity incorrectly compared numerically. Extend the current severity/schema handling
without breaking old INFO/WARNING/CRITICAL rules. Each incident has one recovery event after
an actually notified active failure; no recovery for an unobserved/transient pending failure.

Proposed initial policy (confirm with owner before production): max 3 attempts, incident
cooldown 30 minutes, sustained failure 2 minutes; backup-overdue = expected scheduled completion
+ configured grace. Use existing measured disk/CPU/memory hysteresis where accepted. Persist
incident start, last notification and recovery state; cooldown suppresses repeats for the same
environment/source/condition without hiding a new severity escalation or new incident.
Critical messages disclose environment, provider/job/event ID, stage, time, measured duration/
size where known and a safe reason/action. Never send raw tracebacks, DB URLs, signed object
URLs, provider credentials, reset links or customer records to either group.

Existing in-process monitoring cannot report its own complete process/host loss. Reuse an
approved external health observer or host scheduler for availability/backup-age checks when
that guarantee is needed; no new monitoring platform is required by this design. DB-down
cached direct Telegram send remains explicitly best effort with cooldown and no durable
history until recovery; never claim guaranteed outage notification or send it to Operations.

## NOT-004 — Transaction, dispatch and retry

1. Create a durable event/outbox row in the SAME transaction as the business transition.
   Rollback leaves no deliverable event; commit succeeds regardless of Telegram network state.
2. Worker reads only committed rows; claim with existing SKIP LOCKED/lease/fencing token.
   Use stable event ID plus environment/source/aggregate version/destination unique key.
3. Before sending, recheck enabled policy, bot/config revision, verified destination, TTL and
   event eligibility. Never reroute a pending Developer message into a newly selected Ops chat.
4. Bounded network timeout must fit within the lease. Persist provider message ID/result;
   condition updates on the claim token, reclaim expired processing after restart and audit
   stale/reclaimed attempts. Backoff with jitter; obey retry_after for 429. Retry transient
   timeouts/5xx within attempt/age budget; bad token, blocked group or invalid chat fail safely.
5. Terminal state SENT/FAILED/CANCELLED plus sanitized last error; failed history visible to
   authorized admins. A manual retry creates a controlled attempt of the same logical event,
   never repeats the SO transaction. Disable/remove/expired recovery purges sensitive payload.

Enqueue deduplication prevents duplicate logical events. Telegram delivery has an unavoidable
accepted-send/acknowledgment crash window: a retry may duplicate a message because the API
has no application idempotency transaction with PostgreSQL. Document at-least-once transport,
include the stable event reference and avoid blind immediate retries of unknown outcomes.
Do not promise exactly-once external delivery or risk financial writes to satisfy that claim.
An incident must not alert recursively about failure to send its own alert; logs/admin history
remain the fallback. The current precheck+unique key must handle concurrent unique conflicts
without rolling back the business command: use an insert-on-conflict/savepoint for identical
logical-event replay, preserve its original payload and never swallow unrelated DB errors.
Validate this before adding SO producers. Strict zero-duplicate external delivery would require
a separately accepted provider/consumer deduplication guarantee; owner acceptance of the
Telegram acknowledgment window is an explicit release decision.

## NOT-005 — Delivery records and security

Reuse notification_outbox + notification_incidents. Required fields: event ID/type, severity
or transition, source module/record/version, UTC timestamp, environment, channel, destination
kind/reference/config revision, status, attempt/retry count, next retry, safe error, dedup key,
claim/lease, sent time/provider ID. Avoid storing full rendered customer messages indefinitely;
approve retention for metadata and short-lived sensitive recovery ciphertext separately.

Reuse existing notification history/router/client/UI sections; add destination/event filters
inside Settings rather than a sidebar page. Viewing history is not permission to reveal
recovery content or send tests. Settings manage/test actions and execution authorization use
Casbin; masked audit records capture configuration changes, test actions and delivery outcomes.
Secrets and reset links never appear in public/history/audit responses.

## Focused acceptance

NOT-001–005 are accepted only after mocked/provider-sandbox success/refusal plus isolated
PostgreSQL commit/rollback, concurrent enqueue/claim, crash recovery, cooldown/hysteresis,
policy-disable and secret-redaction cases. Verify one bot/two private distinct groups, exact
Ops/Developer separation, no event on minor Save or rollback, no SO failure during provider
outage, one logical event on replay, explicit unknown-delivery limit and one recovery per
incident. UI manual checks: fields/save/refresh/unsaved protection, three locales, destination
verification and explicit selected-group test. Real sends require separate authorization.
