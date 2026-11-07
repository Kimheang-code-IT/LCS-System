import type { AttachmentMeta, PersonSummary } from '~/types/common'
import type { FreightRecord } from '~/types/record'
import type { FreightModule } from '~/config/freight-modules'

export function useFreightRecordChrome(options: {
  module: ComputedRef<FreightModule | undefined>
  isCreate: ComputedRef<boolean>
  recordId: ComputedRef<string>
  model: Ref<FreightRecord>
}) {
  const store = useFreightStore()
  const auth = useAuthStore()
  const { t } = useI18n()

  const currentUser = computed<PersonSummary>(() => ({
    id: String(auth.user?.id || 'me'),
    name: auth.user?.name || 'You',
    email: auth.user?.email,
  }))

  const listTo = computed(() => options.module.value?.path || '/')

  const siblingIds = computed(() => {
    if (!options.module.value) return []
    return store.list(options.module.value.collection).map(row => String(row.id))
  })

  const siblingIndex = computed(() => siblingIds.value.indexOf(options.recordId.value))
  const canNavigatePrevious = computed(() => siblingIndex.value > 0)
  const canNavigateNext = computed(() => siblingIndex.value >= 0 && siblingIndex.value < siblingIds.value.length - 1)

  async function navigatePrevious() {
    const id = siblingIds.value[siblingIndex.value - 1]
    if (id && options.module.value) await navigateTo(`${options.module.value.path}/${id}`)
  }

  async function navigateNext() {
    const id = siblingIds.value[siblingIndex.value + 1]
    if (id && options.module.value) await navigateTo(`${options.module.value.path}/${id}`)
  }

  const attachments = computed<AttachmentMeta[]>(() => {
    const rows = options.model.value.attachments
    return Array.isArray(rows) ? rows as AttachmentMeta[] : []
  })

  function patch(partial: Record<string, unknown>) {
    options.model.value = { ...options.model.value, ...partial }
  }

  function setChromeField(key: string, value: unknown) {
    if (key === 'assignee') {
      const person = (Array.isArray(value) ? value[0] : value) as PersonSummary | null
      patch({
        assignee: person || null,
        assignedStaff: person?.name || '',
      })
      return
    }
    patch({ [key]: value })
  }

  function emptyFieldValue() {
    return undefined as unknown
  }

  function noopSetField() {}

  return {
    t,
    currentUser,
    listTo,
    canNavigatePrevious,
    canNavigateNext,
    navigatePrevious,
    navigateNext,
    attachments,
    setChromeField,
    emptyFieldValue,
    noopSetField,
  }
}
