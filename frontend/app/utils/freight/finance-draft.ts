/**
 * Restore rules for the Service Order Finance entries draft.
 *
 * Only rows that are still editable drafts are restored. A posted/reversed
 * document is authoritative and is never replaced by a local copy, and a draft
 * document whose server `updatedAt` moved past the copy the user edited is
 * reported as skipped so the operator can decide instead of silently losing an
 * edit.
 */
import { scaledDecimal } from './finance-summary'

/** Reconcile a committed allocation after a lost response, before validating retry bounds. */
export function reconcileReceiptAllocations<T extends { id: string, amount: unknown, completed?: boolean }>(
  drafts: readonly T[], saved: readonly Record<string, unknown>[],
): T[] {
  return drafts.map(allocation => ({
    ...allocation,
    completed: Boolean(allocation.completed || saved.some(row =>
      String(row.targetDocumentId) === allocation.id
      && scaledDecimal(row.amount) === scaledDecimal(allocation.amount))),
  }))
}

export const FINANCE_DRAFT_FIELDS = [
  'date',
  'type',
  'description',
  'partyId',
  'amount',
  'currency',
  'feeTypeId',
  'referenceNumber',
  'remark',
  'financialAccountId',
] as const

export type FinanceDraftRow = Record<string, unknown> & {
  id?: string
  _isNew?: boolean
  _baseUpdatedAt?: string
}

/**
 * Stable server-copy fingerprint. Financial documents have no `updatedAt`
 * column, so the fields a draft may overwrite identify the version it was
 * written against. A changed total/status/date/reference is a conflict.
 */
export function financeDocumentFingerprint(document: Record<string, unknown>): string {
  const lines = Array.isArray(document.lines)
    ? (document.lines as Array<Record<string, unknown>>).map(line => [
        line.description,
        line.quantity,
        line.unitPrice ?? line.unitAmount,
        line.discount,
        line.taxRate,
        line.taxAmount,
      ])
    : []
  return JSON.stringify([
    document.status,
    document.documentDate ?? document.date,
    document.total,
    document.currency,
    document.partyId,
    document.referenceNumber ?? document.referenceNo,
    document.remark ?? document.description,
    lines,
  ])
}

type DraftSource = { id?: string, status?: unknown, updatedAt?: unknown }

export function mergeFinanceDraftRows<Row extends Record<string, unknown>>(
  serverRows: Row[],
  draftRows: readonly FinanceDraftRow[],
  sourceOf: (row: Row) => DraftSource | undefined,
): { rows: Row[], skipped: number, rejected: FinanceDraftRow[] } {
  const byId = new Map(serverRows.map(row => [String(row.id ?? ''), row]))
  const restored = new Map<string, Row>()
  const additions: Row[] = []
  let skipped = 0
  const rejected: FinanceDraftRow[] = []

  for (const draft of draftRows) {
    const id = String(draft.id ?? '').trim()
    if (draft._isNew || !id) {
      additions.push({ ...draft, _isNew: true } as unknown as Row)
      continue
    }
    const server = byId.get(id)
    const source = server ? sourceOf(server) : undefined
    if (!server || !source) {
      skipped += 1
      rejected.push(draft)
      continue
    }
    if (String(source.status || '').toUpperCase() !== 'DRAFT') {
      skipped += 1
      rejected.push(draft)
      continue
    }
    const base = String(draft._baseUpdatedAt || '')
    const current = String(source.updatedAt || '')
    if (base && current && base !== current) {
      skipped += 1
      rejected.push(draft)
      continue
    }
    const next = { ...server } as Record<string, unknown>
    for (const field of FINANCE_DRAFT_FIELDS) {
      if (field in draft) next[field] = draft[field]
    }
    restored.set(id, next as Row)
  }

  return {
    rows: [
      ...serverRows.map(row => restored.get(String(row.id ?? '')) || row),
      ...additions,
    ],
    skipped,
    rejected,
  }
}

/** Minimal JSON-safe projection of a draft row (no `_source` payload copy). */
export function financeDraftSnapshot(rows: readonly Record<string, unknown>[]): FinanceDraftRow[] {
  return rows.map((row) => {
    const output: FinanceDraftRow = {
      id: String(row.id ?? ''),
      _isNew: Boolean(row._isNew),
      _baseUpdatedAt: String(row._baseUpdatedAt ?? ''),
    }
    for (const field of FINANCE_DRAFT_FIELDS) {
      if (field in row) output[field] = row[field]
    }
    return output
  })
}
