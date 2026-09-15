import { freightModules, type FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import { sessionFromUser } from '~/utils/lcs/session-from-user'
import { unwrapApiData } from '~/repositories/http/response'
import { buildDashboardSummary, type DashboardFilters, type DashboardSummary } from '~/utils/lcs/dashboard'
import { matchesFilter, parseFilterQuery } from '~/utils/filter/values'
import { normalizeAuditLog } from '~/utils/freight/audit-logs'
import {
  JOB_DERIVED_COLLECTIONS,
  endpointFor,
  normalizeItems,
  stripRecord,
} from '~/utils/api/freight-remote'

function newId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function emptyDashboard(): DashboardSummary {
  return {
    generatedAt: new Date().toISOString(),
    summary: {
      openOrders: 0,
      inProgressOrders: 0,
      onHoldOrders: 0,
      awaitingClosure: 0,
      receivables: 0,
      overdueReceivableCount: 0,
      payables: 0,
      cashBankBalance: 0,
      revenue: 0,
      expense: 0,
    },
    charts: { revenueExpense: [], ordersByStatus: [], receivablesAging: [], payablesAging: [] },
    options: { customers: [] },
  }
}

export const useFreightStore = defineStore('freight', () => {
  const revision = ref(0)
  const hydrated = ref(false)
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  /** The store is always backed by the real `/api/v1` API. */
  const isRemote = computed(() => true)

  const remoteCache = ref<Record<string, FreightRecord[]>>({})
  const remoteLoaded = ref<Record<string, boolean>>({})
  const inflight = new Map<string, Promise<void>>()
  const dashboardEntries = new Map<string, DashboardSummary>()

  const tenant = useTenantStore()
  watch(() => [tenant.organizationId, tenant.branchId, tenant.assignedBranches.length], () => {
    revision.value += 1
  })

  function bumpRevision() {
    revision.value += 1
  }

  function hydrate() {
    if (hydrated.value) return
    hydrated.value = true
  }

  function reload() {
    const loaded = Object.keys(remoteLoaded.value).filter(key => remoteLoaded.value[key])
    remoteLoaded.value = {}
    void Promise.all(loaded.map(collection => ensureRemote(collection, true)))
    bumpRevision()
  }

  // --- Remote loading -------------------------------------------------------
  function setCache(collection: string, rows: FreightRecord[]) {
    remoteCache.value = { ...remoteCache.value, [collection]: rows }
    remoteLoaded.value = { ...remoteLoaded.value, [collection]: true }
    bumpRevision()
  }

  function deriveJobCollections(jobs: FreightRecord[]) {
    const requirements: FreightRecord[] = []
    const actuals: FreightRecord[] = []
    for (const job of jobs) {
      const jobNo = String(job.jobNo || job.serviceOrderNo || '')
      const serviceOrderId = String(job.id || '')
      for (const row of Array.isArray(job.containerRequirements) ? job.containerRequirements as FreightRecord[] : []) {
        requirements.push({ ...row, id: String(row.id || newId('cr')), jobNo, serviceOrderId })
      }
      for (const row of Array.isArray(job.actualContainers) ? job.actualContainers as FreightRecord[] : []) {
        actuals.push({ ...row, id: String(row.id || newId('ac')), jobNo, serviceOrderId })
      }
    }
    remoteCache.value = {
      ...remoteCache.value,
      containerRequirements: requirements,
      actualContainers: actuals,
      serviceComponents: remoteCache.value.serviceComponents || [],
    }
    remoteLoaded.value = {
      ...remoteLoaded.value,
      containerRequirements: true,
      actualContainers: true,
      serviceComponents: true,
    }
  }

  async function ensureRemote(collection: string, force = false): Promise<void> {
    // Data is fetched on the client where the bearer token / session is available.
    if (import.meta.server) return
    if (!collection) return
    if (!force && remoteLoaded.value[collection]) return
    if (inflight.has(collection)) return inflight.get(collection)

    if (JOB_DERIVED_COLLECTIONS.includes(collection)) {
      const promise = ensureRemote('jobs', force).then(() => {
        deriveJobCollections(remoteCache.value.jobs || [])
        bumpRevision()
      })
      inflight.set(collection, promise)
      try {
        await promise
      }
      finally {
        inflight.delete(collection)
      }
      return
    }

    const endpoint = endpointFor(collection)
    if (!endpoint) {
      setCache(collection, [])
      return
    }

    const promise = (async () => {
      try {
        const response = await api.get(endpoint.path, {
          query: { page_size: 200, ...(endpoint.query || {}) },
          suppressErrorToast: true,
        })
        const items = normalizeItems(unwrapApiData(response))
        setCache(collection, items)
        if (collection === 'jobs') deriveJobCollections(items)
      }
      catch {
        setCache(collection, [])
      }
    })()
    inflight.set(collection, promise)
    try {
      await promise
    }
    finally {
      inflight.delete(collection)
    }
  }

  function upsertRemoteCache(collection: string, record: FreightRecord) {
    if (!record || typeof record !== 'object') return
    const rows = remoteCache.value[collection] || []
    const id = String(record.id ?? '')
    const index = rows.findIndex(row => String(row.id) === id)
    const next = index >= 0 ? rows.map((row, i) => (i === index ? record : row)) : [record, ...rows]
    remoteCache.value = { ...remoteCache.value, [collection]: next }
    if (collection === 'jobs') deriveJobCollections(remoteCache.value.jobs || [])
    bumpRevision()
  }

  function removeFromRemoteCache(collection: string, ids: string[]) {
    const rows = remoteCache.value[collection] || []
    remoteCache.value = { ...remoteCache.value, [collection]: rows.filter(row => !ids.includes(String(row.id))) }
    bumpRevision()
  }

  async function persistRemote(collection: string, record: FreightRecord) {
    const endpoint = endpointFor(collection)
    if (!endpoint || endpoint.readOnly) return
    try {
      const id = String(record.id ?? '')
      const body = stripRecord(record)
      let response: unknown
      if (endpoint.upsertViaPost) response = await api.post(endpoint.path, body)
      else if (id && endpoint.itemPath) response = await api.put(endpoint.itemPath(id), body)
      else response = await api.post(endpoint.path, body)
      const saved = unwrapApiData(response) as FreightRecord | undefined
      if (saved && typeof saved === 'object' && !Array.isArray(saved)) upsertRemoteCache(collection, saved)
    }
    catch {
      toast.add({ title: t('api.somethingWentWrong'), color: 'error' })
    }
  }

  const collections = computed(() => {
    void revision.value
    return remoteCache.value
  })

  function moduleByPath(path: string) {
    return freightModules.find(module => module.path === path)
  }

  function scoped(collection: string): FreightRecord[] {
    void ensureRemote(collection)
    return remoteCache.value[collection] || []
  }

  function list(collection: string): FreightRecord[] {
    return scoped(collection)
  }

  function get(collection: string, id: string) {
    return list(collection).find(row => String(row.id) === String(id)) || null
  }

  function getJobByNo(jobNo: string) {
    const value = jobNo.trim()
    if (!value) return null
    return list('jobs').find(row => String(row.jobNo || '') === value) || null
  }

  function save(collection: string, record: FreightRecord): FreightRecord {
    const next = { ...record, updatedAt: new Date().toISOString() } as FreightRecord
    upsertRemoteCache(collection, next)
    void persistRemote(collection, next)
    return next
  }

  async function create(collection: string, data: Record<string, unknown>, prefix = 'rec'): Promise<FreightRecord> {
    const endpoint = endpointFor(collection)
    const record = stripRecord(data) as FreightRecord
    if (endpoint && !endpoint.readOnly) {
      try {
        const response = await api.post(endpoint.path, record)
        const saved = unwrapApiData(response) as FreightRecord | undefined
        if (saved && typeof saved === 'object') {
          upsertRemoteCache(collection, saved)
          return saved
        }
      }
      catch {
        toast.add({ title: t('api.somethingWentWrong'), color: 'error' })
      }
    }
    const optimistic = { ...record, id: newId(prefix) } as FreightRecord
    upsertRemoteCache(collection, optimistic)
    return optimistic
  }

  function remove(collection: string, ids: string[]) {
    removeFromRemoteCache(collection, ids)
    const endpoint = endpointFor(collection)
    if (endpoint && !endpoint.readOnly) {
      void (async () => {
        try {
          if (endpoint.bulkDelete) await api.delete(endpoint.path, { body: { ids } })
          else if (endpoint.itemPath) {
            for (const id of ids) await api.delete(endpoint.itemPath(id))
          }
        }
        catch {
          toast.add({ title: t('api.somethingWentWrong'), color: 'error' })
        }
      })()
    }
  }

  function addAudit(_action: string, _module: string, _recordNo: string, _remark = '') {
    // Auditing is handled server-side.
  }

  function query(module: FreightModule, options: {
    q?: string
    filters?: Record<string, string | string[]>
    page?: number
    limit?: number
    paginate?: boolean
    dateField?: string
    dateFrom?: string
    dateTo?: string
    sortKey?: string
    sortDir?: 'asc' | 'desc'
  }) {
    const q = (options.q || '').trim().toLowerCase()
    const filters = options.filters || {}
    let rows = list(module.collection)
    if (module.collection === 'auditLogs') rows = rows.map(normalizeAuditLog)
    if (q) {
      rows = rows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(q)))
    }
    for (const [key, value] of Object.entries(filters)) {
      if (!parseFilterQuery(value).length) continue
      rows = rows.filter(row => matchesFilter(row[key], value))
    }
    const dateField = options.dateField
    const dateFrom = (options.dateFrom || '').slice(0, 10)
    const dateTo = (options.dateTo || '').slice(0, 10)
    if (dateField && (dateFrom || dateTo)) {
      rows = rows.filter((row) => {
        const day = String(row[dateField] ?? '').slice(0, 10)
        if (!day) return false
        if (dateFrom && day < dateFrom) return false
        if (dateTo && day > dateTo) return false
        return true
      })
    }
    if (options.sortKey && options.sortDir) {
      const dir = options.sortDir === 'desc' ? -1 : 1
      const sortKey = options.sortKey
      rows = [...rows].sort((a, b) => String(a[sortKey] ?? '').localeCompare(String(b[sortKey] ?? ''), undefined, { numeric: true }) * dir)
    }
    const page = options.page || 1
    const limit = options.limit || 10
    const start = (page - 1) * limit
    return {
      rows: options.paginate === false ? rows : rows.slice(start, start + limit),
      total: rows.length,
      all: rows,
    }
  }

  function related(module: FreightModule, record: FreightRecord) {
    return (module.related || []).map((item) => {
      const target = moduleByPath(item.path)
      const rows = target ? list(target.collection).filter(row => String(row[item.foreignKey] ?? '') === String(record[item.localKey] ?? '')) : []
      return { ...item, rows, module: target }
    })
  }

  const DASHBOARD_COLLECTIONS = [
    'jobs',
    'debitNotes',
    'customerPayments',
    'supplierCosts',
    'supplierPayments',
    'journals',
    'chartOfAccounts',
    'financialAccounts',
  ]

  function dashboardSummary(filters: DashboardFilters = {}): DashboardSummary {
    const key = JSON.stringify(filters)
    let entry = dashboardEntries.get(key)
    if (!entry) {
      entry = emptyDashboard()
      dashboardEntries.set(key, entry)
    }
    void Promise.all(DASHBOARD_COLLECTIONS.map(collection => ensureRemote(collection))).then(() => {
      const next = buildDashboardSummary(remoteCache.value, useTenantSession(), filters)
      Object.assign(entry as object, next)
      bumpRevision()
    })
    return entry
  }

  return {
    isRemote,
    collections,
    hydrate,
    reload,
    list,
    get,
    getJobByNo,
    save,
    create,
    remove,
    addAudit,
    query,
    related,
    dashboardSummary,
  }
})

function useTenantSession() {
  const auth = useAuthStore()
  const tenant = useTenantStore()
  return sessionFromUser(auth.user, tenant.organizationId, tenant.branchId)
}
