import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  canCreateReference,
  referenceCreateDialog,
  referenceCreateTarget,
} from '../app/utils/freight/reference-create'
import {
  clearRecordDraft,
  draftAppliesTo,
  readRecordDraft,
  recordDraftKey,
  writeRecordDraft,
} from '../app/composables/common/useRecordDraft'

function memoryStorage(): Storage {
  const map = new Map<string, string>()
  return {
    get length() { return map.size },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => map.delete(key),
    setItem: (key: string, value: string) => map.set(key, value),
  } as Storage
}

describe('reference-create dialog targets', () => {
  it('offers the small dialog only for masters whose spec needs a code and a name', () => {
    for (const key of ['feeType', 'feeTypeId', 'containerType', 'placeRoleId', 'roleIds', 'direction', 'transportBy', 'currency']) {
      const dialog = referenceCreateDialog(key)
      expect(dialog, key).not.toBeNull()
      expect(dialog!.fields.map(field => field.key).sort()).toEqual(['code', 'name'])
    }
  })

  it('keeps complex masters on the full Master Data page flow', () => {
    // Business parties need roles/codes, document types need behaviour +
    // availability: both must not open the tiny dialog.
    expect(referenceCreateDialog('customerPartyId')).toBeNull()
    expect(referenceCreateDialog('documentType')).toBeNull()
    expect(referenceCreateDialog('documentTypeId')).toBeNull()
  })

  it('keeps the legacy master-data page target as the fallback', () => {
    expect(referenceCreateTarget('documentType')?.path).toBe('/master-data/document-types/new')
  })

  it('selects the value field the quotation form stores', () => {
    // Place roles are stored by id; trade directions by name.
    expect(referenceCreateDialog('placeRoleId')?.valueField).toBe('id')
    expect(referenceCreateDialog('direction')?.valueField).toBe('name')
  })
})

describe('canCreateReference', () => {
  it('allows the coarse reference manager and ALL_PAGES', () => {
    expect(canCreateReference(['master.reference.manage'], [], 'feeType')).toBe(true)
    expect(canCreateReference([], ['ALL_PAGES'], 'feeType')).toBe(true)
    expect(canCreateReference(['configuration.manage'], [], 'feeType')).toBe(true)
  })

  it('refuses a viewer without any create authority', () => {
    expect(canCreateReference(['quotation.read'], [], 'feeType')).toBe(false)
    expect(canCreateReference([], [], 'feeType')).toBe(false)
  })
})

describe('record draft persistence', () => {
  const key = recordDraftKey('u1', 'quotations', '')
  let restore: (() => void) | undefined

  beforeEach(() => {
    vi.stubGlobal('sessionStorage', memoryStorage())
    restore = () => vi.unstubAllGlobals()
  })

  afterEach(() => {
    restore?.()
  })

  it('writes a versioned draft and reads it back unchanged', () => {
    writeRecordDraft(key, { recordId: '', baseUpdatedAt: '', model: { date: '2026-11-01', customerPartyId: '9' } })
    const draft = readRecordDraft(key)!
    expect(draft.v).toBe(1)
    expect(draft.recordId).toBe('')
    expect(draft.model.customerPartyId).toBe('9')
  })

  it('applies a draft to a new quotation and to an unchanged existing record', () => {
    writeRecordDraft(recordDraftKey('u1', 'quotations', '55'), {
      recordId: '55',
      baseUpdatedAt: '2026-11-01T00:00:00Z',
      model: { description: 'dirty' },
    })
    const draft = readRecordDraft(recordDraftKey('u1', 'quotations', '55'))!
    expect(draftAppliesTo(draft, '55', '2026-11-01T00:00:00Z')).toBe(true)
    expect(draftAppliesTo(draft, '55', '2026-11-02T00:00:00Z')).toBe(false)
    expect(draftAppliesTo(draft, '66', '2026-11-01T00:00:00Z')).toBe(false)
  })

  it('treats a new-record draft as always applicable to the new form', () => {
    writeRecordDraft(key, { recordId: '', baseUpdatedAt: '', model: {} })
    const draft = readRecordDraft(key)!
    expect(draftAppliesTo(draft, '', undefined)).toBe(true)
  })

  it('forgives corrupt storage and clears cleanly', () => {
    sessionStorage.setItem(key, '{not json')
    expect(readRecordDraft(key)).toBeNull()
    clearRecordDraft(key)
    expect(readRecordDraft(key)).toBeNull()
  })
})