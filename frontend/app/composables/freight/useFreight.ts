import { h } from 'vue'
import { UBadge } from '#components'
import type { AppHeaderBadge } from '~/composables/layout/useAppHeader'
import type { FreightAction, FreightField, FreightModule, FreightRelated, FreightTable } from '~/config/freight-modules'
import { getFreightModule } from '~/config/freight-modules'
import { JOB_CHECKLIST_TYPES } from '~/config/freight-options'
import { defaultJobRoutePlaces, isMoneyKey } from '~/utils/freight/job-workspace'
import { documentSequenceTypeLabel } from '~/utils/document-sequences'
import { formatMoney as formatMoneyValue, formatNumber as formatNumberValue } from '~/utils/format/format-service'
import { codeTitle, labeledStatusOptions, shortDay } from '~/utils/freight/format'

export { codeTitle, labeledStatusOptions, shortDay }

export function i18nSlug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'general'
}

export function useFreightLabel() {
  const { t, te, locale } = useI18n()
  const route = useRoute()
  const km = computed(() => locale.value === 'km')

  function tx(key: string, fallback = '') {
    return te(key) ? String(t(key)) : fallback
  }

  function fieldLabel(field: Pick<FreightField, 'key' | 'label' | 'labelKm' | 'labelKey'>) {
    if (field.labelKey && te(field.labelKey)) return String(t(field.labelKey))
    const collection = getFreightModule(route.path)?.collection
    if (collection) {
      const scoped = `freight.modules.${collection}.fields.${field.key}`
      if (te(scoped)) return String(t(scoped))
    }
    const generic = `freight.fields.${field.key}`
    if (te(generic)) return String(t(generic))
    return km.value && field.labelKm ? field.labelKm : field.label
  }

  function moduleTitle(module: FreightModule) {
    if (module.titleKey && te(module.titleKey)) return String(t(module.titleKey))
    return tx(`freight.modules.${module.collection}.title`, module.title)
  }

  function moduleSingular(module: FreightModule) {
    return tx(`freight.modules.${module.collection}.singular`, module.singular)
  }

  function sectionTitle(field: Pick<FreightField, 'section'>) {
    const title = field.section || ''
    return tx(`freight.sections.${i18nSlug(title)}`, title)
  }

  function groupTitle(title: string) {
    return tx(`freight.sections.${i18nSlug(title)}`, title)
  }

  function tableTitle(table: Pick<FreightTable, 'key' | 'title'>) {
    return tx(`freight.tables.${table.key}`, table.title)
  }

  function actionLabel(action: Pick<FreightAction, 'key' | 'label'>) {
    return tx(`freight.moduleActions.${action.key}`, action.label)
  }

  function relatedTitle(group: Pick<FreightRelated, 'title'>) {
    return tx(`freight.related.${i18nSlug(group.title)}`, group.title)
  }

  return {
    km,
    tx,
    fieldLabel,
    moduleTitle,
    moduleSingular,
    sectionTitle,
    groupTitle,
    tableTitle,
    actionLabel,
    relatedTitle,
  }
}

export function useFreightRouteModule() {
  const route = useRoute()
  const module = computed(() => getFreightModule(route.path))
  const isCreate = computed(() => route.path.endsWith('/new') || route.params.id === 'new')
  const recordId = computed(() => isCreate.value ? '' : String(route.params.id || ''))
  return { module, isCreate, recordId, route }
}

export function emptyFreightRecord(module: FreightModule) {
  const record: Record<string, unknown> = { id: '', status: module.statuses?.[0] || 'Active' }
  for (const field of module.fields) {
    if (field.type === 'number') record[field.key] = 0
    else if (field.type === 'multiselect') record[field.key] = []
    else if (field.type === 'date') record[field.key] = new Date().toISOString().slice(0, 10)
    else if (field.type === 'checkbox') {
      record[field.key] = field.key === 'status'
        ? (field.options?.[0] ?? 'Active')
        : (field.options?.[1] ?? 'No')
    }
    else record[field.key] = ''
  }
  for (const table of module.tables || []) {
    record[table.key] = table.presets ? table.presets.map(row => ({ ...row })) : []
  }
  if (module.collection === 'roles') {
    record.permissionRows = []
    record.userCount = 0
    record.permissionCount = 0
  }
  if (module.collection === 'documentSequences') {
    record.year = new Date().getFullYear()
    record.lastValue = 0
    record.paddingLength = 6
    record.status = 'ACTIVE'
  }
  if (module.kind === 'job') {
    record.checklist = JOB_CHECKLIST_TYPES.map(type => ({ type, required: true, status: 'Missing', remark: '' }))
    record.activity = []
    record.places = defaultJobRoutePlaces()
    record.containerRequirements = []
    record.actualContainers = []
    record.containerPayments = []
    record.attachments = []
  }
  if (module.kind === 'job-charges' || module.collection === 'jobCharges') {
    record.feeLines = Array.isArray(record.feeLines) ? record.feeLines : []
    record.status = 'Draft'
  }
  return record
}

export function groupedFields(module: FreightModule) {
  const groups: Array<{ title: string, titleKm?: string, fields: FreightField[] }> = []
  for (const field of module.fields) {
    const title = field.section || 'General'
    const current = groups.find(group => group.title === title)
    if (current) current.fields.push(field)
    else groups.push({ title, titleKm: field.sectionKm, fields: [field] })
  }
  return groups
}

export function statusColor(status: string): AppHeaderBadge['color'] {
  const value = status.toLowerCase()
  if (['active', 'paid', 'cleared', 'delivered', 'approved', 'accepted', 'closed', 'completed', 'pod received', 'posted', 'issued', 'converted'].some(s => value.includes(s))) return 'success'
  if (['pending', 'processing', 'partial', 'in transit', 'arriving', 'submitted', 'sent', 'in_progress', 'open', 'draft'].some(s => value.includes(s))) return 'warning'
  if (['inactive', 'overdue', 'missing', 'on hold', 'expired', 'unpaid', 'reversed', 'rejected', 'cancelled', 'superseded'].some(s => value.includes(s))) return 'error'
  return 'neutral'
}

export function asNumber(value: unknown) {
  const n = Number(value || 0)
  return Number.isFinite(n) ? n : 0
}

export function formatMoney(value: unknown, currency?: string) {
  return formatMoneyValue(value, currency)
}

export function formatFreightCell(value: unknown, key: string, currency?: string) {
  if (key === 'documentType') return documentSequenceTypeLabel(value)
  if (isMoneyKey(key)) return formatMoney(value, currency)
  if (typeof value === 'number') return formatNumberValue(value)
  if (Array.isArray(value)) return value.map(item => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}

/** Compact status badge used by list/table cells. Color comes from `statusColor`. */
export function freightStatusBadge(value: unknown, key = 'status', label?: string) {
  const raw = String(value ?? '')
  return h(UBadge, {
    color: statusColor(raw),
    variant: 'subtle',
    size: 'sm',
  }, () => label ?? formatFreightCell(value, key))
}
