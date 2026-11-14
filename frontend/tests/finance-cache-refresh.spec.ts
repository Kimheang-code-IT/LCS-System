import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }

describe('targeted financial cache invalidation', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('ref', ref)
    vi.stubGlobal('defineStore', (_id: string, setup: () => unknown) => setup)
    vi.stubGlobal('useI18n', () => ({ t: (key: string) => key }))
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('queues another read when a mutation occurs during an already-queued refresh', async () => {
    const requests: Array<(response: unknown) => void> = []
    const get = vi.fn(() => new Promise(resolve => { requests.push(resolve) }))
    vi.stubGlobal('useApi', () => ({ get }))
    const { useFreightStore } = await import('../app/stores/freight')
    const store = useFreightStore()
    const initial = store.ensure('debitNotes')
    store.reload(['debitNotes'])
    requests[0]!({ data: [{ id: '1', status: 'Draft' }] })
    await initial
    await settle()
    expect(get).toHaveBeenCalledTimes(2)
    store.reload(['debitNotes'])
    requests[1]!({ data: [{ id: '1', status: 'Posted', outstanding: 100 }] })
    await settle()
    expect(get).toHaveBeenCalledTimes(3)
    requests[2]!({ data: [{ id: '1', status: 'Posted', outstanding: 25 }] })
    await settle()
    expect(store.list('debitNotes')[0]?.outstanding).toBe(25)
    expect(get).toHaveBeenCalledTimes(3)
  })

  it('keeps unrelated loaded reference collections cached', async () => {
    const get = vi.fn().mockResolvedValue({ data: [] })
    vi.stubGlobal('useApi', () => ({ get }))
    const { useFreightStore } = await import('../app/stores/freight')
    const store = useFreightStore()
    expect(store.financialRevision.value).toBe(0)
    await store.ensure('businessParties')
    store.reload(['businessParties'])
    expect(store.financialRevision.value).toBe(0)
    await settle()
    get.mockClear()
    store.reload(['debitNotes'])
    expect(store.financialRevision.value).toBe(1)
    await settle()
    store.list('businessParties')
    expect(get).toHaveBeenCalledTimes(1)
  })
})
