import { freightModules } from '~/config/freight-modules'
import { referenceOptionSource } from '~/utils/freight/reference-options'

export type ReferenceCreateTarget = {
  /** Master Data module path, e.g. `/master-data/container-types`. */
  path: string
  /** Field stored as the select value on the created record. */
  valueField: string
}

/**
 * Resolve the Master Data create page for a reference-backed select field.
 * Returns null for static selects, missing modules or non-creatable modules.
 */
export function referenceCreateTarget(key: string): ReferenceCreateTarget | null {
  const source = referenceOptionSource(key)
  if (!source) return null
  const module = freightModules.find(item =>
    item.collection === source.collection
    && item.group === 'master'
    && item.canCreate !== false,
  )
  if (!module) return null
  return {
    path: `${module.path.replace(/\/$/, '')}/new`,
    valueField: source.valueField || 'code',
  }
}

/** One form field of the inline Add New dialog. Only simple text fields. */
export type ReferenceCreateField = {
  key: 'code' | 'name'
  /** Reuses the shared `freight.fields.*` labels. */
  labelKey: string
  required: boolean
  maxLength: number
}

export type ReferenceCreateDialog = {
  collection: string
  /** The select value stored back into the quotation field. */
  valueField: string
  entityKey: string
  fields: ReferenceCreateField[]
}

/**
 * Master collections whose backend creation spec needs only a code and a name.
 * These open the small in-form Add New dialog instead of navigating away, so an
 * unsaved quotation is never left behind. Complex masters (business parties,
 * document types with their behaviour/module requirements) keep the dedicated
 * Master Data page flow.
 */
const REFERENCE_CREATE_DIALOGS: Record<string, ReferenceCreateDialog> = {
  feeTypes: dialog('feeTypes', 'code'),
  containerTypes: dialog('containerTypes', 'code'),
  partyRoles: dialog('partyRoles', 'id'),
  placeRoles: dialog('placeRoles', 'id'),
  tradeDirections: dialog('tradeDirections', 'name'),
  transportTypes: dialog('transportTypes', 'name'),
  capacityUnits: dialog('capacityUnits', 'code'),
  currencies: dialog('currencies', 'code'),
}

function dialog(collection: string, valueField: string): ReferenceCreateDialog {
  return {
    collection,
    valueField,
    entityKey: `freight.pages.${collection.charAt(0).toLowerCase()}${collection.slice(1)}`,
    fields: [
      { key: 'code', labelKey: 'freight.fields.code', required: true, maxLength: 64 },
      { key: 'name', labelKey: 'freight.fields.name', required: true, maxLength: 255 },
    ],
  }
}

/**
 * The simple-reference dialog config for a select field, or null when the
 * field's master needs its full page (or is not creatable at all).
 */
export function referenceCreateDialog(key: string): ReferenceCreateDialog | null {
  const source = referenceOptionSource(key)
  if (!source) return null
  const config = REFERENCE_CREATE_DIALOGS[source.collection]
  if (!config) return null
  const module = freightModules.find(item => item.collection === source.collection && item.group === 'master')
  if (!module || module.canCreate === false) return null
  return { ...config, valueField: source.valueField === 'id' ? 'id' : config.valueField }
}

/** The module a reference select creates rows in (for the API + titles). */
export function referenceModuleFor(key: string) {
  const source = referenceOptionSource(key)
  if (!source) return null
  return freightModules.find(item => item.collection === source.collection && item.group === 'master') ?? null
}

/**
 * The logged-in user may create rows in this reference's master collection.
 * Mirrors the backend `_collection_guard`'s coarse reference rule (`master.
 * reference.manage` or `configuration.manage`); collections with their own
 * page prefix are also allowed through that page's create code when it is in
 * the caller's page codes. The backend stays authoritative either way.
 */
export function canCreateReference(
  sourcePermissions: readonly string[] | null | undefined,
  pageAccess: readonly string[] | null | undefined,
  key: string,
): boolean {
  if (pageAccess?.includes('ALL_PAGES')) return true
  if (sourcePermissions?.includes('master.reference.manage') || sourcePermissions?.includes('configuration.manage')) {
    return true
  }
  const module = referenceModuleFor(key)
  if (!module?.permission) return false
  const createCode = `${module.permission.slice(0, -'.view'.length)}.create`
  return pageAccess?.includes(createCode) === true
}