---
name: lcs-development
description: Use when implementing, debugging, reviewing, testing, refactoring, or modifying the LCS System backend, frontend, database, API, finance, authentication, infrastructure, or deployment.
---

# LCS System Development Skill

## Purpose

Use this skill whenever working on the LCS Freight Forwarding Platform.

The goal is to make safe, consistent, production-quality changes without breaking existing business logic, database integrity, API contracts, permissions, finance logic, or deployment.

## Project Context

LCS is a modular-monolith freight-forwarding, operations, and double-entry finance platform.

Main technologies:

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic
- Frontend: Nuxt 4, Vue, TypeScript, Pinia
- Database: PostgreSQL
- Cache/service: Redis
- Object storage: MinIO
- Infrastructure: Docker Compose + nginx
- Backend package manager: uv
- Frontend package manager: pnpm

Before making changes, read:

1. `AGENTS.md`
2. `README.md`
3. Relevant files under `docs/`
4. Existing implementation of the affected module
5. Existing tests for that module

Treat `docs/` and `AGENTS.md` as authoritative project references.

---

## Core Working Rule

Never start coding immediately for a non-trivial task.

First:

1. Understand the request.
2. Inspect the existing implementation.
3. Identify affected backend modules.
4. Identify affected frontend modules.
5. Identify database impact.
6. Identify API impact.
7. Identify permission impact.
8. Identify tests that may be affected.
9. Create a short implementation plan.
10. Then implement the change.

Prefer modifying existing architecture over introducing a new pattern.

Do not create duplicate services, repositories, endpoints, schemas, stores, helpers, or components when an appropriate implementation already exists.

---

# Backend Rules

Backend code lives under:

`backend/app/`

Business modules live under:

`backend/app/modules/<module>/`

Typical module files include:

- `router.py`
- `service.py`
- `models.py`
- schemas and supporting module files

Current major modules include:

- auth
- master_data
- quotations
- operations
- finance
- reports
- settings
- setup
- audit

When adding an API route, register it correctly through the existing API routing architecture.

Do not bypass the service layer when the existing module architecture expects business logic there.

Keep business logic out of route handlers where possible.

---

# Database Rules

Use SQLAlchemy models and Alembic migrations.

Never:

- manually modify production database structure
- delete data without explicit requirement
- rewrite migration history casually
- drop tables or columns merely because they appear unused
- change financial records destructively

Before changing a database model:

1. Inspect the existing model.
2. Search for all references.
3. Check API schemas.
4. Check services.
5. Check frontend usage.
6. Check reports.
7. Check tests.
8. Check reset/bootstrap logic.
9. Create or update the appropriate Alembic migration.

New model modules must also be included wherever the project's migration/bootstrap architecture requires them.

Prefer backward-compatible migrations whenever practical.

---

# API Rules

LCS APIs use `/api/v1`.

Successful API responses follow the project's existing response envelope.

Normal payload:

`{"data": ...}`

Paginated collections use the existing pagination structure containing:

- items
- page
- page_size
- total

Use the project's existing error handling rather than inventing another error format.

Before creating a new endpoint, search for an existing endpoint that already provides the required behavior.

Do not create frontend-only fake APIs or mock production data.

---

# Frontend Rules

Frontend code lives under:

`frontend/`

The application uses Nuxt 4 with SSR disabled and is generated as a static SPA.

Use existing:

- repositories
- stores
- composables
- components
- API constants
- configuration

Do not call backend APIs using random direct `fetch()` calls when the existing repository architecture can handle them.

API paths must be registered through the project's existing API endpoint constants and remote endpoint configuration.

Reuse existing UI components and patterns before creating new ones.

Keep TypeScript types explicit for important business objects.

Do not use `any` simply to silence type errors unless there is a documented reason.

---

# Frontend ↔ Backend Contract

Frontend and backend changes must stay synchronized.

When adding or changing an API:

1. Update backend route.
2. Update backend schema/service.
3. Update permissions if required.
4. Update frontend API constants.
5. Update repository method.
6. Update store/composable if required.
7. Update UI.
8. Update tests.

Never leave a frontend endpoint without a corresponding backend route.

Never rename or remove an API without searching the entire frontend for consumers.

---

# Authentication and Authorization

The application uses JWT authentication with rotating refresh sessions.

Do not bypass authentication or permission checks for convenience.

When adding protected functionality:

1. Determine the required permission.
2. Check the permission catalog.
3. Add/update the permission if necessary.
4. Protect the backend endpoint.
5. Apply appropriate frontend visibility/access rules.
6. Add authorization tests.

Backend authorization is authoritative.

Frontend hiding alone is not security.

---

# Finance Safety

Finance is a double-entry accounting system.

Changes affecting:

- journals
- accounts
- financial documents
- posting
- allocation
- balances
- reporting

must be treated as high-risk.

Before modifying finance logic:

1. Understand the existing posting flow.
2. Identify debit and credit effects.
3. Preserve double-entry balance.
4. Preserve historical records.
5. Avoid destructive updates to posted transactions.
6. Add regression tests.
7. Verify financial reports after the change.

Never silently modify posted accounting history.

---

# Quotations and Operations

Preserve existing quotation revision and conversion behavior.

When changing service orders, containers, charges, files, or dynamic tabs, inspect the relationships between:

- quotations
- operations
- master data
- finance
- reports

Do not assume a module is isolated.

---

# Reports

Reports and dashboard KPIs are backend-driven.

Do not duplicate report calculations in the browser unless the architecture explicitly requires it.

Business calculations should have one authoritative implementation.

---

# File Storage

Attachments use the project's storage abstraction and MinIO/S3-compatible storage in the normal deployment.

Do not hard-code local filesystem paths into business features.

Respect the existing upload/download and signed URL architecture.

---

# Security

Never commit:

- passwords
- API keys
- JWT secrets
- database passwords
- cloud credentials
- private keys
- production `.env` files

Validate external input.

Use existing authentication, authorization, validation, and storage abstractions.

Do not disable security controls just to make a feature work.

---

# Implementation Workflow

For every significant task:

## Step 1 — Analyze

Search the repository for:

- related feature
- models
- endpoints
- services
- frontend pages
- components
- stores
- repositories
- tests
- documentation

## Step 2 — Plan

Describe:

- files to modify
- database impact
- API impact
- frontend impact
- security impact
- tests required

## Step 3 — Implement

Make the smallest coherent change that fully solves the requirement.

Avoid unrelated refactoring.

## Step 4 — Validate

Check:

- imports
- typing
- migrations
- API contract
- permissions
- business logic
- frontend behavior
- tests

## Step 5 — Test

Backend commands must be run from `backend/`.

Run:

`uv run pytest -q`

then:

`uv run ruff check .`

For database-related changes also verify:

`uv run alembic upgrade head`

Frontend commands must be run from `frontend/`.

Run:

`pnpm lint`

then:

`pnpm typecheck`

then:

`pnpm test`

For production/build-impacting changes also run:

`pnpm generate`

## Step 6 — Final Review

Before declaring the task complete:

- inspect the diff
- ensure no debug code remains
- ensure no secrets were added
- ensure no unnecessary files changed
- ensure migrations are correct
- ensure frontend/backend contracts match
- ensure tests cover important business behavior

---

# Bug Fix Workflow

When fixing a bug:

1. Reproduce or clearly identify the failure.
2. Find the root cause.
3. Do not patch only the visible symptom.
4. Check whether similar code has the same problem elsewhere.
5. Implement the smallest safe fix.
6. Add a regression test when practical.
7. Run affected tests.
8. Run the relevant quality gates.

Do not change unrelated behavior while fixing the bug.

---

# Refactoring Rules

Refactoring must preserve behavior unless behavior changes are explicitly requested.

Before deleting code:

- search all references
- inspect dynamic imports/configuration
- inspect tests
- inspect API consumers
- inspect database dependencies

Do not remove a database column or table merely because static search finds no obvious reference.

---

# Completion Requirements

A task is complete only when:

- requested behavior is implemented
- existing architecture is respected
- backend/frontend contracts remain valid
- authorization is correct
- database changes are migrated safely
- important edge cases are handled
- tests pass
- lint/type checks pass
- no secrets or debug code were introduced

When reporting completion, summarize:

1. What changed
2. Files changed
3. Database changes
4. API changes
5. Tests added or updated
6. Commands executed
7. Results
8. Remaining risks or limitations

Never claim a command or test passed unless it was actually executed.
