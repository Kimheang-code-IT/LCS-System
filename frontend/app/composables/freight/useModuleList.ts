import type { Ref } from 'vue'
import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/record'
import type { ModuleListQuery } from '~/repositories/contracts/module'
import { useModuleRepository } from '~/repositories'

export function useModuleList(module: Ref<FreightModule | undefined>) {
  const pending = ref(false)
  const error = ref<unknown>(null)
  const items = ref<FreightRecord[]>([])
  const total = ref(0)
  /** Extra list meta (e.g. server-computed footer aggregates). */
  const meta = ref<Record<string, unknown>>({})

  async function refresh(query: ModuleListQuery = {}) {
    if (!module.value) {
      items.value = []
      total.value = 0
      meta.value = {}
      return
    }
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      const result = await repository.list({ page_size: 200, ...query })
      items.value = result.items
      total.value = result.meta.total
      meta.value = result.meta as unknown as Record<string, unknown>
    }
    catch (err) {
      error.value = err
      items.value = []
      total.value = 0
      meta.value = {}
    }
    finally {
      pending.value = false
    }
  }

  return {
    pending,
    error,
    items,
    total,
    meta,
    refresh,
  }
}
