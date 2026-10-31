# Security and Access Control

## Authentication

Preserve session-bound JWT access and rotating opaque refresh cookies. PostgreSQL validates
account/session state and idle/absolute deadlines; refresh replay and revocation must be
tested. Existing HTTP-only cookie and bearer access conventions remain supported.
Setup `/auth/setup` and `/api/v1/auth/setup/*` is allowed only while no user exists.
Setup provisions the initial administrator, protected system role and baseline configuration;
it does not create business transactions or a complete finance chart/period baseline.
Passwords are Argon2id hashes; never return passwords, hashes, tokens, or secret material.

## Authorization

Casbin is the sole decision engine. The code-defined permission vocabulary is in
`backend/app/core/permissions.py`; grants and role assignments live in `casbin_rule`.
Page grants compile to capabilities through existing code. Preserve single-role semantics,
default denial, and the protected Super Administrator role.
The frontend permission snapshot controls navigation/actions for usability; every protected
API operation must enforce backend authorization. No parallel role mapping is permitted.
See [detailed permission catalog and mappings](09_roles_and_permissions.md).

## Tenant isolation

One business deployment is supported. There is no multi-tenant organization/branch isolation
contract. Keep test and production data separate; do not invent tenant fields or scopes.

## Secrets handling

Use approved environment/secret provisioning; inspect variable names and presence without
printing values. Never read, expose, copy, or commit `docs/lcssystem.pem` or other private keys.
Recover critical configuration and secrets through an approved secure process with restricted
access; secret recovery ownership and procedure validation remain open.
Require HTTPS externally and restrict internal database/cache/storage exposure.

## Audit requirements

Preserve important authentication, policy, posting, reversal, allocation, and period-control
events. Restrict audit access and unauthorized modification. Do not claim all ordinary edits
are audited. Financial corrections preserve original history and source relationships.
Retention and legal obligations remain TBD; no automatic purge is authorized.

## Threat considerations and validation

Test direct API bypass, unauthenticated access, insufficient action permissions, stale grants,
expired/revoked sessions, refresh replay, logout, CSRF/cookie protection, and locked identities.
Test upload/download authorization, MIME/size validation, stored content handling, and
sensitive log redaction. Financial threats include duplicate execution, concurrent allocation,
unbalanced journals, historical mutation, and closed-period posting.
S01 covers identity/page/action authorization; other slices cover their own denial paths.
No new mandatory second-person approval engine, status, table, or page is approved.

## Legacy requirement traceability

Stable identifiers migrated from the reviewed SRS. These are requirements, not assertions
that implementation or acceptance has passed. The approved LCS scope/priorities govern;
retired IDs and deferred advanced capabilities do not create extra pages or new workflows.

| ID | Requirement |
|---|---|
| FR-001 | The system shall require every protected request to have an active user context. |
| FR-002 | The system shall resolve the requesting user's effective permissions from the active role assignment before authorizing an action. |
| FR-003 | The system shall reject a request when the required permission is not granted. |
| FR-004 | The system shall attach a request identifier and correlation identifier to each request for tracing and audit. |
| FR-005 | A granted permission shall apply to all records of the corresponding module, since the platform is single-tenant. |
| FR-006 | The system shall deny access when the user has no active role or the active role does not grant the requested permission. |
| FR-007 | The system shall treat expired role assignments as inactive when computing effective permissions. |
| FR-008 | The system shall apply authorization on the server side for every protected endpoint. |
| FR-009 | The system shall not use frontend filtering as a security mechanism. |
| FR-010 | The system shall authenticate users using username or email and password. |
| FR-011 | The system shall store application passwords only as one-way password hashes. Every new password (first-run setup, reset, change, administrator reset, user creation) shall contain at least 8 characters, at least one uppercase letter, one lowercase letter, one number and one special character; one server-side rule shall enforce it, mirrored by the UI, and it shall never be applied to an existing password at login. |
| FR-012 | The system shall support logout and session revocation. |
| FR-013 | The system shall support refresh-token rotation or equivalent secure session renewal. |
| FR-014 | The system shall support password reset using a time-limited, single-use token. |
| FR-015 | The system shall track failed login attempts. |
| FR-016 | The system shall temporarily lock or throttle an account after configured failed-attempt thresholds. |
| FR-017 | The system shall record successful login, logout, and session-revocation events in the audit log; failed attempts are counted on the credential for lockout. |
| FR-018 | The system shall allow an administrator to disable a user and revoke active sessions. |
| FR-019 | Administrators shall create, activate, suspend, lock, and disable users. |
| FR-020 | The system shall support roles containing multiple permissions. |
| FR-021 | A user shall hold exactly one role at a time. |
| FR-022 | The assigned role shall be replaceable; replacing or removing it shall stop contributing permissions on the next request. |
| FR-023 | A deactivated role shall not contribute permissions. |
| FR-024 | Effective permissions shall be exactly the direct grants of the user's one assigned role; roles do not inherit permissions from other roles. |
| FR-025 | Permission and role-assignment changes shall be auditable. |
| FR-026 | The system shall deny access when the user holds no role that grants the required permission. |
| FR-027 | The last active Super Administrator assignment shall not be removed, and the protected `SUPER_ADMIN` role shall not be modified by a caller that does not hold the wildcard grant. |
| FR-028 | The system shall record the actor, action, target entity, result, timestamp, and request correlation identifier for audited actions. |
| FR-029 | The system shall audit financial posting, reversal, allocation, period closure, permission changes, and authorization denial. |
| FR-030 | The system shall not include plaintext passwords, tokens, or encryption keys in audit payloads. |
| FR-031 | Authorized users shall search audit records by actor, event type, entity, result, and date range. |
| FR-054 | The system shall store customer customs credentials separately from the party profile. |
| FR-055 | The system shall encrypt or externally reference retrievable customs passwords. |
| FR-056 | Only authorized users shall retrieve customs passwords. |
| FR-057 | Password retrieval shall require audit logging and may require a reason. |
| FR-153 | The system shall store file metadata in PostgreSQL and file content in object storage. |
| FR-154 | The system shall support attachment links to quotations, revisions, service orders, components, charges, financial documents, and journal sources. |
| FR-155 | The system shall validate file size, MIME type, authorization, and upload completion. |
| FR-156 | The system shall calculate and store file checksums where supported. |
| FR-157 | The system shall support document versions. |
| FR-158 | The system shall restrict downloads according to permission scope. |
| FR-159 | The system shall audit sensitive downloads where configured. |

## Deferred credential requirement boundary

FR-054–057 preserve legacy customs-credential requirements. The old SRS recorded no dedicated
table retrieval API/UI workflow; current implementation completeness remains unverified.
Do not expose a new credential workflow or page during consolidation. Confirm need and source
protection before any future implementation; the encrypted-field design is not proof of delivery.
UR role responsibilities and the protected Super Administrator follow the existing Casbin
catalog, never the obsolete SOP's “one or more roles” wording.
