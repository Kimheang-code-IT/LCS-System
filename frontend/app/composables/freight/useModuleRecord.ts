import type { Ref } from 'vue'
import type { FreightModule } from '~/config/freight-modules'
import { useModuleRepository } from '~/repositories'

export function useModuleRecord(module: Ref<FreightModule | undefined>) {
  const pending = ref(false)
  const error = ref<unknown>(null)

  async function get(id: string) {
    if (!module.value) throw new Error('Module is not available')
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      return await repository.get(id)
    }
    catch (err) {
      error.value = err
      throw err
    }
    finally {
      pending.value = false
    }
  }

  async function create(input: Record<string, unknown>) {
    if (!module.value) throw new Error('Module is not available')
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      const record = await repository.create(input)
      useFreightStore().reload()
      return record
    }
    catch (err) {
      error.value = err
      throw err
    }
    finally {
      pending.value = false
    }
  }

  async function update(id: string, input: Record<string, unknown>) {
    if (!module.value) throw new Error('Module is not available')
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      const record = await repository.update(id, input)
      useFreightStore().reload()
      return record
    }
    catch (err) {
      error.value = err
      throw err
    }
    finally {
      pending.value = false
    }
  }

  async function remove(ids: string[]) {
    if (!module.value) throw new Error('Module is not available')
    pending.value = true
    error.value = null
    try {
      const repository = useModuleRepository(module.value)
      await repository.remove(ids)
      useFreightStore().reload()
    }
    catch (err) {
      error.value = err
      throw err
    }
    finally {
      pending.value = false
    }
  }

  return {
    pending,
    error,
    get,
    create,
    update,
    remove,
  }
}
