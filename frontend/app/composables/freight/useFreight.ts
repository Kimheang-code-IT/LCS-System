import { h } from 'vue'
import { UBadge } from '#components'
import type { AppHeaderBadge } from '~/composables/layout/useAppHeader'
import type { FreightAction, FreightField, FreightModule, FreightRelated, FreightSelectOption, FreightTable } from '~/config/freight-modules'
import { getFreightModule } from '~/config/freight-modules'
import { JOB_CHECKLIST_TYPES } from '~/config/freight-options'
import { isMoneyKey } from '~/utils/freight/job-workspace'
import { documentSequenceTypeLabel } from '~/utils/document-sequences'
import {
  formatDate as formatDateValue,
  formatDateTime as formatDateTimeValue,
  formatMoney as formatMoneyValue,
  formatNumber as formatNumberValue,
  getFormatConfig,
} from '~/utils/format/format-service'
import { toFiniteNumber } from '~/utils/format/number'
import { slugify } from '~/utils/text/slug'
import { codeTitle, labeledStatusOptions, shortDay } from '~/utils/freight/format'

export { codeTitle, labeledStatusOptions, shortDay }

export const i18nSlug = slugify

/** Deduplicates dev warnings so a label in a long table only reports once. */
const warnedLabels = new Set<string>()

/**
 * Surfaces labels that ship without an i18n key. Without this a missing key is
 * invisible in English and only shows up as stray English in Khmer or Chinese.
 */
function warnMissingLabel(key: string, fallback: string) {
  if (!import.meta.dev || warnedLabels.has(key)) return
  warnedLabels.add(key)
  console.warn(
    `[i18n] Missing translation key "${key}" for label "${fallback}". `
    + 'Add it to en.json, km.json and zh.json (or give the field a labelKey).',
  )
}

/**
 * Admin-maintained translations that ship with a *record* rather than with the
 * app: component attributes and dynamic-table columns are defined by users in
 * Component Configuration and store their own `labelKm` column in the database.
 * Those are looked up per active locale instead of through the message bundles.
 * Adding a stored `labelZh` later only requires extending `STORED_LABEL_FIELDS`.
 */
const STORED_LABEL_FIELDS: Record<string, keyof FreightField> = {
  km: 'labelKm',
}

/** Returns an admin-supplied label for the active locale, if one exists. */
function storedLabel(field: FreightField, locale: string): string | undefined {
  const stored = field.labelTranslations as Record<string, string> | undefined
  const fromMap = stored?.[locale]?.trim()
  if (fromMap) return fromMap
  const fieldName = STORED_LABEL_FIELDS[locale]
  const value = fieldName ? (field[fieldName] as string | undefined) : undefined
  return value?.trim() || undefined
}

export function useFreightLabel() {
  const { t, te, locale } = useI18n()
  const route = useRoute()

  function tx(key: string, fallback = '') {
    return te(key) ? String(t(key)) : fallback
  }

  /**
   * Resolution order: explicit `labelKey` -> module-scoped key -> generic field
   * key -> an admin-stored translation for the active locale -> the hardcoded
   * English label. Every label shipped in code now has an i18n key in all
   * locales, so a miss means the label was added without one; that warns in dev
   * and renders English instead of leaving a gap in Khmer or Chinese.
   */
  function fieldLabel(field: Pick<FreightField, 'key' | 'label' | 'labelKm' | 'labelKey' | 'labelTranslations'>) {
    if (field.labelKey && te(field.labelKey)) return String(t(field.labelKey))
    const collection = getFreightModule(route.path)?.collection
    if (collection) {
      const scoped = `freight.modules.${collection}.fields.${field.key}`
      if (te(scoped)) return String(t(scoped))
    }
    const generic = `freight.fields.${field.key}`
    if (te(generic)) return String(t(generic))
    const stored = storedLabel(field as FreightField, locale.value)
    if (stored) return stored
    warnMissingLabel(generic, field.label)
    return field.label
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
  // nginx serves generated directories and redirects `/new` -> `/new/`, so strip
  // trailing slashes before matching the create route.
  const path = computed(() => route.path.replace(/\/+$/, '') || '/')
  const module = computed(() => getFreightModule(path.value))
  const isCreate = computed(() => path.value.endsWith('/new') || route.params.id === 'new')
  const recordId = computed(() => isCreate.value ? '' : String(route.params.id || ''))
  return { module, isCreate, recordId, route }
}

function firstOptionValue(option: FreightSelectOption | undefined): string | undefined {
  if (option == null) return undefined
  return typeof option === 'string' ? option : option.value
}

/**
 * Status a newly created record starts in (and is saved as when the form does
 * not send one). Reference/master and operations modules start `Active`;
 * workflow documents keep their first declared status (e.g. `Draft`).
 */
export function defaultStatusForModule(module: FreightModule): string {
  const statusField = module.fields.find(field => field.key === 'status')
  return firstOptionValue(statusField?.options?.[0]) || module.statuses?.[0] || 'Active'
}

export function emptyFreightRecord(module: FreightModule) {
  const record: Record<string, unknown> = { id: '', status: defaultStatusForModule(module) }
  for (const field of module.fields) {
    // The status field is seeded by `defaultStatusForModule`; do not blank it.
    if (field.key === 'status') continue
    if (field.type === 'number') record[field.key] = 0
    else if (field.type === 'multiselect') record[field.key] = []
    else if (field.type === 'date') record[field.key] = new Date().toISOString().slice(0, 10)
    else if (field.type === 'checkbox') {
      record[field.key] = field.options?.[1] ?? 'No'
    }
    else record[field.key] = ''
  }
  for (const table of module.tables || []) {
    record[table.key] = table.presets ? table.presets.map(row => ({ ...row })) : []
  }
  if (module.fields.some(field => field.key === 'currency')) {
    if (!String(record.currency || '').trim()) record.currency = getFormatConfig().currency
    // A new document converts into the company's base currency. A saved document
    // carries its own stored base currency from the payload, so this only seeds
    // the form; the backend remains the authority on what is stored.
    if (!String(record.baseCurrency || '').trim()) record.baseCurrency = getFormatConfig().currency
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
    record.places = []
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
  if (['active', 'paid', 'cleared', 'delivered', 'approved', 'accepted', 'closed', 'completed', 'finished', 'pod received', 'posted', 'issued', 'converted'].some(s => value.includes(s))) return 'success'
  if (['pending', 'processing', 'partial', 'in transit', 'arriving', 'submitted', 'sent', 'in_progress', 'open', 'draft', 'maintenance'].some(s => value.includes(s))) return 'warning'
  if (['inactive', 'overdue', 'missing', 'on hold', 'expired', 'unpaid', 'reversed', 'rejected', 'cancelled', 'superseded'].some(s => value.includes(s))) return 'error'
  return 'neutral'
}

export const asNumber = toFiniteNumber

export function formatMoney(value: unknown, currency?: string) {
  return formatMoneyValue(value, currency)
}

/**
 * Identifiers are labels, never amounts: rendering `entityId` 46 through the
 * number formatter produced "46.00", which reads like a decimal amount.
 */
const IDENTIFIER_KEY = /(?:^id$|Id$|_id$)/

export function formatFreightCell(value: unknown, key: string, currency?: string) {
  if (key === 'documentType') return documentSequenceTypeLabel(value)
  if (IDENTIFIER_KEY.test(key)) {
    const identifier = String(value ?? '').trim()
    if (/^-?\d+$/.test(identifier)) return identifier
  }
  if (isMoneyKey(key)) return formatMoney(value, currency)
  if (/date$/i.test(key) || key === 'date') return formatDateValue(value)
  if (/(?:At|Activity|Timestamp|DateTime)$/i.test(key)) return formatDateTimeValue(value)
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
