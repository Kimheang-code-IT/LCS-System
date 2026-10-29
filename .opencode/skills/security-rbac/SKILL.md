---
name: security-rbac
description: Use when implementing or reviewing LCS authentication, authorization, Casbin policies, permissions, roles, role inheritance, session and token handling, audit events, administrator protection, or secret handling.
---

# Security and RBAC

Authentication and authorization for the LCS platform. The backend is the only
authorization authority; the frontend hides what a user should not see, it does not
protect anything.

## When to use

- Adding an endpoint and deciding which permission it needs.
- Changing roles, permissions, role assignment, inheritance, or the permission catalog.
- Touching sessions, tokens, password policy, or lockout.
- Handling a secret, a credential, or a sensitive field.
- Reviewing an authorization gap or an audit requirement.

## Required inputs

1. The operation and who should be allowed to perform it.
2. Whether an existing permission code already covers it.
3. Whether the change affects an administrator's own account or the last super administrator.

## Project references

| Document | Use it for |
|---|---|
| `docs/09_roles_and_permissions.md` | Casbin model, catalog, page→capability compile, role composition, enforcement, synchronization |
| `docs/11_deployment_and_security.md` §16-§17 | Controls that must stay enforced |
| `AGENTS.md` §Backend | Auth model, cookie/token transport |
| `backend/app/core/permissions.py` | The code-owned catalog, matrix pages, page grants and role seeds |
| `backend/app/core/authorization/` | The enforcer, policy readers/writers, cycle detection, Redis sync |
| `backend/app/core/deps.py`, `core/context.py`, `core/database.py` | Guard dependencies, per-decision check, denial audit |
| `backend/tests/test_auth_rbac.py`, `tests/test_role_permissions.py` | Existing coverage to extend |

## Model

- **JWT access token** (short-lived) delivered as `Authorization: Bearer` or a
  Secure HttpOnly cookie; **rotating refresh token** backed by a persisted
  `user_sessions` row. Refresh tokens are never readable from JavaScript.
- **One authorization engine: Casbin.** Policies live in `casbin_rule`
  (`p, role:SALES, quotation, read`; `g, user:15, role:SALES`;
  `g, role:MANAGER, role:VIEWER`). `roles` and `permissions` are display metadata
  and decide nothing.
- **Multiple roles per user.** Effective permissions are the union of every role,
  including the ones inherited through `g` edges.
- **Permission catalog is code-defined** in `app/core/permissions.py` and synced on
  startup (`ensure_permission_catalog`). The sync only *adds* what a role is missing,
  recompiles every stored role code set, and then reloads the enforcer.
- **Page codes vs capabilities.** The Roles screen grants page codes
  (`sales.quotations.view`); `resolve_role_codes`/`compile_role_permissions` turn them
  into the capability codes the guards check (`quotation.read`). Expansion is one
  hop in each direction and never loops.
- **Protected super administrator**: `SUPER_ADMIN` holds `p, role:SUPER_ADMIN, *, *`.
  Only a wildcard holder may modify it; the last holder cannot be unassigned,
  deactivated or deleted; the first user (`system_identity = DEFAULT_SYSTEM_ADMIN`)
  cannot be deleted or deactivated.
- **Tokens are versioned** (`users.token_version`): deactivation, forced logout,
  and password change bump it, so revocation is immediate despite stateless JWTs.
- **Fail closed.** If the policy table cannot be read, the in-memory copy is dropped
  and every check denies until a reload succeeds.

## Workflow

1. **Decide the permission first.** Search for an existing code before adding one.
   Adding a code requires:
   - an entry in `SOURCE_PERMISSIONS` (API capability) or the page/matrix tuples;
   - a page that grants it in `PAGE_PERMISSION_GRANTS` (or, for a deliberately
     coarse fallback, a note in `docs/09` §15);
   - a row in `docs/09_roles_and_permissions.md`;
   - a decision about which seeded role in `ROLE_DEFINITIONS` should hold it.
   `tests/test_role_permissions.py` fails if a capability no page can grant.
2. **Protect the endpoint** with `Depends(require_permission("code"))`
   (`require_permission(*codes)` requires all, `require_any_permission(*codes)` any).
   An inline guard may call `context.has_permission(code)`; either way the denial is
   audited once, by `core/database.py::record_denial` when the request session sees
   the `AccessDenied`.
3. **Never compute permissions yourself.** No module may read `roles`,
   `permissions`, `casbin_rule` or the frontend snapshot to decide access.
   `RequestContext.has_permission` is the only primitive.
4. **Assign roles through `app.core.authorization`**, never by writing a row.
5. **Audit every security-relevant change**: user and role changes, permission
   edits, configuration publishes, archive restore, financial posting and
   reversal, and sensitive administrator actions.
6. **Never widen access to unblock a feature.** Grant the narrowest code that
   makes the feature work.

## Security and validation requirements

- **No privilege escalation.** A user cannot grant a code they do not hold; a
  non-super administrator cannot touch `SUPER_ADMIN` or one of its holders; nobody
  can change their own roles; the last super administrator cannot be removed.
- **Role inheritance cannot cycle.** `would_create_cycle` rejects self and cyclic
  edges with a `422`.
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
uv run python -m pytest tests/test_auth_rbac.py tests/test_role_permissions.py -q --no-header
uv run python -m pytest -q && uv run ruff check app tests alembic scripts
```

Required coverage for a change:

| Case | Expected |
|---|---|
| Valid login | access token + rotated refresh session |
| Bad password repeated past the threshold | account locked for the configured window |
| Endpoint called without a permission | 403 and an `AUTHORIZATION_DENIED` audit event |
| Endpoint called with the wrong role | 403 |
| Role grant or revoke | policy rows change and the decision flips without re-login |
| Page checkbox saved | compile grants the capability the guard checks |
| Role inherits a parent | parent's capabilities apply; a cycle is rejected |
| Protected super administrator modified | rejected |
| Last super administrator removed | rejected |
| Self-escalation attempt | rejected |
| Deactivated user's existing token | rejected via `token_version` |
| Sensitive field in a response or snapshot | masked |

Remember the test client keeps the login cookie: clear `client.cookies` before
asserting that an anonymous request is rejected, or the test silently exercises an
authenticated request.

## Acceptance criteria

- Every new endpoint declares a permission, and a test proves denial without it.
- The permission is grantable from the Roles screen (a page grants it).
- Administrative self-protection and last-admin guards still hold.
- No secret is exposed in a response, an audit snapshot, a log, or a commit.
- Audit events are written for the changes listed in step 5.
- Backend suite and ruff pass; the frontend contract test still passes.

## Expected outputs

- Changed `permissions.py`, `core/authorization/*`, and/or the module router.
- A row in `docs/09_roles_and_permissions.md`.
- Authorization tests including the denial path.
- A security finding recorded in `docs/11_deployment_and_security.md` §18 if a gap cannot be closed now.
