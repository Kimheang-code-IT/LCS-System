---
name: quotation-management
description: Use when implementing or changing LCS quotation creation, revision and version history, commercial pricing lines, send/accept/reject workflow, revision comparison, or conversion of an accepted quotation into a Service Order.
---

# Quotation management

Quotations are versioned commercial offers. An issued revision is a historical
record: it must never change after it is sent, and a Service Order must stay linked
to the exact revision it was converted from.

## When to use

- Creating or editing a quotation, or creating a new revision.
- Changing pricing lines, totals, or commercial terms.
- Sending, accepting, rejecting, or comparing revisions.
- Converting an accepted revision into a Service Order.

## Required inputs

1. Which revision is being acted on (`revisionId`), not just the quotation id.
2. The intended state transition and who may perform it.
3. Whether the quotation is already converted.

## Project references

| Document | Use it for |
|---|---|
| `docs/04_functional_design.md` | Intended quotation behaviour |
| `backend/app/modules/quotations/models.py` | `Quotation`, `QuotationRevision`, `QuotationRevisionLine`, `QuotationConversion` |
| `backend/app/modules/quotations/service.py` | The authoritative lifecycle implementation |
| `docs/14_47_table_migration_analysis.md` §2.3 | Why revisions are not renamed to "versions" |
| `docs/11_permissions_matrix.md` | `quotation.*` permission codes |

## Model and lifecycle

- `quotations` is the stable identity (number, customer, trade direction,
  `current_revision_no`, header status).
- `quotation_revisions` holds the commercial terms per version: `revision_no`,
  `status`, dates, currency, and totals. `UNIQUE(quotation_id, revision_no)`.
- `quotation_revision_lines` holds the priced lines; `quotation_revision_containers`
  and `quotation_revision_places` hold container requirements and the multi-leg
  route. **All three belong to a revision** — they are part of its history.
- `quotation_conversions` records the one-to-one link to a Service Order and is the
  duplicate-conversion guard (`UNIQUE(quotation_revision_id)`,
  `UNIQUE(service_order_id)`).

States: `DRAFT → SENT → ACCEPTED → CONVERTED`, with `REJECTED`, `SUPERSEDED`,
`EXPIRED`, and `CANCELLED` as terminal or superseding states.

`IMMUTABLE_STATUSES` in `quotations/service.py` is the set that may not be edited
in place. Editing a quotation whose latest revision is immutable automatically
clones a new draft — that is the versioning mechanism, so do not bypass it.

## Workflow

1. **Create the quotation and its first revision together.** A quotation without a
   revision has no commercial terms and no totals.
2. **Allocate the revision number under a lock.** `_clone_revision` takes
   `SELECT … FOR UPDATE` on the quotation header before computing `MAX(revision_no)+1`.
   Without the lock two concurrent "create revision" requests both read the same
   maximum and one hits the unique constraint. Keep the lock when changing this
   code.
3. **Clone, never mutate.** A new revision copies header, lines, containers, and
   places from its source and starts as `DRAFT`. The source is left byte-identical.
4. **Send, accept, reject are explicit state transitions.** Each records its own
   timestamp (`sent_at`, `accepted_at`, `rejected_at`). Accepting supersedes the
   competing revisions of the same quotation.
5. **Convert only an accepted revision.** `convert_revision` requires `ACCEPTED`,
   refuses a prior conversion with `Conflict("DUPLICATE_CONVERSION")`, creates the
   Service Order through `operations.create_service_order_from_quotation`, writes
   `QuotationConversion`, and moves both revision and quotation to `CONVERTED`.
   The order keeps `quotation_revision_id`, so the exact revision is preserved.
6. **Compare, do not recompute.** `compare_revisions` diffs two revisions of the
   *same* quotation: header fields, added/removed/modified lines, and the total
   difference. It never writes.
7. **A converted quotation cannot be deleted** (`QUOTATION_HAS_SERVICE_ORDER`); it
   is the audit trail behind the order.

## Security and validation requirements

- Sending and accepting need `quotation.send` / `quotation.accept`; converting needs
  `quotation.convert`. Do not merge these.
- Only a `SENT` revision may be accepted; only `ACCEPTED` may be converted. Reject
  anything else with `InvalidState`, not a silent no-op.
- Rejection is final for that revision: a follow-up offer is a new revision, which
  keeps the approval history readable. Reset `quotation.status` only when no other
  revision can still be accepted.
- Never recompute a historical total. `amount = quantity × unit_price` does **not**
  hold for a stored line, because the model applies a line-level discount and tax
  (`line_subtotal − line_discount + line_tax = line_total`). The stored values are
  the record.
- Validate that a referenced fee type, container type, and place exist; an unknown
  reference must be a field error, not a NULL.
- A rejected or superseded revision must not be reachable as "current".

## Testing

```bash
cd backend
uv run python -m pytest tests/test_quotation_versions.py tests/test_quotations.py -q --no-header
uv run python -m pytest -q && uv run ruff check .
```

Required coverage:

| Case | Expected |
|---|---|
| Create V1 | one revision, status DRAFT, totals stored |
| Edit a draft | same revision updated in place |
| Send, then edit | new revision created; V1 keeps its status, lines, and total |
| Create V2, V3 | distinct revision numbers, no duplicates |
| Concurrent revision creation | distinct numbers, no unique-constraint error |
| Compare two revisions | header and line differences plus total delta |
| Compare across quotations | rejected with a field error |
| Accept a non-sent revision | rejected |
| Reject a sent revision | `rejected_at` set, visible in history, cannot be accepted afterwards |
| Convert an accepted revision | Service Order created and linked to that revision |
| Convert twice | `DUPLICATE_CONVERSION` |
| Delete a converted quotation | `QUOTATION_HAS_SERVICE_ORDER` |

## Acceptance criteria

- An issued revision is never modified, proven by a test.
- Revision numbers are unique and race-safe under a row lock.
- The Service Order points at the exact conversion revision.
- Duplicate conversion is impossible.
- Permission denial is tested for send/accept/reject/convert.
- Full backend suite and ruff pass; the frontend contract test still passes.

## Expected outputs

- Changed `quotations/service.py`, `router.py`, and/or `models.py`.
- Tests covering every affected row of the table above.
- Updated quotation behaviour in the relevant `docs/` file, with the revision
  lifecycle and the immutability rule stated explicitly.
