/** Quotation revision history: grid rows and revision-number formatting. */

export type RevisionRow = Record<string, unknown>

/** `R01`, `R02`; a missing revision number shows an em dash. */
export function formatRevisionNo(value: unknown): string {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? `R${String(Math.trunc(number)).padStart(2, '0')}` : '—'
}

/**
 * Rows for the Revisions grid, newest first.
 *
 * `createdBy` arrives as the display name, or as the numeric user id when the
 * account has no name any more; the second case shows an em dash instead of a
 * bare id.
 */
export function revisionGridRows(rows: RevisionRow[]): RevisionRow[] {
  return [...rows]
    .sort((a, b) => Number(b.revisionNo || 0) - Number(a.revisionNo || 0))
    .map((row) => {
      const creator = String(row.createdBy ?? '').trim()
      return {
        ...row,
        revisionNo: formatRevisionNo(row.revisionNo),
        createdBy: creator && !/^\d+$/.test(creator) ? creator : '—',
      }
    })
}
