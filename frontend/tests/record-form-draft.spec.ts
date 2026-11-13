import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import {
  clearRecordDraft,
  clearRecordDraftsForUser,
  readRecordDraft,
  readRecordDraftsByPrefix,
  recordDraftKey,
  writeRecordDraft,
} from '../app/composables/common/useRecordDraft'
import { useRecordFormDraft } from '../app/composables/common/useRecordFormDraft'

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

function form(model: Record<string, unknown>, overrides: Record<string, unknown> = {}) {
  const recordId = ref('12')
  const state = { model, dirty: true, canDraft: true, recordId, base: '2026-11-12T08:00:00Z' }
  const draft = useRecordFormDraft<Record<string, unknown>>({
    collection: () => 'quotations',
    scope: () => user,
    recordId: () => state.recordId.value,
    baseUpdatedAt: () => state.base,
    model: () => state.model,
    apply: (stored) => { state.model = { ...state.model, ...stored } },
    isDirty: () => state.dirty,
    canDraft: () => state.canDraft,
    delay: 50,
    ...overrides,
  })
  draft.bind()
  return { state, draft }
}

describe('useRecordFormDraft', () => {
  it('keeps an opted-in conflicting draft until explicit restore or discard', () => {
    const { state, draft } = form({ description: 'Unsaved route' }, { preserveConflict: true })
    draft.flush()
    state.base = '2026-11-12T09:00:00Z'
    state.model = { description: 'Newer server route' }
    expect(draft.restore()).toBe('none')
    expect(draft.conflict.value).toBe(true)
    state.dirty = false
    draft.flush()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')?.model.description).toBe('Unsaved route')
    draft.restoreConflict()
    expect(state.model.description).toBe('Unsaved route')
    expect(draft.conflict.value).toBe(false)
    draft.clear()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')).toBeNull()
  })
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage())
    vi.stubGlobal('sessionStorage', memoryStorage())
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('writes a versioned envelope scoped by user, module and record', () => {
    const { draft } = form({ description: 'Draft text' })
    draft.flush()
    const stored = readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')!
    expect(stored.v).toBe(2)
    expect(stored.collection).toBe('quotations')
    expect(stored.scope).toBe(user)
    expect(stored.model.description).toBe('Draft text')
  })

  it('restores a compatible draft and drops one written against a newer server copy', () => {
    const { state, draft } = form({ description: 'Draft text' })
    draft.flush()

    state.model = { description: 'Server text' }
    expect(draft.restore()).toBe('applied')
    expect(state.model.description).toBe('Draft text')

    state.base = '2026-11-12T09:00:00Z'
    expect(draft.restore()).toBe('none')
    // The newer server copy wins; the stale local draft is discarded silently.
    expect(state.model.description).toBe('Draft text')
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')).toBeNull()
  })

  it('never restores or writes when the form is read-only', () => {
    const { state, draft } = form({ description: 'Posted' })
    state.canDraft = false
    draft.flush()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')).toBeNull()

    writeRecordDraft(recordDraftKey(user, 'quotations', '12'), {
      recordId: '12',
      collection: 'quotations',
      baseUpdatedAt: '2026-11-12T08:00:00Z',
      model: { description: 'stale' },
    }, 'local')
    expect(draft.restore()).toBe('none')
  })

  it('reads a legacy sessionStorage draft when no local copy exists', () => {
    writeRecordDraft(recordDraftKey(user, 'quotations', '12'), {
      recordId: '12',
      baseUpdatedAt: '2026-11-12T08:00:00Z',
      model: { description: 'legacy session' },
    }, 'session')
    const { state, draft } = form({ description: '' })
    expect(draft.restore()).toBe('applied')
    expect(state.model.description).toBe('legacy session')
  })

  it('ignores a draft stored under another module in the same slot', () => {
    writeRecordDraft(recordDraftKey(user, 'quotations', '12'), {
      recordId: '12',
      collection: 'debitNotes',
      baseUpdatedAt: '2026-11-12T08:00:00Z',
      model: { total: 1 },
    }, 'local')
    const { state, draft } = form({ description: '' })
    expect(draft.restore()).toBe('none')
    expect(state.model.description).toBe('')
  })

  it('debounces writes and flushes the pending edit', () => {
    vi.useFakeTimers()
    const { state, draft } = form({ description: 'a' })
    draft.schedule()
    state.model = { description: 'ab' }
    draft.schedule()
    vi.advanceTimersByTime(49)
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')).toBeNull()
    vi.advanceTimersByTime(1)
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')!.model.description).toBe('ab')
  })

  it('clears the pre-save new slot when the record id arrives', () => {
    const { state, draft } = form({ description: 'new' })
    state.recordId.value = ''
    draft.bind()
    draft.flush()
    const newKey = recordDraftKey(user, 'quotations', '')
    expect(readRecordDraft(newKey, 'local')).not.toBeNull()

    state.recordId.value = '99'
    draft.clear()
    expect(readRecordDraft(newKey, 'local')).toBeNull()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '99'), 'local')).toBeNull()
  })

  it('does not rewrite a committed save when the form unmounts', () => {
    const { state, draft } = form({ description: 'saved' })
    state.recordId.value = ''
    draft.bind()
    draft.schedule()

    state.recordId.value = '42'
    state.base = '2026-11-12T09:00:00Z'
    draft.clear()

    // Leaving the page right after the save (onBeforeUnmount) must not turn the
    // saved model back into a draft for the next "New" form.
    draft.flush()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '42'), 'local')).toBeNull()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', ''), 'local')).toBeNull()
  })

  it('drafts again after a new edit follows a save', () => {
    const { state, draft } = form({ description: 'saved' })
    draft.clear()
    state.model = { description: 'edited again' }
    draft.schedule()
    draft.flush()
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')!.model.description)
      .toBe('edited again')
  })

  it('drops File/secret values before writing', () => {
    const { draft } = form({
      description: 'kept',
      password: 'secret',
      accessToken: 'token',
      _ui: true,
      file: new Blob(['x']),
    })
    draft.flush()
    const stored = readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')!
    expect(stored.model).toEqual({ description: 'kept' })
  })
})

describe('draft storage helpers', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage())
    vi.stubGlobal('sessionStorage', memoryStorage())
  })
  afterEach(() => vi.unstubAllGlobals())

  it('reads v1 drafts without discarding them', () => {
    const key = recordDraftKey(user, 'quotations', '12')
    localStorage.setItem(key, JSON.stringify({
      v: 1,
      savedAt: '2026-11-01T00:00:00Z',
      recordId: '12',
      baseUpdatedAt: '2026-11-01T00:00:00Z',
      model: { description: 'old draft' },
    }))
    expect(readRecordDraft(key, 'local')!.model.description).toBe('old draft')
  })

  it('lists new-record drafts newest first', () => {
    const prefix = recordDraftKey(user, 'serviceOrderCharge', '7:new:')
    writeRecordDraft(`${prefix}a`, {
      recordId: '7:new:a', collection: 'serviceOrderCharge', baseUpdatedAt: '', model: { savedAt: 1 },
    }, 'local')
    const older = readRecordDraft(`${prefix}a`, 'local')!
    localStorage.setItem(`${prefix}a`, JSON.stringify({ ...older, savedAt: '2026-11-01T00:00:00Z' }))
    writeRecordDraft(`${prefix}b`, {
      recordId: '7:new:b', collection: 'serviceOrderCharge', baseUpdatedAt: '', model: { savedAt: 2 },
    }, 'local')
    const entries = readRecordDraftsByPrefix(prefix, 'local')
    expect(entries).toHaveLength(2)
    expect(entries[0]!.key).toBe(`${prefix}b`)
  })

  it('clears only the signed-in user drafts on logout', () => {
    writeRecordDraft(recordDraftKey(user, 'quotations', '12'), { recordId: '12', model: {} }, 'local')
    writeRecordDraft(recordDraftKey('u2', 'quotations', '12'), { recordId: '12', model: {} }, 'local')
    clearRecordDraftsForUser(user)
    expect(readRecordDraft(recordDraftKey(user, 'quotations', '12'), 'local')).toBeNull()
    expect(readRecordDraft(recordDraftKey('u2', 'quotations', '12'), 'local')).not.toBeNull()
    clearRecordDraft(recordDraftKey('u2', 'quotations', '12'), 'local')
  })
})
