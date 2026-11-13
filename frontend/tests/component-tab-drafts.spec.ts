import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, effectScope, nextTick, ref, toValue, watch } from 'vue'
import { useComponentTabs } from '../app/composables/freight/useComponentTabs'

const { bootstrap, saveGroupRows } = vi.hoisted(() => ({ bootstrap: vi.fn(), saveGroupRows: vi.fn() }))
vi.mock('../app/repositories', () => ({ useLcsRepositories: () => ({ componentConfig: { bootstrap, saveGroupRows } }) }))

const config = (value: string) => ({ tabs: [{ code: 'customs', groups: [{
  id: 'g1', attributes: [], rows: [{ id: '1', values: { reference: value } }],
}] }], references: {} })
const settle = async () => { await Promise.resolve(); await nextTick(); await Promise.resolve() }

describe('configured Service Order row persistence', () => {
  const scopes: ReturnType<typeof effectScope>[] = []
  beforeEach(() => {
    bootstrap.mockReset()
    saveGroupRows.mockReset()
    for (const [key, value] of Object.entries({ ref, computed, watch, toValue })) vi.stubGlobal(key, value)
    vi.stubGlobal('useState', (_key: string, init: () => unknown) => ref(init()))
  })
  afterEach(() => { scopes.forEach(scope => scope.stop()); vi.unstubAllGlobals() })
  function state(order = ref('SO-1')) {
    const scope = effectScope()
    scopes.push(scope)
    return { order, tabs: scope.run(() => useComponentTabs(order))! }
  }

  it('keeps edits and row removals during a configuration reload', async () => {
    bootstrap.mockResolvedValue(config('server'))
    const { tabs } = state()
    await settle()
    tabs.setGroupRows('g1', [{ id: '1', reference: 'typed' }])
    await tabs.load(true)
    expect(tabs.rowsForGroup('g1')[0]?.reference).toBe('typed')
    expect(tabs.savedRowsByGroup.value.g1?.[0]?.reference).toBe('server')
    tabs.setGroupRows('g1', [])
    await tabs.load(true)
    expect(tabs.rowsForGroup('g1')).toEqual([])
  })

  it('ignores an older order response arriving last', async () => {
    let finishOld!: (value: unknown) => void
    bootstrap.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    bootstrap.mockResolvedValueOnce(config('new order'))
    const { tabs, order } = state()
    order.value = 'SO-2'
    await settle()
    finishOld(config('old order'))
    await settle()
    expect(tabs.rowsForGroup('g1')[0]?.reference).toBe('new order')
  })

  it('retains newer edits when a save response arrives and records only the persisted baseline', async () => {
    bootstrap.mockResolvedValue(config('server'))
    const { tabs } = state()
    await settle()
    tabs.setGroupRows('g1', [{ id: '1', reference: 'submitted' }])
    let finish!: (value: unknown) => void
    saveGroupRows.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const saving = tabs.saveGroup('g1')
    tabs.setGroupRows('g1', [{ id: '1', reference: 'newer' }])
    finish([{ id: '1', values: { reference: 'submitted' } }])
    await saving
    expect(tabs.rowsForGroup('g1')[0]?.reference).toBe('newer')
    expect(tabs.savedRowsByGroup.value.g1?.[0]?.reference).toBe('submitted')
  })
})
