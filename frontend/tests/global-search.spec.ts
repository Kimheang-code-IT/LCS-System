import { computed, effectScope, nextTick, onScopeDispose, ref, watch } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AiSearchAnswer, SearchHit } from '../app/types/search'
import { useGlobalSearch } from '../app/composables/search/useGlobalSearch'

const menu = vi.hoisted(() => vi.fn())
vi.mock('~/composables/layout/useMenu', () => ({ useMenu: menu }))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

function hit(id: string): SearchHit {
  return { id, entityId: id, entityType: 'document', title: id, text: id, snippet: id,
    url: `/quotations/${id}`, permission: 'quotation.read', mimeType: '', updatedAt: '', score: 1, sourceLabel: 'Quotations' }
}

type RequestOptions = { requestKey: string, query: { q: string, mode: string, limit: number } }
let reads: Array<ReturnType<typeof deferred<{ data: SearchHit[] }>> & { options: RequestOptions }>
let answers: Array<ReturnType<typeof deferred<{ data: AiSearchAnswer }>> & {
  options: { requestKey: string }, body: { q: string, hitIds: string[] }
}>
const cancelRequest = vi.fn()
const scopes: ReturnType<typeof effectScope>[] = []

function mount() {
  const scope = effectScope()
  scopes.push(scope)
  const search = scope.run(() => useGlobalSearch())!
  search.open.value = true
  return { scope, search }
}

async function type(search: ReturnType<typeof useGlobalSearch>, query: string, ms = 120) {
  search.searchTerm.value = query
  await nextTick()
  if (ms) await vi.advanceTimersByTimeAsync(ms)
}

async function flush() {
  // Flush transport -> useSearch -> palette continuations without advancing debounce time.
  for (let i = 0; i < 5; i++) await Promise.resolve()
  await nextTick()
}

function resultIds(search: ReturnType<typeof useGlobalSearch>) {
  return search.groups.value.find(group => group.id === 'records-files')?.items?.map(item => item.id) ?? []
}

beforeEach(() => {
  vi.useFakeTimers()
  reads = []; answers = []
  cancelRequest.mockReset()
  menu.mockReturnValue({ links: ref([[{ label: 'Allowed page', to: '/quotations' }]]), close: vi.fn() })
  vi.stubGlobal('ref', ref)
  vi.stubGlobal('computed', computed)
  vi.stubGlobal('watch', watch)
  vi.stubGlobal('onScopeDispose', onScopeDispose)
  vi.stubGlobal('useI18n', () => ({ t: (key: string) => key }))
  vi.stubGlobal('useApi', () => ({
    // Deliberately allow completion after cancellation: a resolved response can still be stale.
    get: vi.fn((_url: string, options: RequestOptions) => {
      const pending = { ...deferred<{ data: SearchHit[] }>(), options }
      reads.push(pending)
      return pending.promise
    }),
    post: vi.fn((_url: string, body: { q: string, hitIds: string[] }, options: { requestKey: string }) => {
      const pending = { ...deferred<{ data: AiSearchAnswer }>(), body, options }
      answers.push(pending)
      return pending.promise
    }),
    cancelRequest,
  }))
})

afterEach(() => {
  for (const scope of scopes.splice(0)) scope.stop()
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('global search request ownership', () => {
  it('debounces rapid typing to one request for the latest trimmed query', async () => {
    const { search } = mount()
    await type(search, 'f', 40)
    await type(search, 'fr', 40)
    await type(search, ' freight ', 119)
    expect(reads).toHaveLength(0)
    await vi.advanceTimersByTimeAsync(1)
    expect(reads).toHaveLength(1)
    expect(reads[0]!.options.query).toEqual({ q: 'freight', mode: 'keyword', limit: 12 })
  })

  it('does not send another query for whitespace-only changes', async () => {
    const { search } = mount()
    await type(search, 'freight')
    reads[0]!.resolve({ data: [hit('current')] }); await flush()
    await type(search, ' freight ')
    expect(reads).toHaveLength(1)
    expect(resultIds(search)).toEqual(['current'])
  })

  it('keeps the newer mode result when an older mode resolves last', async () => {
    const { search } = mount()
    await type(search, 'freight')
    search.setMode('semantic'); await nextTick(); await vi.advanceTimersByTimeAsync(120)
    reads[1]!.resolve({ data: [hit('new')] }); await flush()
    reads[0]!.resolve({ data: [hit('old')] }); await flush()
    expect(resultIds(search)).toEqual(['new'])
  })

  it('invalidates the old request before the replacement debounce fires', async () => {
    const { search } = mount()
    await type(search, 'old')
    await type(search, 'new', 0)
    reads[0]!.resolve({ data: [hit('obsolete')] }); await flush()
    expect(resultIds(search)).toEqual([])
    expect(cancelRequest).toHaveBeenCalledWith(reads[0]!.options.requestKey)
    await vi.advanceTimersByTimeAsync(120)
    expect(reads).toHaveLength(2)
  })

  it('an old completion cannot stop the newer loading indicator', async () => {
    const { search } = mount()
    await type(search, 'old')
    await type(search, 'new')
    reads[0]!.resolve({ data: [] }); await flush()
    expect(search.loading.value).toBe(true)
    reads[1]!.resolve({ data: [hit('new')] }); await flush()
    expect(search.loading.value).toBe(false)
  })

  it('an obsolete rejection cannot clear the current results', async () => {
    const { search } = mount()
    await type(search, 'old')
    await type(search, 'new')
    reads[1]!.resolve({ data: [hit('new')] }); await flush()
    reads[0]!.reject(new Error('cancelled or offline')); await flush()
    expect(resultIds(search)).toEqual(['new'])
  })

  it('clearing immediately resets results/loading and rejects a late completion', async () => {
    const { search } = mount()
    await type(search, 'freight')
    await type(search, '   ', 0)
    expect(search.loading.value).toBe(false)
    expect(resultIds(search)).toEqual([])
    reads[0]!.resolve({ data: [hit('late')] }); await flush()
    expect(resultIds(search)).toEqual([])
    await vi.advanceTimersByTimeAsync(120)
    expect(reads).toHaveLength(1)
  })

  it('clears a pending timer on close and searches the current query on reopen', async () => {
    const { search } = mount()
    await type(search, 'freight', 60)
    search.open.value = false; await nextTick()
    await vi.advanceTimersByTimeAsync(120)
    expect(reads).toHaveLength(0)
    search.open.value = true; await nextTick(); await vi.advanceTimersByTimeAsync(120)
    expect(reads).toHaveLength(1)
  })

  it('does not query while closed or for an empty query', async () => {
    const { search } = mount()
    await type(search, '   ')
    expect(reads).toHaveLength(0)
    search.open.value = false; await nextTick()
    await type(search, 'hidden query')
    expect(reads).toHaveLength(0)
  })

  it('cleans up a pending debounce when its scope unmounts', async () => {
    const { search, scope } = mount()
    await type(search, 'freight', 60)
    scope.stop()
    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(120)
    expect(reads).toHaveLength(0)
  })

  it('cancels an active request and ignores completion after unmount', async () => {
    const { search, scope } = mount()
    await type(search, 'freight')
    scope.stop()
    expect(cancelRequest).toHaveBeenCalledWith(reads[0]!.options.requestKey)
    reads[0]!.resolve({ data: [hit('late')] }); await flush()
    expect(resultIds(search)).toEqual([])
    expect(search.loading.value).toBe(false)
  })

  it('closing cancels an active read and ignores its late completion', async () => {
    const { search } = mount()
    await type(search, 'freight')
    search.open.value = false; await nextTick()
    expect(cancelRequest).toHaveBeenCalledWith(reads[0]!.options.requestKey)
    reads[0]!.resolve({ data: [hit('late')] }); await flush()
    expect(resultIds(search)).toEqual([])
    expect(search.loading.value).toBe(false)
  })

  it('uses separate cancellation keys for separate palette instances', async () => {
    const first = mount(); const second = mount()
    await type(first.search, 'first')
    await type(second.search, 'second')
    expect(reads[0]!.options.requestKey).not.toBe(reads[1]!.options.requestKey)
    cancelRequest.mockClear(); first.scope.stop()
    expect(cancelRequest).not.toHaveBeenCalledWith(reads[1]!.options.requestKey)
  })

  it('a current network failure clears loading and permits another search', async () => {
    const { search } = mount()
    await type(search, 'first')
    reads[0]!.reject(new Error('offline')); await flush()
    expect(search.loading.value).toBe(false)
    expect(resultIds(search)).toEqual([])
    await type(search, 'retry')
    reads[1]!.resolve({ data: [hit('recovered')] }); await flush()
    expect(resultIds(search)).toEqual(['recovered'])
  })

  it('preserves navigation supplied by the permission-filtered menu', () => {
    const { search } = mount()
    expect(search.groups.value.find(group => group.id === 'navigation')?.items).toEqual([
      expect.objectContaining({ to: '/quotations', label: 'Allowed page' }),
    ])
  })
})

describe('search answer ownership', () => {
  it('does not duplicate an answer request and preserves its query/source contract', async () => {
    const { search } = mount()
    await type(search, 'freight')
    reads[0]!.resolve({ data: [hit('source')] }); await flush()
    const first = search.onAskAi()
    await search.onAskAi()
    expect(answers).toHaveLength(1)
    expect(answers[0]!.body).toEqual({ q: 'freight', hitIds: ['source'] })
    answers[0]!.resolve({ data: { answer: 'Answer', citations: [hit('source')] } }); await first
    expect(search.asking.value).toBe(false)
    expect(search.groups.value.find(group => group.id === 'ai-sources')?.items?.[0]?.to).toBe('/quotations/source')
  })

  it('recovers from an answer network failure without leaving a spinner', async () => {
    const { search } = mount()
    await type(search, 'freight')
    reads[0]!.resolve({ data: [] }); await flush()
    const first = search.onAskAi()
    answers[0]!.reject(new Error('offline')); await first
    expect(search.asking.value).toBe(false)
    expect(search.groups.value.some(group => group.id === 'ai-answer')).toBe(false)
    const retry = search.onAskAi()
    expect(answers).toHaveLength(2)
    answers[1]!.resolve({ data: { answer: 'Recovered', citations: [] } }); await retry
    expect(search.groups.value.find(group => group.id === 'ai-answer')?.items?.[0]?.label).toBe('Recovered')
  })

  it('close cancels the answer request and hidden/empty queries cannot ask', async () => {
    const { search } = mount()
    await search.onAskAi()
    expect(answers).toHaveLength(0)
    await type(search, 'freight')
    reads[0]!.resolve({ data: [] }); await flush()
    const answer = search.onAskAi()
    search.open.value = false; await nextTick()
    expect(cancelRequest).toHaveBeenCalledWith(answers[0]!.options.requestKey)
    await search.onAskAi()
    expect(answers).toHaveLength(1)
    answers[0]!.resolve({ data: { answer: 'Late', citations: [] } }); await answer
    expect(search.groups.value.some(group => group.id === 'ai-answer')).toBe(false)
  })

  it('does not publish an answer for a superseded query', async () => {
    const { search } = mount()
    await type(search, 'old')
    reads[0]!.resolve({ data: [hit('old')] }); await flush()
    const answer = search.onAskAi()
    await type(search, 'new', 0)
    expect(search.asking.value).toBe(false)
    answers[0]!.resolve({ data: { answer: 'Obsolete answer', citations: [hit('old')] } })
    await answer
    expect(search.groups.value.some(group => group.id === 'ai-answer')).toBe(false)
  })

  it('does not publish an answer after close or unmount', async () => {
    const { search, scope } = mount()
    await type(search, 'old')
    reads[0]!.resolve({ data: [hit('old')] }); await flush()
    const answer = search.onAskAi()
    search.open.value = false; await nextTick(); scope.stop()
    answers[0]!.resolve({ data: { answer: 'Late answer', citations: [] } }); await answer
    expect(search.asking.value).toBe(false)
    expect(search.groups.value.some(group => group.id === 'ai-answer')).toBe(false)
  })

  it('an older answer cannot reset the newer answer loading state', async () => {
    const { search } = mount()
    await type(search, 'old')
    reads[0]!.resolve({ data: [] }); await flush()
    const oldAnswer = search.onAskAi()
    await type(search, 'new')
    reads[1]!.resolve({ data: [] }); await flush()
    const newAnswer = search.onAskAi()
    expect(answers).toHaveLength(2)
    answers[0]!.resolve({ data: { answer: 'Old', citations: [] } }); await oldAnswer
    expect(search.asking.value).toBe(true)
    answers[1]!.resolve({ data: { answer: 'New', citations: [] } }); await newAnswer
    expect(search.asking.value).toBe(false)
    expect(search.groups.value.find(group => group.id === 'ai-answer')?.items?.[0]?.label).toBe('New')
  })
})
