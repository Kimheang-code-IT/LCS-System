import type { ActivityEvent, AttachmentMeta, EntityComment, PersonSummary } from '~/types/docetra/common'
import type { FreightRecord } from '~/types/freight/record'
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
  const commentBody = ref('')
  const submittingComment = ref(false)

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

  const comments = computed<EntityComment[]>(() => {
    const rows = options.model.value.comments
    return Array.isArray(rows) ? rows as EntityComment[] : []
  })

  const attachments = computed<AttachmentMeta[]>(() => {
    const rows = options.model.value.attachments
    return Array.isArray(rows) ? rows as AttachmentMeta[] : []
  })

  const tags = computed<string[]>(() => {
    const rows = options.model.value.tags
    if (Array.isArray(rows)) return rows.map(String)
    const text = String(options.model.value.tags || '').trim()
    return text ? text.split(',').map(part => part.trim()).filter(Boolean) : []
  })

  const activity = computed<ActivityEvent[]>(() => {
    const entityId = String(options.model.value.id || '')
    const entityType = options.module.value?.collection || 'record'
    const fromRecord = Array.isArray(options.model.value.activity)
      ? (options.model.value.activity as Array<Record<string, unknown>>).map((item, index) => ({
          id: String(item.id || `act-${index}`),
          entityType,
          entityId,
          action: String(item.action || 'updated'),
          summary: String(item.action || item.summary || 'updated'),
          occurredAt: String(item.at || item.occurredAt || options.model.value.updatedAt || new Date().toISOString()),
          actor: { id: 'user', name: String(item.user || currentUser.value.name) } as PersonSummary,
        }))
      : []
    const title = options.module.value
      ? String(options.model.value[options.module.value.titleField] || '')
      : ''
    const recordNos = new Set([
      title,
      entityId,
      String(options.model.value.jobNo || ''),
    ].filter(Boolean))
    const fromAudit = store.list('auditLogs')
      .filter(row => recordNos.has(String(row.recordNo || row.entity || '')))
      .map(row => ({
        id: String(row.id),
        entityType,
        entityId,
        action: String(row.action || 'updated'),
        summary: String(row.action || 'updated'),
        occurredAt: String(row.occurredAt || row.createdAt || new Date().toISOString()),
        actor: { id: 'user', name: String(row.user || currentUser.value.name) } as PersonSummary,
        metadata: {
          result: row.result ? String(row.result) : undefined,
          remark: row.remark ? String(row.remark) : undefined,
          module: row.module ? String(row.module) : undefined,
        },
      }))
    return [...fromRecord, ...fromAudit].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt))
  })

  const metaOwner = computed<PersonSummary>(() => ({
    id: 'owner',
    name: String(options.model.value.createdBy || options.model.value.assignedStaff || currentUser.value.name),
  }))

  const metaAssignee = computed<PersonSummary | null>(() => {
    const raw = options.model.value.assignee
    if (raw && typeof raw === 'object' && 'name' in (raw as object)) return raw as PersonSummary
    const name = String(options.model.value.assignedStaff || options.model.value.contact || '')
    return name ? { id: 'assignee', name } : null
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

  async function submitComment() {
    const body = commentBody.value.trim()
    if (!body || options.isCreate.value) return
    submittingComment.value = true
    try {
      const next: EntityComment = {
        id: `cmt-${Date.now()}`,
        entityType: options.module.value?.collection || 'record',
        entityId: String(options.model.value.id || ''),
        body,
        author: currentUser.value,
        createdAt: new Date().toISOString(),
      }
      patch({ comments: [...comments.value, next] })
      commentBody.value = ''
      if (options.module.value && options.model.value.id) {
        store.save(options.module.value.collection, options.model.value)
      }
    }
    finally {
      submittingComment.value = false
    }
  }

  async function updateComment(id: string, body: string) {
    patch({
      comments: comments.value.map(item => item.id === id
        ? { ...item, body, editedAt: new Date().toISOString() }
        : item),
    })
    if (options.module.value && options.model.value.id) {
      store.save(options.module.value.collection, options.model.value)
    }
  }

  async function deleteComment(id: string) {
    patch({ comments: comments.value.filter(item => item.id !== id) })
    if (options.module.value && options.model.value.id) {
      store.save(options.module.value.collection, options.model.value)
    }
  }

  function emptyFieldValue() {
    return undefined as unknown
  }

  function noopSetField() {}

  return {
    t,
    commentBody,
    submittingComment,
    currentUser,
    listTo,
    canNavigatePrevious,
    canNavigateNext,
    navigatePrevious,
    navigateNext,
    comments,
    attachments,
    tags,
    activity,
    metaOwner,
    metaAssignee,
    setChromeField,
    submitComment,
    updateComment,
    deleteComment,
    emptyFieldValue,
    noopSetField,
  }
}
