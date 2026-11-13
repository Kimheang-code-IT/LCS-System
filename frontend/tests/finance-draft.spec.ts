import { describe, expect, it } from 'vitest'
import { useRecordFormDraft } from '../app/composables/common/useRecordFormDraft'
import { recordDraftKey, readRecordDraft } from '../app/composables/common/useRecordDraft'
import {
  financeDocumentFingerprint,
  financeDraftSnapshot,
  mergeFinanceDraftRows,
  reconcileReceiptAllocations,
} from '../app/utils/freight/finance-draft'

const source = (id: string, status: string, updatedAt = '2026-11-12T08:00:00Z') => ({
  id,
  status,
  updatedAt,
})

const serverRows = [
  { id: 'draft-1', description: 'Original draft', amount: 10, date: '2026-11-12', _isNew: false, _source: source('draft-1', 'Draft') },
  { id: 'posted-1', description: 'Posted invoice', amount: 50, date: '2026-11-12', _isNew: false, _source: source('posted-1', 'Posted') },
]

const draftRows = [
  { id: 'draft-1', _baseUpdatedAt: '2026-11-12T08:00:00Z', description: 'Edited draft', amount: 20, date: '2026-11-13' },
  { id: 'posted-1', _baseUpdatedAt: '2026-11-12T08:00:00Z', description: 'Hacked posted', amount: 1, date: '2026-11-13' },
  { id: 'new-1', _isNew: true, description: 'New expense', amount: 5, date: '2026-11-13' },
]

describe('finance entries draft restore', () => {
  it('recovers committed allocations after a lost response even when the invoice is now settled', () => {
    const [allocation] = reconcileReceiptAllocations(
      [{ id: 'invoice-1', amount: 100, outstanding: 0, completed: false }],
      [{ targetDocumentId: 'invoice-1', amount: '100.0000' }],
    )
    expect(allocation?.completed).toBe(true)
    expect(allocation?.amount).toBe(100)
  })

  it('does not mistake another amount or target for the intended allocation', () => {
    const [allocation] = reconcileReceiptAllocations(
      [{ id: 'invoice-1', amount: 100 }],
      [{ targetDocumentId: 'invoice-1', amount: 50 }, { targetDocumentId: 'invoice-2', amount: 100 }],
    )
    expect(allocation?.completed).toBe(false)
  })
  it('preserves finance identity and version metadata through the shared draft writer', () => {
    const storage = new Map<string, string>()
    const previous = globalThis.localStorage
    Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    } })
    try {
      const draft = useRecordFormDraft({
        collection: () => 'serviceOrderFinance', scope: () => 'u1', recordId: () => '1',
        model: () => ({ rows: financeDraftSnapshot(draftRows) }),
        sanitize: () => ({ rows: financeDraftSnapshot(draftRows) }),
        apply: () => {}, isDirty: () => true,
      })
      draft.bind()
      draft.flush()
      const stored = readRecordDraft(recordDraftKey('u1', 'serviceOrderFinance', '1'), 'local')!
      const restored = mergeFinanceDraftRows(serverRows, stored.model.rows as typeof draftRows, row => row._source)
      expect(restored.rows.find(row => row.id === 'new-1')).toMatchObject({ _isNew: true, amount: 5 })
      expect((stored.model.rows as typeof draftRows)[0]?._baseUpdatedAt).toBe('2026-11-12T08:00:00Z')
    }
    finally { Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: previous }) }
  })
  it('restores editable draft rows and new rows, never posted documents', () => {
    const { rows, skipped } = mergeFinanceDraftRows(serverRows, draftRows, row => row._source)
    expect(rows.find(row => row.id === 'draft-1')).toMatchObject({ description: 'Edited draft', amount: 20 })
    expect(rows.find(row => row.id === 'posted-1')).toMatchObject({ description: 'Posted invoice', amount: 50 })
    expect(rows.find(row => row.id === 'new-1')).toMatchObject({ _isNew: true, description: 'New expense' })
    expect(skipped).toBe(1)
  })

  it('skips a draft edited against an older server copy', () => {
    const { rows, skipped } = mergeFinanceDraftRows(
      [{ ...serverRows[0]!, _source: source('draft-1', 'Draft', '2026-11-12T10:00:00Z') }],
      [{ ...draftRows[0]! }],
      row => row._source,
    )
    expect(rows[0]).toMatchObject({ description: 'Original draft' })
    expect(skipped).toBe(1)
  })

  it('drops a draft whose document was deleted', () => {
    const { rows, skipped } = mergeFinanceDraftRows([], [draftRows[0]!], row => row._source)
    expect(rows).toHaveLength(0)
    expect(skipped).toBe(1)
  })

  it('fingerprints the server copy so a changed document is not overwritten', () => {
    const base = { status: 'Draft', total: 10, currency: 'USD', documentDate: '2026-11-12', lines: [{ description: 'A', quantity: 1, unitPrice: 10 }] }
    const changed = { ...base, total: 12 }
    expect(financeDocumentFingerprint(base)).toBe(financeDocumentFingerprint({ ...base }))
    expect(financeDocumentFingerprint(base)).not.toBe(financeDocumentFingerprint(changed))
  })

  it('serialises only editable fields and no server payload copy', () => {
    const [snapshot] = financeDraftSnapshot([{
      id: 'draft-1',
      _isNew: false,
      _source: { lines: [{ secret: true }] },
      description: 'Edited',
      amount: 20,
      currency: 'USD',
    }])
    expect(snapshot).toMatchObject({ id: 'draft-1', description: 'Edited', amount: 20, currency: 'USD' })
    expect(snapshot).not.toHaveProperty('_source')
  })
})
