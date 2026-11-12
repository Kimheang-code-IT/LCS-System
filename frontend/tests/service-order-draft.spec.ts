import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  clearRecordDraft,
  draftAppliesTo,
  draftConflictsWithServer,
  readRecordDraft,
  recordDraftKey,
  sanitizeDraftModel,
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

const user = 'u1'
const keyFor = (recordId: string) => recordDraftKey(user, 'serviceOrders', recordId)

describe('service order draft persistence', () => {
  afterEach(() => { vi.unstubAllGlobals() })

  it('restores an eligible draft after a refresh/reopen', () => {
    vi.stubGlobal('localStorage', memoryStorage())
    const key = keyFor('12')
    writeRecordDraft(key, {
      recordId: '12',
      baseUpdatedAt: '2026-11-12T08:00:00Z',
      model: { internalReference: 'REF-1', places: [{ id: 'p1', place: 'Port' }] },
    }, 'local')

    const draft = readRecordDraft(key, 'local')!
    expect(draftAppliesTo(draft, '12', '2026-11-12T08:00:00Z')).toBe(true)
    expect(draft.model.internalReference).toBe('REF-1')
    expect((draft.model.places as Array<Record<string, unknown>>)[0]!.place).toBe('Port')
  })

  it('isolates drafts by user and by record', () => {
    vi.stubGlobal('localStorage', memoryStorage())
    writeRecordDraft(keyFor('12'), { recordId: '12', baseUpdatedAt: '', model: { description: 'A' } }, 'local')
    writeRecordDraft(keyFor('13'), { recordId: '13', baseUpdatedAt: '', model: { description: 'B' } }, 'local')

    expect(recordDraftKey('u2', 'serviceOrders', '12')).not.toBe(keyFor('12'))
    expect(readRecordDraft(recordDraftKey('u2', 'serviceOrders', '12'), 'local')).toBeNull()
    expect(readRecordDraft(keyFor('13'), 'local')!.model.description).toBe('B')
  })

  it('does not silently apply a draft written against an older server copy', () => {
    vi.stubGlobal('localStorage', memoryStorage())
    const key = keyFor('12')
    writeRecordDraft(key, { recordId: '12', baseUpdatedAt: '2026-11-12T08:00:00Z', model: { description: 'old' } }, 'local')
    const draft = readRecordDraft(key, 'local')!

    expect(draftAppliesTo(draft, '12', '2026-11-12T09:00:00Z')).toBe(false)
    expect(draftConflictsWithServer(draft, '12', '2026-11-12T09:00:00Z')).toBe(true)
  })

  it('clears only the saved record draft and survives corrupt storage', () => {
    const storage = memoryStorage()
    vi.stubGlobal('localStorage', storage)
    writeRecordDraft(keyFor('12'), { recordId: '12', baseUpdatedAt: '', model: { a: 1 } }, 'local')
    writeRecordDraft(keyFor('13'), { recordId: '13', baseUpdatedAt: '', model: { b: 2 } }, 'local')
    clearRecordDraft(keyFor('12'), 'local')
    expect(readRecordDraft(keyFor('12'), 'local')).toBeNull()
    expect(readRecordDraft(keyFor('13'), 'local')).not.toBeNull()

    storage.setItem(keyFor('14'), '{broken')
    expect(readRecordDraft(keyFor('14'), 'local')).toBeNull()
    expect(storage.getItem(keyFor('14'))).toBeNull()
  })

  it('degrades to no-op when browser storage is unavailable', () => {
    vi.stubGlobal('localStorage', undefined)
    expect(() => writeRecordDraft(keyFor('12'), { recordId: '12', baseUpdatedAt: '', model: {} }, 'local')).not.toThrow()
    expect(readRecordDraft(keyFor('12'), 'local')).toBeNull()
    expect(() => clearRecordDraft(keyFor('12'), 'local')).not.toThrow()
  })

  it('keeps every visited tab mounted so tab switches cannot discard values', () => {
    const APP = fileURLToPath(new URL('../app', import.meta.url))
    const detail = readFileSync(`${APP}/components/freight/JobDetail.vue`, 'utf8')
    for (const tab of ['overview', 'route', 'containers', 'files']) {
      expect(detail).toContain(`tabVisited('${tab}')`)
    }
    // v-show hides the inactive tab instead of unmounting it.
    expect(detail).toContain("v-show=\"activeTab === 'overview'\"")
    expect(detail).toContain("v-show=\"activeTab === 'route'\"")
    expect(detail).toContain("v-show=\"activeTab === 'containers'\"")
    expect(detail).toContain('v-if="chargesVisited" v-show="activeTab === \'charges\'"')
    expect(detail).toContain('v-if="financeVisited" v-show="activeTab === \'finance\'"')
    expect(detail).toContain('useRecordFormDraft')
    expect(detail).toContain('formDraft')
  })

  it('never persists File objects, credentials or client-only keys', () => {
    const model = sanitizeDraftModel({
      internalReference: 'REF-1',
      password: 'secret',
      accessToken: 'token',
      _uiOpen: true,
      file: new Blob(['x']),
      nested: { description: 'kept', _temp: 1 },
    })
    expect(model.internalReference).toBe('REF-1')
    expect(model.nested).toEqual({ description: 'kept' })
    expect(model.password).toBeUndefined()
    expect(model.accessToken).toBeUndefined()
    expect(model._uiOpen).toBeUndefined()
    expect(model.file).toBeUndefined()
  })
})
