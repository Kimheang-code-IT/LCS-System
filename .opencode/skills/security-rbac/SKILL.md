---
name: security-rbac
description: Use when implementing or reviewing LCS authentication, authorization, permissions, roles, single-role enforcement, session and token handling, audit events, administrator protection, or secret handling.
---

# Security and RBAC

Authentication and authorization for the LCS platform. The backend is the only
authorization authority; the frontend hides what a user should not see, it does not
protect anything.

## When to use

- Adding an endpoint and deciding which permission it needs.
- Changing roles, permissions, role assignment, or the permission catalog.
- Touching sessions, tokens, password policy, or lockout.
- Handling a secret, a credential, or a sensitive field.
- Reviewing an authorization gap or an audit requirement.

## Required inputs

1. The operation and who should be allowed to perform it.
2. Whether an existing permission code already covers it.
3. Whether the change affects an administrator's own account or the last admin.

## Project references

| Document | Use it for |
|---|---|
| `docs/09_roles_and_permissions.md` | The catalog, page mapping, role composition, and enforcement |
| `docs/11_deployment_and_security.md` §16-§17 | Controls that must stay enforced |
| `AGENTS.md` §Backend | Auth model, cookie/token transport |
| `backend/app/core/permissions.py` | The code-owned catalog and role definitions |
| `backend/app/modules/auth/service.py` | `PAGE_KEYS_BY_SOURCE`, lockout policy, admin guards |
| `backend/tests/test_auth_rbac.py`, `tests/test_role_permissions.py` | Existing coverage to extend |

## Model

- **JWT access token** (short-lived) delivered as `Authorization: Bearer` or a
  Secure HttpOnly cookie; **rotating refresh token** backed by a persisted
  `user_sessions` row. Refresh tokens are never readable from JavaScript.
- **One active role per user**, enforced by a partial unique index on
  `user_role_assignments` where `expires_at IS NULL`. Replacing a role expires the
  previous assignment rather than deleting it, so history survives.
- **Permission catalog is code-defined** in `app/core/permissions.py` and synced on
  startup (`ensure_permission_catalog`). The sync only *adds*; grants made in the
  database persist.
- **Page permissions** are what the Roles screen grants; each page code expands to
  the API codes it implies via `PAGE_PERMISSION_SOURCE_CODES`, mirrored for the UI
  in `auth/service.py::PAGE_KEYS_BY_SOURCE`.
- **Protected System Administrator**: the first user carries
  `system_identity = "DEFAULT_SYSTEM_ADMIN"`, cannot be deleted, cannot be
  deactivated, and is force-restored to `PLATFORM_ADMIN` on startup.
- **Tokens are versioned** (`users.token_version`): deactivation, forced logout,
  and password change bump it, so revocation is immediate despite stateless JWTs.

## Workflow

1. **Decide the permission first.** Search for an existing code before adding one.
   Adding a code requires:
   - an entry in `SOURCE_PERMISSIONS` (API) or the page/matrix tuples;
   - a page mapping in `PAGE_PERMISSION_SOURCE_CODES` **and**
     `auth/service.py::PAGE_KEYS_BY_SOURCE`, or
     `tests/test_role_permissions.py::test_every_source_permission_has_a_page_key_for_legacy_roles`
     fails;
   - a row in `docs/09_roles_and_permissions.md`.
2. **Protect the endpoint** with
   `Depends(require_permission("code"))`. That dependency writes an
   `AUTHORIZATION_DENIED` audit event before raising, which is what makes denials
   reviewable.
3. **Enforce "one active role"** through the existing assignment helpers, never by
   writing `role_id` on the user.
4. **Audit every security-relevant change**: user and role changes, permission
   edits, configuration publishes, archive restore, financial posting and
   reversal, and sensitive administrator actions.
5. **Never widen access to unblock a feature.** Grant the narrowest code that
   makes the feature work.

## Security and validation requirements

- **No privilege escalation.** A user cannot grant themselves a permission they do
  not hold; the last Platform Administrator cannot be removed, deactivated, or
  deleted; the protected account cannot be edited into a weaker state.
- **Never return credentials.** Password hashes live in `user_credentials` and are
  never serialized. `core/crypto.py::SENSITIVE_FIELD_NAMES` lists fields that must
  be masked in responses and in archive snapshots.
- **Authorization is server-side.** A frontend `permission` in `definePageMeta` or
  a hidden button is UX, not enforcement. Do not report a feature protected because
  the button is hidden.
- **Rate-limit login and unauthenticated probes**; lockout policy lives in
  `auth/service.py` (`MAX_FAILED_ATTEMPTS`, `LOCKOUT_MINUTES`).
- Do not log tokens, cookies, or request bodies containing credentials.
- Backup and restore paths must redact secrets (`backup/service.py::SENSITIVE_HINTS`).
- Never commit a secret. `.gitignore` covers `.env`, `*.pem`, `*.key`; a private key
  found inside the repository is a finding to report, not a file to delete without
  asking.

## Testing

```bash
cd backend
uv run python -m pytest tests/test_auth_rbac.py tests/test_role_permissions.py tests/test_auth_remember_me.py -q --no-header
uv run python -m pytest -q && uv run ruff check .
```

Required coverage for a change:

| Case | Expected |
|---|---|
| Valid login | access token + rotated refresh session |
| Bad password repeated past the threshold | account locked for the configured window |
| Endpoint called without a permission | 403 and an `AUTHORIZATION_DENIED` audit event |
| Endpoint called with the wrong role | 403 |
| Second active role assigned to a user | previous assignment expired, exactly one active |
| Protected admin deactivated or deleted | rejected |
| Last Platform Administrator removed | rejected |
| Self-escalation attempt | rejected |
| Deactivated user's existing token | rejected via `token_version` |
| Sensitive field in a response or snapshot | masked |

Remember the test client keeps the login cookie: clear `client.cookies` before
asserting that an anonymous request is rejected, or the test silently exercises an
authenticated request.

## Acceptance criteria

- Every new endpoint declares a permission, and a test proves denial without it.
- The permission is grantable from the Roles screen (page mapping exists).
- Administrative self-protection and last-admin guards still hold.
- No secret is exposed in a response, an audit snapshot, a log, or a commit.
- Audit events are written for the changes listed in step 4.
- Backend suite and ruff pass; the frontend contract test still passes.

## Expected outputs

- Changed `permissions.py`, `auth/service.py`, and/or the module router.
- A row in `docs/09_roles_and_permissions.md`.
- Authorization tests including the denial path.
- A security finding recorded in `docs/11_deployment_and_security.md` §18 if a gap cannot be closed now.
