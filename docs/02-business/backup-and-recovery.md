# Cloud Backup and Coordinated Recovery

Status: target requirements/design, 2026-11-04; implementation NOT_STARTED.
[Inventory](../01-architecture/integration-architecture.md#current-implementation-inventory)
records existing R2 JSON snapshots, Google Sheets mirror and deployment pg_dump behavior.
[Plan E/G](../04-implementation/plans/PLAN-0005-settings-integrations.md) owns future work;
S12 still owns separately authorized isolated recovery acceptance. No backup is run here.

## BAK-001 — Scope and provider boundary

One active cloud destination per schedule: Cloudflare R2 recommended, Google Drive optional.
Several provider configurations may exist but only one selected revision receives a run.
Switching providers affects future runs; old backups retain their provider/config locator and
remain restorable until explicitly migrated/retired. No duplicated backup-generation logic.
Google Sheets is preserved as a separately labeled legacy redacted mirror, not a Drive file
backup, PostgreSQL archive or disaster-recovery substitute. No local MinIO dependency is added
to the target; direct R2/Drive SDK access is sufficient. Existing upload storage/MinIO volumes
and Compose remain unchanged until an authorized migration with object/reference checks.

Daily encrypted off-host database backup remains the production requirement from the runbook.
UI may offer Manual/Daily/Weekly/Monthly; a weaker production schedule needs an explicit accepted
RPO exception. RPO 24h/RTO 4h remain proposals, not approved/measured results. A daily schedule
plus upload/retry lag can exceed 24h; measure the latest VERIFIED recoverable cutoff.

## BAK-002 — Settings and actions

| Group | Fields / constraints |
|---|---|
| Common | Enable Automatic Backup; active Provider R2/Drive; frequency; local start time; IANA Time Zone; Retention Days; Maximum Copies; Include Database/Uploaded Files/Configuration; Encryption enabled; protected-backup policy |
| Status | Last successful upload, last VERIFIED recovery set, next scheduled UTC/local run, status/stage, size/duration, overdue state; do not equate upload success with recoverability |
| R2 | Account ID, Bucket Name, write-only Access Key ID/Secret Access Key, derived/allowlisted HTTPS Endpoint, optional environment-scoped prefix; Test Connection |
| Drive | Connect Google Account, authorized account identity, destination folder, connection status, Test Connection, Disconnect; never a Google password |
| Actions | Save Changes, Test Connection, Backup Now, View History, Download, Verify, Restore; existing Settings header/actions/components |

Database inclusion is mandatory for a complete recovery set. If files/config are omitted,
label the artifact database-only and refuse a claim of complete application recovery. Record
server-enforced bounds for retention/copies/free disk/job size once owners approve them.
Zero/invalid retention or a provider failure cannot authorize deleting all backups.

Connection checks verify credentials/target access without destructive writes; optional test
object creation requires an explicit documented cleanup permission/action. Backup Now is an
explicit run command, not a side effect of Save or Test. Queued jobs return IDs immediately.
History distinguishes GENERATED/UPLOADED/VERIFIED/RESTORE_TESTED and failures by stage.

## BAK-003 — One recovery-set builder

Pipeline: claim durable job → capture consistent database + attachment/config cutoff → generate
archive → validate manifest/required entries → authenticated encryption → upload → remote
size/checksum verification → mark VERIFIED → guarded retention → developer notification.
No later stage fabricates earlier success; interrupted artifacts never become restore candidates.

Use existing deployment pg_dump -Fc capability in a bounded controlled runner, pinned compatible
PostgreSQL tools, with fixed arguments and deployment-managed connection secrets (no shell
interpolation/browser database URLs). A filtered BackupRecord JSON export is not this dump.
Use a consistent database snapshot; coordinate attachment references and immutable object
versions/content hashes at that cutoff. If mutations cannot be snapshotted reliably, use a
brief authorized write-quiesce barrier; never copy database/files independently and call them
consistent. Mark the exact cutoff and all intentional exceptions in the manifest.

Contents: PostgreSQL schema/data/sequence state including valid auth credentials and permissions,
required business uploads/attachments, required configuration, application/schema/Alembic
versions, organization/environment identity, manifest format version, file list/size/checksums,
UTC start/cutoff/end, tool versions and encryption key ID. Auth hashes and sensitive config
are allowed ONLY inside the encrypted restricted DR archive, never normal exports/logs.
Exclude caches, temp files, dependency/venv/build directories, unneeded logs and plaintext keys.
A redacted export that cannot recover accounts/relationships is not a complete recovery set.

Use streaming/bounded staging and quotas; fail before disk exhaustion; remove staging ciphertext
and plaintext safely after completion/TTL. Authenticate encryption (reviewed streaming AEAD or
equivalent established tool), distinct data key per archive, externally wrapped/escrowed master
key with key ID/algorithm/version. Do not write a home-grown cipher or load large dumps entirely
into RAM. Key management/streaming library choice needs a concrete implementation review.
Transport/TLS or server-managed bucket encryption alone does not satisfy this application
backup-encryption/key-recovery requirement. Keep decryption credentials/escrow outside both
archive and primary database; test losing the original host without losing the keys.

Manifest private content is encrypted and authenticated; an outer locator may expose only format,
key ID, ciphertext size/hash and non-sensitive job ID needed to locate/decrypt. Do not expose
customer filenames/account values in object metadata or public history. A checksum detects
corruption, authenticated encryption/signature proves tamper resistance under the key policy.

## BAK-004 — R2 adapter

Reuse core/storage.py S3Storage and boto3; retain ensure_bucket=False for backup operations.
Derive https://{validated_account_id}.r2.cloudflarestorage.com for the approved account, with
explicit allowlisted jurisdiction endpoints where needed. Validate host/scheme/DNS against SSRF;
no metadata IP, arbitrary URL, insecure TLS or user-supplied shell path. Region auto per API.
Use a private bucket and separate application/environment prefix, e.g. lcs/{installation}/{env}/.
No public bucket/custom-domain exposure; no broad account token or bucket auto-creation.

Least privilege separates uploader/verifier/read/download/retention-delete where possible.
Reuse SDK signed access only after app authorization; prefer a short-lived one-use download
ticket/proxy, audit access, never Telegram a signed URL. Metadata/history remains restricted.
Use multipart/resumable upload for large archives, fixed upload identity and bounded retry;
reconcile ambiguous upload completion before creating another object. Abort abandoned multipart
uploads under a scoped retention policy. Never share process-wide upload credentials/settings.

## BAK-005 — Google Drive adapter

Use the installed google-api-python-client/google-auth libraries with server-side authorization
code flow, state binding, PKCE where supported, exact HTTPS callback allowlist and account/folder
selection. Keep refresh/access credentials encrypted server-side; use minimum practical scopes
(start with drive.file for app-created/user-authorized objects). If existing folder access needs
Picker/explicit grants or broader scope, document the reason/consent rather than silently
requesting all Drive access. Connect/reconnect/disconnect require privileged settings access.

Store encrypted archive bytes as ordinary binary Drive files, NOT Google Docs/Sheets conversion.
Persist file ID, selected folder/account identity and checksum/size in manifest metadata. Use
resumable upload and bounded retry/refresh. Revoked authorization becomes REAUTH_REQUIRED,
not an infinite refresh loop; notify Developer through the independent configured channel.
Disconnect revokes/deletes local credentials only after explicit confirmation and records what
old backups will require to restore. It never deletes the remote archives automatically.

Service accounts have no personal storage quota/ownership; use an authorized shared drive or
user OAuth appropriate to the account. Do not assume sharing a My Drive folder solves this.
Organization access, shared-drive membership/flags, account storage quota and API quota must
be checked before enabling. Scope/namespace is not authorization for another tenant's files.

## BAK-006 — Durable scheduling and crash handling

Reuse backup/scheduler.py asyncio tick/advisory locks. Persist next intended schedule occurrence,
active run/lease and monotonic stage checkpoints; unique (installation, environment, schedule,
occurrence) key plus manual-command key prevents duplicate runs. Re-read due/active state under
the lock; initial in-process active_run_id alone does not protect multiple replicas.
Long work renews its lease or records a safe stopped state; expired claims can be recovered.
Record actor/manual reason, config/provider revision and bounded retry count/next attempt.

Store UTC instants + IANA timezone. Define DST gap = next valid local time, fold = one occurrence;
monthly invalid day = last valid day. After downtime run one latest missed occurrence, record
older missed slots, do not flood providers with every missed day. Failed runs back off with
jitter within a documented job budget; retry does not postpone detection of overdue verified
backups. No overlaps, duplicate scheduler instances or uncontrolled separate worker fleet.
A later worker separation is justified only by measured blocking/runtime needs.

## BAK-007 — Verification and retention

After upload: verify object/file exists, expected nonzero ciphertext size, end-to-end ciphertext
SHA-256 (provider checksum when equivalent, otherwise authenticated readback), readable/authentic
manifest, all required entries and manifest-to-archive checksums. S3 ETag is not assumed a SHA-256
or multipart-content MD5. A verified upload still needs periodic isolated restore drills.
Readback/decrypt/key-unavailable failures mark VERIFICATION_FAILED and alert Developer; preserve
the candidate for investigation, never count it as last known good.

Retention is disabled until an explicit valid policy is configured. Combine age and maximum
copies only within the exact installation/environment/provider namespace and completed verified
run catalog; preserve marked/protected backups, any restore-in-use set and the last known-good
VERIFIED set (plus latest RESTORE_TESTED set when distinct). Never retain only failed or
incomplete artifacts to satisfy a copy cap. No retention based on untrusted object names alone.
Preview eligible deletions, audit IDs/counts, retry deletions safely and reconcile remote/catalog
state. Missing DB/catalog must fail closed for deletion. Approved storage limits alert instead
of deleting protected data. Current local 30-day dump cleanup is history, not the target policy.

## BAK-008 — Controlled restore, not row import

Restore is a high-privilege recovery operation, not ordinary CRUD, an unrestricted SQL endpoint
or a long-running browser request. Default target for implementation/tests is isolated only.

1. Authorized administrator selects backup ID/provider; server resolves a trusted stored locator.
   Show cutoff, source environment/installation, format, schema/app/tool versions, included
   files/config, verification/restore-test state and known omissions. Block wrong installation,
   incompatible/encrypted-with-missing-key/corrupted/incomplete sets.
2. Verify remote bytes, authenticated decrypt, manifest and checksums before touching any target.
   Reject path traversal/symlinks/archive bombs. Pin an allowlisted server-owned target and plan.
3. Create expiring restore plan/nonce bound to actor, backup, digest, target and config revision;
   require recent reauthentication, explicit typed backup/environment confirmation and separate
   operational authorization for production. Recheck permission at execution; return 202/job ID.
4. Enter an externally controllable restore-safe state: block writes, financial posting, queues,
   schedulers, webhooks and all external sends on the target; drain in-flight transactions and
   capture a verified pre-restore recovery point/current file set. Maintenance state cannot be
   restored away merely by replacing app_settings. Keep recovery control outside the target DB.
5. Restore to a fresh database and separate object prefix with fixed trusted tooling; validate
   constraints, extensions, schema versions, sequences, row/control counts, journal debit=credit,
   posting uniqueness, settlement bounds, reports, source links, permissions and every referenced
   attachment. Do not bypass financial guards to merge arbitrary historical rows.
6. Restore compatible encrypted configuration using available escrow; keep provider credentials
   disabled pending explicit review. Invalidate all old sessions/refresh/reset/pairing tokens,
   cancel or quarantine old pending notifications/jobs and prevent duplicate historical events.
   Persist recovery audit/checkpoints outside the replaced database and reconcile the new audit.
7. Only after validation permit controlled pointer/config cutover and a read-only smoke check;
   authorized operator decides reopening writes. Record measured RPO/RTO, checks, counts and
   discrepancies. Send sanitized Developer completion/failure from a trusted independent state.

On partial failure keep maintenance and the original DB/file set; do not expose a mixture.
Record stage and safe checkpoint. Retry into a clean staging target or abandon it; rollback is
an explicit validated switch to the pre-restore pair, not an automatic downgrade/overwrite.
If failure happens after cutover, quiesce again, assess new writes and use an approved recovery
plan; never silently discard them. Resume availability only after integrity verification.
No restore drill, provider access, destructive SQL or cutover is authorized by writing this doc.

## Focused acceptance and unresolved owners

Test with mock providers and synthetic disposable PostgreSQL/storage: exact builder reused for
R2/Drive, cross-replica duplicate run refusal, restart at every stage, DST/missed run, interrupted
upload, wrong key/checksum, folder/account revocation, retention last-good/environment guards,
unauthorized download/restore, stale restore nonce and failed staged recovery. Perform an
explicitly authorized full DB+files+config recovery drill before claiming complete recovery.
Manual: configure/test without side effects, queue Backup Now, inspect status/history/download,
verify corrupt sample refusal and restore plan metadata/confirmations on isolated target.
Owners must approve RPO/RTO, retention/copies/protected policy, schedule/grace/timezone, archive
size/resource limits, key escrow/rotation, recovery operator and recurring provider budget.
