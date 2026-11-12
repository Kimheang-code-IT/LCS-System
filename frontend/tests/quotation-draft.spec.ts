import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  canCreateReference,
  referenceCreateModule,
  referenceCreatePayload,
  referenceCreateValueField,
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

describe('quick entry module resolution', () => {
  it('resolves a creatable module for every referenced master field', () => {
    // Document forms, line tables and the finance entry dialog all rely on the
    // same registry: a key without a module shows no Add New.
    const fields = [
      'feeType', 'feeTypeId', 'containerType', 'placeRoleId', 'roleIds', 'roles',
      'direction', 'tradeDirection', 'transportBy', 'currency', 'fromCurrencyCode',
      'toCurrencyCode', 'documentType', 'documentTypeId', 'partyId', 'customerPartyId',
      'ownerParty', 'operatorParty', 'capacityUnit', 'identityType',
      'debitAccount', 'creditAccount', 'taxAccount', 'financialAccountId',
    ]
    for (const key of fields) {
      expect(referenceCreateModule(key), key).not.toBeNull()
    }
  })

  it('uses the module declared by the master, not a per-field copy', () => {
    expect(referenceCreateModule('feeType')?.collection).toBe('feeTypes')
    expect(referenceCreateModule('partyId')?.collection).toBe('businessParties')
    expect(referenceCreateModule('debitAccount')?.collection).toBe('chartOfAccounts')
    expect(referenceCreateModule('identityType')?.collection).toBe('transportAssetIdentityTypes')
    // Fields are the ones the full Master Data page renders.
    expect(referenceCreateModule('partyId')?.fields.map(field => field.key)).toEqual(
      expect.arrayContaining(['partyCode', 'legalName', 'roleIds']),
    )
  })

  it('refuses static selects, unknown keys and non-creatable modules', () => {
    expect(referenceCreateModule('status')).toBeNull()
    expect(referenceCreateModule('notAReference')).toBeNull()
    expect(referenceCreateModule('periodId')).toBeNull()
  })

  it('selects the value field the parent form stores', () => {
    // Place roles are stored by id; trade directions by name.
    expect(referenceCreateValueField('placeRoleId')).toBe('id')
    expect(referenceCreateValueField('direction')).toBe('name')
    expect(referenceCreateValueField('currency')).toBe('code')
  })

  it('posts the module form values without the id or computed fields', () => {
    const module = referenceCreateModule('documentType')!
    const payload = referenceCreatePayload(module, {
      id: '',
      code: 'CUSTOM',
      name: 'Custom Document',
      availableIn: ['sales'],
      postingRequired: 'No',
    })
    expect(payload).toEqual({
      code: 'CUSTOM',
      name: 'Custom Document',
      availableIn: ['sales'],
      postingRequired: 'No',
    })
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
    expect(draft.v).toBe(2)
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