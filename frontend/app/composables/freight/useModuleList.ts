import type { Ref } from 'vue'
import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import type { ModuleListQuery } from '~/repositories/contracts/module'
import { useModuleRepository } from '~/repositories'

export function useModuleList(module: Ref<FreightModule | undefined>) {
  const pending = ref(false)
  const error = ref<unknown>(null)
  const items = ref<FreightRecord[]>([])
  const total = ref(0)

  async function refresh(query: ModuleListQuery = {}) {
    if (!module.value) {
      items.value = []
      total.value = 0
      return
    }
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      const result = await repository.list(query)
      items.value = result.items
      total.value = result.meta.total
    }
    catch (err) {
      error.value = err
      items.value = []
      total.value = 0
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
    refresh,
  }
}
