# PLAN-0007 — Service Order authorized files/attachments (S03 task batch)

## Metadata

Slice: S03 — Operational Execution (P06 task 06.2 authorized-files portion)
Status: Completed
Last updated: 2026-11-05
Task level: STANDARD (browser + unit verification of existing backend; frontend shared-code fixes)

## Objective and requirement IDs

Authorized files attached to a Service Order persist, preview through the controlled
download endpoint, and can be deleted only by an account holding `attachment.delete`;
read-only accounts see no upload/delete affordances and the API refuses them.
Requirements: LCS-004, LCS-010 (authorized files), MOD-003 files tab;
owner [P06 task 06.2](../phases/P06-service-orders.md).

## Dependencies and current implementation evidence

The backend attachment flow (presign/upload → `AttachmentLink(entity_type='jobs')` →
soft-delete) already existed and was verified read-only 2026-11-04: SO detail/list assemble
`attachments` from the authoritative `AttachmentLink` rows via `_attachment_payload`
(`storageKey` + presigned url after an expiring `url`). No backend change in this batch.

## Scope and planned changes

Verification-first; fix only demonstrated defects (all frontend shared code):

- Preview of persisted storage-key files through `safeFilePreviewUrl`/`filePreviewHref`.
- Row-menu Delete affordance on file tables, gated by permission and edit state.
- Files grid repopulation when attachments load after the record.

## Verification and exact results

| Check | Command | Result / date |
|---|---|---|
| Browser upload→persist→preview→delete + viewer deny-side | `browser e2e run of e2e/attachments.spec.ts` (local dev compose stack at http://localhost, rebuilt frontend container) | 2 passed, 2026-11-05. Uploaded `booking-slip.png` through the Files tab on the fixture SO (`ATTACH{stamp}` party → quotation → SO), persisted across reload, preview link href contains `/attachments/` and answers <400; Actions → Delete removes the stored link (names poll). Viewer: upload/delete hidden, API 403/404, no row leak |
| Type/lint/unit gates | `pnpm typecheck`; `pnpm exec eslint` (touched files); `pnpm exec vitest run` | typecheck 0 errors; eslint clean; 825 passed (99 files) 2026-11-05, incl. `tests/file-preview.spec.ts` +2 cases (storage-key endpoint wins over an expiring presigned url; `//evil.example` relative URL refused) |
| Regression slice | `browser e2e run of e2e/action-gating.spec.ts e2e/qa-business-workflows.spec.ts` | 9 passed / 4 skipped (skipped rows are existing separate-fixture tests), 2026-11-05 |

## Demonstrated defects fixed

1. **Silent preview drop** — `safeFilePreviewUrl()` (`app/utils/security/url.ts`) rejected
   leading-slash relative URLs because `new URL(raw)` throws for them; persisted
   storage-key previews therefore rendered as plain names. Now accepts `/path`
   (never `//authority`), keeps blob:/data:/http(s) handling unchanged.
2. **No Delete affordance** — file tables (FILE_ATTACHMENT_COLUMNS) have no
   `type:'delete'` column, so `hasDeleteColumn` was never true and the row menu offered no
   removal. `AppLineTable` now adds a Delete action for file tables gated by
   `attachment.delete` (auth store) and `!props.disabled`, calling the existing
   `removeRow` → `removeUploaded` path (soft delete via the attachments API).
3. **Late attachment load** — `JobFiles.loadRows` did not rerun when attachments attached to
   a late-loaded record arrived; its watch now includes `job.attachments.length`.

## Acceptance criteria

1. Authorized upload through the Files tab is stored, linked to the order and listed after
   reload — proven (browser).
2. Preview goes through `/api/v1/attachments/file/{storageKey}` and answers — proven.
3. Delete removes the stored link exactly once and only with `attachment.delete`; viewer
   has no UI affordance and API refusal — proven.
4. No backend change, no posting side effect, soft delete preserves audit — read-only source
   verification.

## Handoff

- Plan closed 2026-11-05. Checklist row E26 records the evidence. No commit authorized yet.
- Remaining S03 slice items: closed 2026-11-05 by PLAN-0008 (E27): FLOW-004/005 + DATA-006
  COMPLETE; shared portions of DATA-011 (→S11), TECH-017/DATA-013 recovery (→S12) deferred
  with recorded owners. Actual containers, copied-pricing persistence and the Finish lock
  were verified in E25/E17 journeys.
- Limits: browser evidence Chromium-only (NT02); fixture rows `ATTACH{stamp}` remain in the
  disposable dev DB (documented in the spec header). No production data touched.
