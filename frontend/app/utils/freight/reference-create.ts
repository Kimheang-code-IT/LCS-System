import type { FreightModule } from '~/config/freight-modules'
import { freightModules } from '~/config/freight-modules'
import { referenceOptionSource } from '~/utils/freight/reference-options'

/**
 * The Master Data module that creates rows for a reference-backed select field,
 * or null when the field is not referenced from a creatable module.
 *
 * Every module that can create records already declares its form fields, so the
 * Quick Entry modal renders that same declaration instead of a per-master copy.
 */
export function referenceCreateModule(key: string): FreightModule | null {
  const source = referenceOptionSource(key)
  if (!source) return null
  const module = freightModules.find(item =>
    item.collection === source.collection
    && item.canCreate !== false
    && !item.readOnly,
  )
  return module ?? null
}

/** The module a reference select creates rows in (for permissions + titles). */
export function referenceModuleFor(key: string): FreightModule | null {
  const source = referenceOptionSource(key)
  if (!source) return null
  return freightModules.find(item => item.collection === source.collection) ?? null
}

/** The record field stored as the select value (falls back to the label side). */
export function referenceCreateValueField(key: string): string {
  return referenceOptionSource(key)?.valueField || 'code'
}

/**
 * Payload for a Quick Entry create: the module's own form model minus the id and
 * every computed field (the backend derives those on create; sending them would
 * pin values the user never typed).
 */
export function referenceCreatePayload(
  module: FreightModule,
  model: Record<string, unknown>,
): Record<string, unknown> {
  const computedKeys = new Set(module.fields.filter(field => field.computed).map(field => field.key))
  return Object.fromEntries(
    Object.entries(model).filter(([key]) => key !== 'id' && !computedKeys.has(key)),
  )
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
